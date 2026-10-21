/** Join class names, skipping falsy values. Components avoid conflicting overrides by design. */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
