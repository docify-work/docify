import type { ChatSource } from "@/api/types";

export const CITE_TITLE = "docify-cite";

/**
 * Only http(s) and relative URLs survive (Master Doc §5.1). Everything else (javascript:, data:,
 * mailto:, vbscript: …) becomes "" and the link renders as plain text.
 */
export function safeUrl(url: string): string {
  const u = url.trim();
  if (/^https?:\/\//i.test(u)) return u;
  // Relative: no scheme. (A colon before any / ? # means a scheme.)
  if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return "";
  if (u.startsWith("//")) return ""; // protocol-relative → treat as external of unknown scheme
  return u;
}

export function isExternal(href: string): boolean {
  if (!/^https?:\/\//i.test(href)) return false;
  try {
    return new URL(href).origin !== window.location.origin;
  } catch {
    return true;
  }
}

/**
 * Turns chat citation markers `[n]` into links to source n (skipping fenced code blocks).
 * `[n](…)` already-links are left alone.
 */
export function linkCitations(text: string, sources: ChatSource[] | null | undefined): string {
  if (!sources?.length) return text;
  const byN = new Map(sources.map((s) => [s.n, s.url]));
  return text
    .split(/(```[\s\S]*?```)/g)
    .map((part) =>
      part.startsWith("```")
        ? part
        : part.replace(/\[(\d{1,2})\](?!\()/g, (m, n: string) => {
            const url = byN.get(Number(n));
            return url ? `[${n}](${url} "${CITE_TITLE}")` : m;
          }),
    )
    .join("");
}
