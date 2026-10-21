import { afterEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, mockFetch } from "@/test/utils";
import { ApiError, CSRF_HEADER, errorMessage, fieldError, isPublicPath, request, setUnauthorizedHandler } from "./client";

const headersOf = (init?: RequestInit) => new Headers(init?.headers);

describe("api client", () => {
  let restore: (() => void) | undefined;
  afterEach(() => restore?.());

  it("sends the CSRF header on unsafe methods only, with same-origin credentials", async () => {
    const fetch = mockFetch(() => jsonResponse({ ok: true }));
    await request("/workspaces");
    await request("/workspaces", { method: "POST", body: { name: "Acme" } });
    await request("/repos/1", { method: "DELETE" });

    const [getCall, postCall, delCall] = fetch.mock.calls;
    expect(getCall![0]).toBe("/api/workspaces");
    expect(headersOf(getCall![1]).has(CSRF_HEADER)).toBe(false);
    expect(getCall![1]!.credentials).toBe("same-origin");

    expect(headersOf(postCall![1]).get(CSRF_HEADER)).toBe("1");
    expect(headersOf(postCall![1]).get("content-type")).toBe("application/json");
    expect(postCall![1]!.body).toBe(JSON.stringify({ name: "Acme" }));
    expect(headersOf(delCall![1]).get(CSRF_HEADER)).toBe("1");
  });

  it("builds query strings and skips empty values", async () => {
    const fetch = mockFetch(() => jsonResponse({ items: [] }));
    await request("/workspaces/acme/jobs", { query: { cursor: null, status: "failed", limit: 30, repo: "" } });
    expect(fetch.mock.calls[0]![0]).toBe("/api/workspaces/acme/jobs?status=failed&limit=30");
  });

  it("turns problem+json into an ApiError with detail, code and request id", async () => {
    mockFetch(() =>
      jsonResponse(
        { type: "x", title: "Conflict", status: 409, detail: "The document changed meanwhile.", code: "review_conflict", request_id: "r1" },
        409,
      ),
    );
    const err = await request("/review/doc/1/approve", { method: "POST" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const e = err as ApiError;
    expect(e.status).toBe(409);
    expect(e.code).toBe("review_conflict");
    expect(e.detail).toBe("The document changed meanwhile.");
    expect(e.requestId).toBe("r1");
    expect(errorMessage(e)).toBe("The document changed meanwhile.");
  });

  it("exposes validation field errors", async () => {
    mockFetch(() =>
      jsonResponse({ status: 422, detail: "Some fields are invalid.", code: "validation_error", errors: [{ loc: ["body", "email"], msg: "Not an email" }] }, 422),
    );
    const err = await request("/auth/signup", { method: "POST", body: {}, skipAuthRedirect: true }).catch((e: unknown) => e);
    expect(fieldError(err, "email")).toBe("Not an email");
    expect(fieldError(err, "password")).toBeUndefined();
  });

  it("formats 429 with retry_after, falling back to the Retry-After header", async () => {
    mockFetch(() => jsonResponse({ status: 429, detail: "Slow down and try again later.", code: "rate_limited", retry_after: 7 }, 429));
    const a = await request("/x").catch((e: unknown) => e);
    expect(errorMessage(a)).toBe("Slow down — retry in 7s.");

    mockFetch(() => new Response("", { status: 429, headers: { "retry-after": "12" } }));
    const b = await request("/x").catch((e: unknown) => e);
    expect((b as ApiError).retryAfter).toBe(12);
    expect(errorMessage(b)).toBe("Slow down — retry in 12s.");
  });

  it("gives a friendly message for gateway errors without a JSON body", async () => {
    mockFetch(() => new Response("<html>Bad gateway</html>", { status: 502, headers: { "content-type": "text/html" } }));
    const err = (await request("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.detail).toMatch(/unavailable/i);
  });

  it("maps network failures to ApiError status 0", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const err = (await request("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.code).toBe("network");
  });

  it("redirects to login with ?next on 401 from a private page", async () => {
    const handler = vi.fn();
    restore = setUnauthorizedHandler(handler);
    window.history.replaceState(null, "", "/w/acme/jobs?status=failed");
    mockFetch(() => jsonResponse({ status: 401, detail: "Please sign in.", code: "unauthorized" }, 401));

    const err = await request("/workspaces/acme/jobs").catch((e: unknown) => e);
    expect((err as ApiError).status).toBe(401);
    expect(handler).toHaveBeenCalledWith("/w/acme/jobs?status=failed");
  });

  it("does not redirect on 401 when opted out or on public pages", async () => {
    const handler = vi.fn();
    restore = setUnauthorizedHandler(handler);
    mockFetch(() => jsonResponse({ status: 401, detail: "Wrong email or password.", code: "invalid_credentials" }, 401));

    window.history.replaceState(null, "", "/w/acme");
    await request("/auth/login", { method: "POST", body: {}, skipAuthRedirect: true }).catch(() => undefined);
    window.history.replaceState(null, "", "/login");
    await request("/me").catch(() => undefined);
    expect(handler).not.toHaveBeenCalled();
  });

  it("knows which paths are public", () => {
    expect(isPublicPath("/")).toBe(true);
    expect(isPublicPath("/login")).toBe(true);
    expect(isPublicPath("/invite/abc")).toBe(true);
    expect(isPublicPath("/w/acme")).toBe(false);
    expect(isPublicPath("/account")).toBe(false);
  });
});
