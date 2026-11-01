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
    kind: Literal["code", "commit"] = "code"
    repo: str
    commit_sha: str
    url: str
    # kind=code
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    # kind=commit
    title: str | None = None
    author: str | None = None
    date: datetime | None = None


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


# ----------------------------------------------------------------------------- checks, issues, insights (D66)

Severity = Literal["info", "low", "medium", "high", "critical"]


class PolicyOut(Out):
    id: uuid.UUID
    name: str
    description: str | None
    kind: Literal["regex", "terms"]
    pattern: str
    severity: Severity
    paths: str | None
    enabled: bool
    template: str | None
    created_at: datetime


class PolicyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    kind: Literal["regex", "terms"] = "terms"
    pattern: str = Field(min_length=1, max_length=500)
    severity: Severity = "medium"
    paths: str | None = Field(default=None, max_length=300)
    enabled: bool = True


class PolicyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    kind: Literal["regex", "terms"] | None = None
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    severity: Severity | None = None
    paths: str | None = Field(default=None, max_length=300)
    enabled: bool | None = None


class PolicyTestIn(BaseModel):
    kind: Literal["regex", "terms"]
    pattern: str = Field(min_length=1, max_length=500)
    sample: str = Field(max_length=5000)


class PolicyTestOut(Out):
    ok: bool
    error: str | None = None
    matches: list[dict[str, Any]] = []


class PolicyTemplateOut(Out):
    key: str
    name: str
    description: str
    kind: str
    severity: str
    paths: str
    enabled: bool


class ScanIn(BaseModel):
    repo_id: uuid.UUID | None = None


class ScanOut(Out):
    repos: int
    findings_created: int


class FindingOut(Out):
    id: uuid.UUID
    repo_id: uuid.UUID
    repo_full_name: str = ""
    policy_id: uuid.UUID | None
    policy_name: str
    severity: Severity
    status: Literal["open", "acknowledged", "resolved", "false_positive"]
    source: str
    path: str
    line: int | None
    snippet: str
    match: str
    commit_sha: str | None
    commit_message: str | None
    author_name: str | None
    author_login: str | None
    committed_at: datetime | None
    pr_number: int | None
    assignee_login: str | None
    note: str | None
    issue_number: int | None = None
    url: str | None = None
    created_at: datetime


class FindingsOut(Out):
    items: list[FindingOut]
    counts: dict[str, int]


class FindingPatch(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "false_positive"] | None = None
    assignee_login: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class SuspectReason(Out):
    text: str
    url: str | None = None


class Suspect(Out):
    login: str | None
    name: str
    score: float
    confidence: float
    reasons: list[SuspectReason]


class IssueOut(Out):
    id: uuid.UUID
    number: int
    repo_id: uuid.UUID | None
    repo_full_name: str | None = None
    title: str
    body: str | None
    status: Literal["open", "in_progress", "resolved", "closed"]
    severity: Severity
    source: Literal["docify", "github", "finding"]
    paths: list[str]
    github_number: int | None
    github_url: str | None
    github_author: str | None
    finding_id: uuid.UUID | None
    suspects: list[Suspect]
    analyzed_at: datetime | None
    assignee_login: str | None
    assigned_at: datetime | None
    created_at: datetime
    closed_at: datetime | None


class IssueIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    body: str | None = Field(default=None, max_length=20000)
    repo_id: uuid.UUID | None = None
    severity: Severity = "medium"
    paths: list[str] = Field(default_factory=list, max_length=20)


class IssuePatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    body: str | None = Field(default=None, max_length=20000)
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    severity: Severity | None = None
    assignee_login: str | None = Field(default=None, max_length=100)
    unassign: bool = False


class GithubIssueOut(Out):
    number: int
    title: str
    state: str
    author: str | None
    labels: list[str]
    comments: int
    url: str
    created_at: datetime
    imported_issue_number: int | None = None


class GithubImportIn(BaseModel):
    repo_id: uuid.UUID
    number: int = Field(ge=1)


class ContributorOut(Out):
    login: str | None
    name: str
    commits: int
    last_commit: datetime
