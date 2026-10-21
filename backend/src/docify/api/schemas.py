"""Request/response models — the API contract (frontend types are generated from OpenAPI)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["admin", "member"]
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])$")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ok(Out):
    ok: bool = True
    message: str | None = None


# ----------------------------------------------------------------------------- health / config


class VersionOut(Out):
    version: str
    env: str


class PublicConfigOut(Out):
    env: str
    version: str
    github_enabled: bool
    google_enabled: bool
    github_app_slug: str | None
    demo_workspace_slug: str


# ----------------------------------------------------------------------------- auth


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetPasswordIn(TokenIn):
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class PatchMeIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class IdentityOut(Out):
    id: uuid.UUID
    provider: str
    login: str | None
    email: str | None
    created_at: datetime


class MembershipBrief(Out):
    id: uuid.UUID
    slug: str
    name: str
    role: Role
    is_public_demo: bool


class MeOut(Out):
    id: uuid.UUID
    email: str
    name: str | None
    avatar_url: str | None
    email_verified: bool
    has_password: bool
    identities: list[IdentityOut]
    workspaces: list[MembershipBrief]


class SessionOut(Out):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


# ----------------------------------------------------------------------------- workspaces


class WorkspaceSettings(BaseModel):
    auto_publish: bool = True
    chat_enabled: bool = True


class WorkspaceSettingsPatch(BaseModel):
    auto_publish: bool | None = None
    chat_enabled: bool | None = None


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=50)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is not None and not SLUG.match(v):
            raise ValueError("Use 3-50 lowercase letters, digits or dashes.")
        return v


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    settings: WorkspaceSettingsPatch | None = None


class WorkspaceOut(Out):
    id: uuid.UUID
    slug: str
    name: str
    role: Role | None
    is_public_demo: bool
    settings: WorkspaceSettings
    created_at: datetime
    repo_count: int = 0
    member_count: int = 0


class MemberOut(Out):
    user_id: uuid.UUID
    email: str
    name: str | None
    avatar_url: str | None
    role: Role
    joined_at: datetime


class MemberPatch(BaseModel):
    role: Role


class InviteIn(BaseModel):
    email: EmailStr
    role: Role = "member"


class InviteOut(Out):
    id: uuid.UUID
    email: str
    role: Role
    expires_at: datetime
    created_at: datetime


class InvitePublicOut(Out):
    workspace_name: str
    workspace_slug: str
    email: str
    role: Role
    expired: bool


# ----------------------------------------------------------------------------- GitHub


class InstallUrlOut(Out):
    url: str


class GithubRepoOption(Out):
    github_repo_id: int
    full_name: str
    private: bool
    default_branch: str | None
    attached_workspace: str | None  # slug if already attached somewhere you can see; "other" otherwise


class InstallationOut(Out):
    installation_id: int
    account_login: str
    account_type: str
    suspended: bool
    repos: list[GithubRepoOption]


class AttachReposIn(BaseModel):
    github_repo_ids: list[int] = Field(min_length=1, max_length=20)


# ----------------------------------------------------------------------------- repos / docs


class RepoOut(Out):
    id: uuid.UUID
    workspace_id: uuid.UUID
    full_name: str
    owner: str
    name: str
    default_branch: str
    private: bool
    archived: bool
    status: str
    last_processed_sha: str | None
    last_synced_at: datetime | None
    error: dict[str, Any] | None
    html_url: str
    created_at: datetime


class VersionBrief(Out):
    id: uuid.UUID
    version: int
    status: str
    commit_sha: str
    model: str | None
    partial: bool
    created_at: datetime


class DocOut(Out):
    id: uuid.UUID
    repo_id: uuid.UUID
    repo_full_name: str
    kind: str
    title: str
    published: VersionBrief | None
    has_pending_review: bool
    updated_at: datetime | None


class DocDetailOut(DocOut):
    content_md: str | None  # citations rendered as GitHub permalinks
    source_paths: list[str]
    repo_html_url: str
    commit_url: str | None


class DocVersionOut(VersionBrief):
    content_md: str


class ChangelogOut(Out):
    id: uuid.UUID
    repo_id: uuid.UUID
    from_sha: str | None
    to_sha: str
    content_md: str
    pr_numbers: list[int]
    status: str
    created_at: datetime


class ReviewItemOut(Out):
    kind: Literal["doc", "changelog"]
    id: uuid.UUID
    repo_id: uuid.UUID
    repo_full_name: str
    title: str
    content_md: str
    base_content_md: str | None
    created_at: datetime


# ----------------------------------------------------------------------------- search / chat


class SearchHitOut(Out):
    kind: Literal["code", "doc", "changelog"]
    repo_id: uuid.UUID
    repo_full_name: str
    title: str
    snippet: str
    url: str | None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    doc_id: uuid.UUID | None = None
    changelog_id: uuid.UUID | None = None
    score: float  # snippets mark matches with «…» (plain text, never HTML)


class SearchOut(Out):
    query: str
    scope: Literal["code", "docs"]
    hits: list[SearchHitOut]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: uuid.UUID | None = None
    repo_ids: list[uuid.UUID] | None = None


class ChatSource(Out):
    n: int
    repo: str
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    url: str


class ChatMessageOut(Out):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[ChatSource] | None
    created_at: datetime


class ThreadOut(Out):
    id: uuid.UUID
    title: str | None
    created_at: datetime


class ThreadDetailOut(ThreadOut):
    messages: list[ChatMessageOut]


# ----------------------------------------------------------------------------- jobs


class JobOut(Out):
    id: uuid.UUID
    type: str
    status: str
    attempts: int
    max_attempts: int
    repo_id: uuid.UUID | None
    repo_full_name: str | None
    error: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    run_after: datetime


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class DemoOut(Out):
    workspace_slug: str | None
    available: bool
