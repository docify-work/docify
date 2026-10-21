// One function per API endpoint (contract: frontend/openapi.json). Pages call these through TanStack Query.
import { ApiError, apiFetch, request } from "./client";
import { readSSE } from "./sse";
import type {
  Changelog,
  ChatIn,
  ChatSource,
  Demo,
  DocDetail,
  Doc,
  DocVersion,
  Identity,
  Installation,
  Invite,
  InvitePublic,
  Job,
  Me,
  Member,
  Ok,
  Page,
  PublicConfig,
  Repo,
  ReviewItem,
  Role,
  SearchOut,
  Session,
  Thread,
  ThreadDetail,
  Workspace,
  WorkspacePatch,
} from "./types";

const enc = encodeURIComponent;

// ------------------------------------------------------------------ public
export const getPublicConfig = () => request<PublicConfig>("/config", { skipAuthRedirect: true });
export const getDemo = () => request<Demo>("/demo", { skipAuthRedirect: true });

// ------------------------------------------------------------------ auth
export const auth = {
  signup: (body: { email: string; password: string; name?: string | null }) =>
    request<Ok>("/auth/signup", { method: "POST", body, skipAuthRedirect: true }),
  login: (body: { email: string; password: string }) =>
    request<Ok>("/auth/login", { method: "POST", body, skipAuthRedirect: true }),
  logout: () => request<Ok>("/auth/logout", { method: "POST", skipAuthRedirect: true }),
  verifyEmail: (token: string) =>
    request<Ok>("/auth/verify-email", { method: "POST", body: { token }, skipAuthRedirect: true }),
  resendVerification: (email: string) =>
    request<Ok>("/auth/resend-verification", { method: "POST", body: { email }, skipAuthRedirect: true }),
  forgotPassword: (email: string) =>
    request<Ok>("/auth/forgot-password", { method: "POST", body: { email }, skipAuthRedirect: true }),
  resetPassword: (token: string, password: string) =>
    request<Ok>("/auth/reset-password", { method: "POST", body: { token, password }, skipAuthRedirect: true }),
};

/** Browser navigation target for OAuth (not fetch — it's a redirect chain). */
export function oauthStartUrl(provider: "github" | "google", purpose: "login" | "link", redirectTo?: string): string {
  const params = new URLSearchParams({ purpose });
  if (redirectTo) params.set("redirect_to", redirectTo);
  return `/api/auth/${provider}/start?${params.toString()}`;
}

