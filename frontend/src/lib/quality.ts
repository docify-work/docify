import type { FindingStatus, IssueStatus, Severity } from "@/api/types";
import type { Tone } from "@/components/ui";

export const SEVERITIES: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

export const severityTone: Record<Severity, Tone> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "info",
  info: "neutral",
};

export const severityLabel: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const findingStatusLabel: Record<FindingStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
  false_positive: "False positive",
};

export const findingStatusTone: Record<FindingStatus, Tone> = {
  open: "warning",
  acknowledged: "info",
  resolved: "success",
  false_positive: "neutral",
};

export const issueStatusLabel: Record<IssueStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const issueStatusTone: Record<IssueStatus, Tone> = {
  open: "warning",
  in_progress: "info",
  resolved: "success",
  closed: "neutral",
};

export function personLabel(p: {
  login?: string | null;
  name?: string | null;
}): string {
  return p.login ? `@${p.login}` : (p.name ?? "unknown");
}

export function githubAvatar(
  login: string | null | undefined,
  size = 48,
): string | null {
  // CSP allows only avatars.githubusercontent.com (which also serves avatars by username).
  return login
    ? `https://avatars.githubusercontent.com/${encodeURIComponent(login)}?size=${size}`
    : null;
}

export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 7) : "";
}
