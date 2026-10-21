/**
 * Thin typed fetch wrapper for the Docify API (same-origin `/api/*`).
 *
 * - Sends the session cookie (`credentials: "same-origin"`).
 * - Adds `X-Docify-CSRF: 1` on every non-GET request (Master Doc §10.5).
 * - Turns RFC 9457 problem+json responses into `ApiError`.
 * - On 401 calls the registered "unauthorized" handler (redirect to /login?next=…),
 *   unless the request opted out (`skipAuthRedirect`) or the user is on a public page.
 */

export const API_PREFIX = "/api";
export const CSRF_HEADER = "X-Docify-CSRF";

export interface Problem {
  type?: string;
  title?: string;
  status?: number;
  detail?: string | null;
  code?: string;
  request_id?: string | null;
  errors?: { loc: string[]; msg: string }[];
  retry_after?: number;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly requestId: string | null;
  readonly retryAfter: number | null;
  readonly fieldErrors: { loc: string[]; msg: string }[];

  constructor(status: number, problem: Problem, fallback?: string) {
    const detail = problem.detail || problem.title || fallback || `Request failed (${status}).`;
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = problem.code ?? (status === 0 ? "network" : `http_${status}`);
    this.detail = detail;
    this.requestId = problem.request_id ?? null;
    this.retryAfter = typeof problem.retry_after === "number" ? problem.retry_after : null;
    this.fieldErrors = problem.errors ?? [];
  }
}

/** Human message for any error (ApiError or not). 429 gets a "slow down" hint. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429 && err.retryAfter != null) {
      return `Slow down — retry in ${err.retryAfter}s.`;
    }
    return err.detail;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

/** Field-level message from a 422 validation problem, keyed by the last `loc` segment. */
export function fieldError(err: unknown, field: string): string | undefined {
  if (!(err instanceof ApiError)) return undefined;
  return err.fieldErrors.find((e) => e.loc[e.loc.length - 1] === field)?.msg;
}

// ------------------------------------------------------------------ 401 handling

const PUBLIC_PATHS = [
  /^\/$/,
  /^\/login\/?$/,
  /^\/signup\/?$/,
  /^\/verify-email\/?$/,
  /^\/forgot-password\/?$/,
  /^\/reset-password\/?$/,
  /^\/privacy\/?$/,
  /^\/invite\/[^/]+\/?$/,
];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((re) => re.test(pathname));
}

export function loginUrl(next?: string): string {
  return next && next !== "/" ? `/login?next=${encodeURIComponent(next)}` : "/login";
}

type UnauthorizedHandler = (next: string) => void;

const defaultUnauthorized: UnauthorizedHandler = (next) => {
  window.location.assign(loginUrl(next));
};

let onUnauthorized: UnauthorizedHandler = defaultUnauthorized;

/** The app installs a router-aware handler; tests can install a spy. Returns a restore fn. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): () => void {
  onUnauthorized = handler;
  return () => {
    onUnauthorized = defaultUnauthorized;
  };
}

function handleUnauthorized(): void {
  const { pathname, search } = window.location;
  if (isPublicPath(pathname)) return;
  onUnauthorized(pathname + search);
}

// ------------------------------------------------------------------ requests

export type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** Don't redirect to /login on 401 (e.g. `GET /me`, login form). */
  skipAuthRedirect?: boolean;
}

export function buildUrl(path: string, query?: Query): string {
  let url = API_PREFIX + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}

async function toApiError(res: Response): Promise<ApiError> {
  let problem: Problem = {};
  const type = res.headers.get("content-type") ?? "";
  if (type.includes("json")) {
    try {
      problem = (await res.json()) as Problem;
    } catch {
      problem = {};
    }
  }
  if (problem.retry_after == null) {
    const header = Number(res.headers.get("retry-after"));
    if (Number.isFinite(header) && header > 0) problem.retry_after = header;
  }
  const fallback =
    res.status >= 502 && res.status <= 504
      ? "The server is unavailable right now. Try again in a moment."
      : res.statusText || undefined;
  return new ApiError(res.status, problem, fallback);
}

/** Low-level: performs the request, throws ApiError for non-2xx, returns the raw Response. */
export async function apiFetch(path: string, opts: RequestOptions = {}): Promise<Response> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  if (method !== "GET") headers[CSRF_HEADER] = "1";
  let body: string | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, { code: "network" }, "Can't reach the server. Check your connection.");
  }

  if (!res.ok) {
    const error = await toApiError(res);
    if (res.status === 401 && !opts.skipAuthRedirect) handleUnauthorized();
    throw error;
  }
  return res;
}

/** JSON request. Empty bodies resolve to `undefined`. */
export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await apiFetch(path, opts);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
