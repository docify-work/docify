/**
 * The API marks search matches with «…» (plain text). Older responses used <b>…</b>; both are
 * supported. We never inject HTML: split into segments, render matches as <mark>.
 */
export function parseHighlights(snippet: string): { text: string; hit: boolean }[] {
  const out: { text: string; hit: boolean }[] = [];
  let hit = false;
  for (const part of snippet.split(/(<\/?b>|«|»)/i)) {
    if (part === "«" || /^<b>$/i.test(part)) hit = true;
    else if (part === "»" || /^<\/b>$/i.test(part)) hit = false;
    else if (part) out.push({ text: part.replace(/<[^>]*>/g, ""), hit });
  }
  return out;
}
