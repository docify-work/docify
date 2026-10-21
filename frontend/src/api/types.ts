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

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "dead" | "blocked_budget";
