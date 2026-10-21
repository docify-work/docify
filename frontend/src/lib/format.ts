const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto", style: "short" });
const dtf = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });
const df = new Intl.DateTimeFormat("en", { dateStyle: "medium" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const diff = Math.round((t - now) / 1000);
  const abs = Math.abs(diff);
  if (abs < 45) return "just now";
  for (const [unit, secs] of UNITS) {
    if (abs >= secs) return rtf.format(Math.round(diff / secs), unit);
  }
  return rtf.format(Math.round(diff / 60), "minute");
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dtf.format(d);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : df.format(d);
}

export const shortSha = (sha: string | null | undefined) => (sha ? sha.slice(0, 7) : "—");

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Best-effort one-line summary of a backend `error` JSON object (repo/job). */
export function summarizeError(err: unknown): string | null {
  if (!err) return null;
  if (typeof err === "string") return err;
  if (typeof err === "object") {
    const o = err as Record<string, unknown>;
    for (const k of ["message", "detail", "error", "reason", "code"]) {
      if (typeof o[k] === "string" && o[k]) return o[k];
    }
    return JSON.stringify(err);
  }
  return String(err);
}

export function initials(nameOrEmail: string | null | undefined): string {
  const s = (nameOrEmail ?? "?").trim();
  const base = s.includes("@") ? s.split("@")[0]! : s;
  const parts = base.split(/[\s._-]+/).filter(Boolean);
  const out = (parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "");
  return out.toUpperCase();
}

/** "Chrome on Windows" from a User-Agent string. */
export function describeAgent(ua: string | null): { label: string; mobile: boolean } {
  if (!ua) return { label: "Unknown device", mobile: false };
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /Firefox\//.test(ua)
      ? "Firefox"
      : /Chrome\//.test(ua)
        ? "Chrome"
        : /Safari\//.test(ua)
          ? "Safari"
          : /curl|python|httpx/i.test(ua)
            ? "Script"
            : "Browser";
  const os = /Windows/.test(ua)
    ? "Windows"
    : /Android/.test(ua)
      ? "Android"
      : /iPhone|iPad/.test(ua)
        ? "iOS"
        : /Mac OS X/.test(ua)
          ? "macOS"
          : /Linux/.test(ua)
            ? "Linux"
            : "";
  return { label: os ? `${browser} on ${os}` : browser, mobile: /Mobile|Android|iPhone/.test(ua) };
}
