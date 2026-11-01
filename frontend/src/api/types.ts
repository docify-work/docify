// Friendly aliases for the generated OpenAPI types (`npm run gen-api` → schema.d.ts).
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["MeOut"];
export type Membership = S["MembershipBrief"];
export type Identity = S["IdentityOut"];
export type Session = S["SessionOut"];
export type PublicConfig = S["PublicConfigOut"];
export type Demo = S["DemoOut"];
export type Workspace = S["WorkspaceOut"];
export type WorkspacePatch = S["WorkspacePatch"];
export type Member = S["MemberOut"];
export type Invite = S["InviteOut"];
export type InvitePublic = S["InvitePublicOut"];
export type Installation = S["InstallationOut"];
export type GithubRepoOption = S["GithubRepoOption"];
export type Repo = S["RepoOut"];
export type Doc = S["DocOut"];
export type DocDetail = S["DocDetailOut"];
export type DocVersion = S["DocVersionOut"];
export type Changelog = S["ChangelogOut"];
export type ReviewItem = S["ReviewItemOut"];
export type Job = S["JobOut"];
export type SearchOut = S["SearchOut"];
export type SearchHit = S["SearchHitOut"];
export type ChatIn = S["ChatIn"];
export type ChatSource = S["ChatSource"];
export type ChatMessage = S["ChatMessageOut"];
export type Thread = S["ThreadOut"];
export type ThreadDetail = S["ThreadDetailOut"];
export type Ok = S["Ok"];
export type Role = "admin" | "member";

export interface Page<T> {
  items: T[];
  next_cursor?: string | null;
}

export type RepoStatus =
  | "pending"
  | "indexing"
  | "ready"
  | "error"
  | "empty"
  | "too_large"
  | "disconnected"
  | "suspended";

export type JobStatus =
  "queued" | "running" | "succeeded" | "failed" | "dead" | "blocked_budget";

// ------------------------------------------------------------------ checks, issues, insights (D66)
export type Policy = S["PolicyOut"];
export type PolicyIn = S["PolicyIn"];
export type PolicyPatch = S["PolicyPatch"];
export type PolicyTemplate = S["PolicyTemplateOut"];
export type PolicyTestOut = S["PolicyTestOut"];
export type Finding = S["FindingOut"];
export type FindingsOut = S["FindingsOut"];
export type FindingPatch = S["FindingPatch"];
export type Issue = S["IssueOut"];
export type IssueIn = S["IssueIn"];
export type IssuePatch = Partial<S["IssuePatch"]>;
export type Suspect = S["Suspect"];
export type GithubIssue = S["GithubIssueOut"];
export type Contributor = S["ContributorOut"];
export type Severity = Policy["severity"];
export type FindingStatus = Finding["status"];
export type IssueStatus = Issue["status"];

/** GET /repos/{id}/insights (free-form JSON on the API side). */
export interface Insights {
  repo: {
    id: string;
    full_name: string;
    default_branch: string;
    github_created_at: string | null;
  };
  totals: {
    commits: number;
    contributors: number;
    prs_merged: number;
    additions: number;
    deletions: number;
    files: number;
    lines: number;
    docs: number;
    open_findings: number;
    open_issues: number;
    first_commit: string | null;
    last_commit: string | null;
    days_since_last_commit: number | null;
    bus_factor: number;
  };
  contributors: {
    login: string | null;
    name: string;
    commits: number;
    share: number;
    additions: number;
    deletions: number;
    files_touched: number;
    prs: number;
    first_commit: string;
    last_commit: string;
    top_areas: { area: string; changes: number }[];
    recent_commits: {
      sha: string;
      title: string;
      date: string;
      pr: number | null;
    }[];
  }[];
  weekly_commits: { week_start: string; commits: number }[];
  heatmap: { weekday: number; hour: number; commits: number }[];
  hot_files: { path: string; changes: number; authors: number }[];
  languages: { language: string; files: number; lines: number }[];
  findings_by_severity: Record<string, number>;
  health: { score: number; grade: string; notes: string[] };
  github: {
    stars: number;
    forks: number;
    watchers: number;
    open_issues: number;
    size_kb: number;
    license: string | null;
    topics: string[];
    description: string | null;
    homepage: string | null;
    created_at: string | null;
    pushed_at: string | null;
    visibility: string | null;
    languages: Record<string, number>;
    pulls: {
      total: number;
      open: number;
      merged: number;
      closed_unmerged: number;
      avg_hours_to_merge: number | null;
      by_author: { login: string; count: number }[];
      recent: {
        number: number;
        title: string;
        state: string;
        merged: boolean;
        author: string | null;
        url: string;
        updated_at: string;
      }[];
    };
  } | null;
  github_updated_at: string | null;
}
