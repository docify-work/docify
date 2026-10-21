export type BackendState = "unknown" | "awake" | "sleeping";

/**
 * Probe `/api/health` with a timeout. 502/503/504, timeouts and network errors mean the
 * (scale-to-zero) demo server is asleep (Master Doc §5.1). Other statuses count as awake.
 */
export async function probeBackend(timeoutMs = 4000, fetchImpl: typeof fetch = fetch): Promise<BackendState> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetchImpl("/api/health", { signal: ctrl.signal, cache: "no-store", credentials: "same-origin" });
    return [502, 503, 504].includes(res.status) ? "sleeping" : "awake";
  } catch {
    return "sleeping";
  } finally {
    clearTimeout(timer);
  }
}

export const SLEEPING_MESSAGE = "The demo backend is sleeping — it can be started in about 5 minutes.";
