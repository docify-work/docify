"""ORM models — mirrors Master Doc §6 (Data Model).

Every tenant-owned row carries `workspace_id`, and all access goes through the
repo layer with a principal (`docify.db.repo`), so cross-tenant reads are hard
to write by accident.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from docify.db.base import Base, IdMixin, TimestampMixin

EMBED_DIM = 1024  # voyage-code-3 (D18). Changing it needs a migration + reembed.


def _check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name)


# ----------------------------------------------------------------------------- identity


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    name: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    disabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_gen: Mapped[int] = mapped_column(Integer, server_default=text("0"))


PROVIDERS = ("github", "google")


class AuthIdentity(IdMixin, TimestampMixin, Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id"),
        _check_in("provider", PROVIDERS, "provider"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(CITEXT)
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    login: Mapped[str | None] = mapped_column(String(100))  # GitHub login, for display


class Session(IdMixin, TimestampMixin, Base):
    __tablename__ = "sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hmac: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))


EMAIL_TOKEN_PURPOSES = ("verify", "reset", "signup_notice")


class EmailToken(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_tokens"
    __table_args__ = (_check_in("purpose", EMAIL_TOKEN_PURPOSES, "purpose"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    token_hmac: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Verify tokens carry the password chosen by whoever requested *this* link; verifying applies it
    # (or wipes the password if none), so a stranger's password on an unverified account never survives.
    password_hash: Mapped[str | None] = mapped_column(String(255))


OAUTH_PURPOSES = ("login", "link", "install")


class OAuthState(TimestampMixin, Base):
    __tablename__ = "oauth_states"
    __table_args__ = (_check_in("purpose", OAUTH_PURPOSES, "purpose"),)
    state_hmac: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(20))
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    code_verifier: Mapped[str | None] = mapped_column(String(128))
    nonce: Mapped[str | None] = mapped_column(String(128))
    redirect_to: Mapped[str | None] = mapped_column(String(300))
    installation_id: Mapped[int | None] = mapped_column(BigInteger)  # install flow: set by the Setup URL step
    browser_hmac: Mapped[bytes | None] = mapped_column(LargeBinary)  # binds the flow to the starting browser
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ----------------------------------------------------------------------------- workspaces

ROLES = ("admin", "member")


class Workspace(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_public_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("""'{"auto_publish": true, "chat_enabled": true}'::jsonb""")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Membership(IdMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"), _check_in("role", ROLES, "role"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))


class Invite(IdMixin, TimestampMixin, Base):
    __tablename__ = "invites"
    __table_args__ = (
        Index(
            "uq_invites_open_email", "workspace_id", "email", unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        _check_in("role", ROLES, "role"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(CITEXT)
    role: Mapped[str] = mapped_column(String(10))
    token_hmac: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ----------------------------------------------------------------------------- GitHub


class GithubInstallation(IdMixin, TimestampMixin, Base):
    __tablename__ = "github_installations"
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    account_login: Mapped[str] = mapped_column(String(100))
    account_type: Mapped[str] = mapped_column(String(20))
    repository_selection: Mapped[str | None] = mapped_column(String(20))
    permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    installed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceInstallation(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspace_installations"
    __table_args__ = (UniqueConstraint("workspace_id", "installation_id"),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    installation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("github_installations.installation_id", ondelete="CASCADE"), index=True
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Repos the connecting user can actually see in this installation (from /user/installations/{id}/repositories).
    # Org installations expose every repo to the installation token, so attach is limited to this list.
    allowed_repo_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default=text("'{}'"))


REPO_STATUSES = (
    "pending", "indexing", "ready", "error", "empty", "too_large", "disconnected", "suspended",
)


class Repository(IdMixin, TimestampMixin, Base):
    __tablename__ = "repositories"
    __table_args__ = (_check_in("status", REPO_STATUSES, "status"),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    installation_id: Mapped[int] = mapped_column(BigInteger)
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(201))
    default_branch: Mapped[str] = mapped_column(String(255))
    indexed_branch: Mapped[str | None] = mapped_column(String(255))
    private: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    last_processed_sha: Mapped[str | None] = mapped_column(String(40))
    last_full_index_sha: Mapped[str | None] = mapped_column(String(40))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    size_kb: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sync_lease_owner: Mapped[str | None] = mapped_column(String(100))
    sync_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ----------------------------------------------------------------------------- content


class File(IdMixin, TimestampMixin, Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("repo_id", "path"),)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Text)
    blob_sha: Mapped[str] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    line_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    summary: Mapped[str | None] = mapped_column(Text)
    symbols: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    summary_model: Mapped[str | None] = mapped_column(String(60))
    summary_blob_sha: Mapped[str | None] = mapped_column(String(64))


class Chunk(IdMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_ws_repo", "workspace_id", "repo_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunks_path_trgm", "path", postgresql_using="gin", postgresql_ops={"path": "gin_trgm_ops"}),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    commit_sha: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    search_text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', search_text)", persisted=True)
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    embed_model: Mapped[str | None] = mapped_column(String(60))


DOC_KINDS = ("overview", "setup", "api")
VERSION_STATUSES = ("published", "pending_review", "rejected", "superseded")


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("repo_id", "kind"), _check_in("kind", DOC_KINDS, "kind"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True)
    )
    source_paths: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))


class DocumentVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version"),
        _check_in("status", VERSION_STATUSES, "status"),
        Index("ix_document_versions_tsv", "tsv", postgresql_using="gin"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_md: Mapped[str] = mapped_column(Text)
    commit_sha: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))
    partial: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('english', content_md)", persisted=True))


CHANGELOG_STATUSES = ("published", "pending_review", "rejected")


class ChangelogEntry(IdMixin, TimestampMixin, Base):
    __tablename__ = "changelog_entries"
    __table_args__ = (
        Index("ix_changelog_repo_created", "repo_id", text("created_at DESC")),
        _check_in("status", CHANGELOG_STATUSES, "status"),
        Index("ix_changelog_entries_tsv", "tsv", postgresql_using="gin"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    from_sha: Mapped[str | None] = mapped_column(String(40))
    to_sha: Mapped[str] = mapped_column(String(40))
    content_md: Mapped[str] = mapped_column(Text)
    pr_numbers: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(String(20))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('english', content_md)", persisted=True))


# ----------------------------------------------------------------------------- jobs

JOB_TYPES = ("repo_index", "repo_sync", "repo_purge", "installation_sync", "reembed")
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "dead", "blocked_budget")


class Job(IdMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "uq_jobs_dedupe_open", "dedupe_key", unique=True,
            postgresql_where=text("status IN ('queued', 'blocked_budget')"),
        ),
        Index("ix_jobs_status_run_after", "status", "run_after"),
        Index("ix_jobs_status_lease", "status", "lease_expires_at"),
        Index("ix_jobs_ws_created", "workspace_id", text("created_at DESC")),
        _check_in("type", JOB_TYPES, "type"),
        _check_in("status", JOB_STATUSES, "status"),
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    repo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repositories.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'queued'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event: Mapped[str] = mapped_column(String(60))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Singleton(Base):
    __tablename__ = "singletons"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ----------------------------------------------------------------------------- AI usage & chat


class LlmUsage(IdMixin, TimestampMixin, Base):
    __tablename__ = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_created", "created_at"),
        Index("ix_llm_usage_ws_created", "workspace_id", "created_at"),
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), server_default=text("0"))


class ChatThread(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_threads"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200))


class ChatMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)


class AuditEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_ws_created", "workspace_id", "created_at"),)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(200))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