// ------------------------------------------------------------------ me
/** Returns null when not signed in (401) instead of redirecting. */
export async function getMe(): Promise<Me | null> {
  try {
    return await request<Me>("/me", { skipAuthRedirect: true });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}
export const me = {
  update: (name: string | null) => request<Me>("/me", { method: "PATCH", body: { name } }),
  remove: () => request<Ok>("/me", { method: "DELETE" }),
  changePassword: (body: { current_password?: string | null; new_password: string }) =>
    request<Ok>("/me/password", { method: "POST", body }),
  identities: () => request<Identity[]>("/me/identities"),
  unlink: (id: string) => request<Ok>(`/me/identities/${enc(id)}`, { method: "DELETE" }),
  sessions: () => request<Session[]>("/me/sessions"),
  revokeSession: (id: string) => request<Ok>(`/me/sessions/${enc(id)}`, { method: "DELETE" }),
};

// ------------------------------------------------------------------ workspaces
export const workspaces = {
  list: () => request<Workspace[]>("/workspaces"),
  create: (body: { name: string; slug?: string | null }) =>
    request<Workspace>("/workspaces", { method: "POST", body }),
  get: (ws: string) => request<Workspace>(`/workspaces/${enc(ws)}`),
  update: (ws: string, body: WorkspacePatch) =>
    request<Workspace>(`/workspaces/${enc(ws)}`, { method: "PATCH", body }),
  remove: (ws: string) => request<Ok>(`/workspaces/${enc(ws)}`, { method: "DELETE" }),
  members: (ws: string) => request<Member[]>(`/workspaces/${enc(ws)}/members`),
  setRole: (ws: string, userId: string, role: Role) =>
    request<Ok>(`/workspaces/${enc(ws)}/members/${enc(userId)}`, { method: "PATCH", body: { role } }),
  removeMember: (ws: string, userId: string) =>
    request<Ok>(`/workspaces/${enc(ws)}/members/${enc(userId)}`, { method: "DELETE" }),
  leave: (ws: string) => request<Ok>(`/workspaces/${enc(ws)}/leave`, { method: "POST" }),
  invites: (ws: string) => request<Invite[]>(`/workspaces/${enc(ws)}/invites`),
  invite: (ws: string, body: { email: string; role: Role }) =>
    request<Invite>(`/workspaces/${enc(ws)}/invites`, { method: "POST", body }),
  revokeInvite: (ws: string, id: string) =>
    request<Ok>(`/workspaces/${enc(ws)}/invites/${enc(id)}`, { method: "DELETE" }),
};

export const invites = {
  get: (token: string) => request<InvitePublic>(`/invites/${enc(token)}`, { skipAuthRedirect: true }),
  accept: (token: string) => request<Workspace>(`/invites/${enc(token)}/accept`, { method: "POST" }),
};

// ------------------------------------------------------------------ github
export const github = {
  installUrl: (ws: string) => request<{ url: string }>(`/workspaces/${enc(ws)}/github/install-url`),
  installations: (ws: string) => request<Installation[]>(`/workspaces/${enc(ws)}/github/installations`),
  attach: (ws: string, installationId: number, ids: number[]) =>
    request<Repo[]>(`/workspaces/${enc(ws)}/github/installations/${installationId}/repos`, {
      method: "POST",
      body: { github_repo_ids: ids },
    }),
};

// ------------------------------------------------------------------ repos & docs
export const repos = {
  list: (ws: string) => request<Repo[]>(`/workspaces/${enc(ws)}/repos`),
  get: (id: string) => request<Repo>(`/repos/${enc(id)}`),
  resync: (id: string) => request<Ok>(`/repos/${enc(id)}/resync`, { method: "POST" }),
  reindex: (id: string) => request<Ok>(`/repos/${enc(id)}/reindex`, { method: "POST" }),
  remove: (id: string) => request<Ok>(`/repos/${enc(id)}`, { method: "DELETE" }),
  changelog: (id: string, cursor?: string | null) =>
    request<Page<Changelog>>(`/repos/${enc(id)}/changelog`, { query: { cursor, limit: 20 } }),
};

export const docs = {
  list: (ws: string, repo?: string) => request<Doc[]>(`/workspaces/${enc(ws)}/docs`, { query: { repo } }),
  get: (id: string) => request<DocDetail>(`/docs/${enc(id)}`),
  versions: (id: string) => request<DocVersion[]>(`/docs/${enc(id)}/versions`),
};

export const review = {
  list: (ws: string) => request<ReviewItem[]>(`/workspaces/${enc(ws)}/review`),
  decide: (kind: "doc" | "changelog", id: string, decision: "approve" | "reject") =>
    request<Ok>(`/review/${kind}/${enc(id)}/${decision}`, { method: "POST" }),
};

export const jobs = {
  list: (ws: string, opts: { cursor?: string | null; status?: string; limit?: number } = {}) =>
    request<Page<Job>>(`/workspaces/${enc(ws)}/jobs`, {
      query: { cursor: opts.cursor, status: opts.status, limit: opts.limit },
    }),
  retry: (id: string) => request<Ok>(`/jobs/${enc(id)}/retry`, { method: "POST" }),
};

// ------------------------------------------------------------------ search & chat
export const search = (ws: string, q: string, scope: "code" | "docs", repo?: string) =>
  request<SearchOut>(`/workspaces/${enc(ws)}/search`, { query: { q, scope, repo } });

export const threads = {
  list: (ws: string) => request<Thread[]>(`/workspaces/${enc(ws)}/chat/threads`),
  get: (id: string) => request<ThreadDetail>(`/chat/threads/${enc(id)}`),
  remove: (id: string) => request<Ok>(`/chat/threads/${enc(id)}`, { method: "DELETE" }),
};

export interface ChatHandlers {
  onMeta?: (threadId: string) => void;
  onToken: (text: string) => void;
  onSources?: (sources: ChatSource[]) => void;
  onError?: (message: string) => void;
  onDone?: (threadId: string | null) => void;
}

/** POST /workspaces/{ws}/chat and consume the SSE stream. Throws ApiError if the request itself fails. */
export async function streamChat(ws: string, body: ChatIn, handlers: ChatHandlers, signal?: AbortSignal) {
  const res = await apiFetch(`/workspaces/${enc(ws)}/chat`, {
    method: "POST",
    body,
    signal,
    headers: { Accept: "text/event-stream" },
  });
  await readSSE(res, ({ event, data }) => {
    let payload: unknown;
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }
    const p = payload as Record<string, unknown>;
    switch (event) {
      case "meta":
        handlers.onMeta?.(String(p.thread_id));
        break;
      case "token":
        handlers.onToken(String(p.text ?? ""));
        break;
      case "sources":
        handlers.onSources?.(Array.isArray(payload) ? (payload as ChatSource[]) : []);
        break;
      case "error":
        handlers.onError?.(String(p.message ?? "Something went wrong."));
        break;
      case "done":
        handlers.onDone?.(p.thread_id ? String(p.thread_id) : null);
        break;
      default:
        break;
    }
  });
}

// ------------------------------------------------------------------ query keys
export const qk = {
  me: ["me"] as const,
  config: ["config"] as const,
  workspace: (ws: string) => ["ws", ws] as const,
  repos: (ws: string) => ["ws", ws, "repos"] as const,
  repo: (id: string) => ["repo", id] as const,
  installations: (ws: string) => ["ws", ws, "installations"] as const,
  docs: (ws: string, repo?: string) => ["ws", ws, "docs", repo ?? "all"] as const,
  doc: (id: string) => ["doc", id] as const,
  docVersions: (id: string) => ["doc", id, "versions"] as const,
  changelog: (id: string) => ["repo", id, "changelog"] as const,
  review: (ws: string) => ["ws", ws, "review"] as const,
  jobs: (ws: string, status?: string) => ["ws", ws, "jobs", status ?? "all"] as const,
  members: (ws: string) => ["ws", ws, "members"] as const,
  invites: (ws: string) => ["ws", ws, "invites"] as const,
  invite: (token: string) => ["invite", token] as const,
  threads: (ws: string) => ["ws", ws, "threads"] as const,
  thread: (id: string) => ["thread", id] as const,
  search: (ws: string, q: string, scope: string, repo?: string) => ["ws", ws, "search", q, scope, repo ?? ""] as const,
  identities: ["me", "identities"] as const,
  sessions: ["me", "sessions"] as const,
};
