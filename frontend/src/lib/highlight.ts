/**
 * Postgres `ts_headline` marks matches with <b>…</b>. We never inject HTML: split into text
 * segments, render matches as <mark>, and drop any other tag-looking text.
 */
export function parseHighlights(snippet: string): { text: string; hit: boolean }[] {
  const out: { text: string; hit: boolean }[] = [];
  let hit = false;
  for (const part of snippet.split(/(<\/?b>)/i)) {
    if (/^<b>$/i.test(part)) hit = true;
    else if (/^<\/b>$/i.test(part)) hit = false;
    else if (part) out.push({ text: part.replace(/<[^>]*>/g, ""), hit });
  }
  return out;
}
