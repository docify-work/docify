import {
  AlertOctagon,
  Ban,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock,
  FileWarning,
  Inbox,
  Loader2,
  PauseCircle,
  PlugZap,
  Wallet,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Tooltip } from "./Tooltip";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-fg-muted ring-border",
  accent: "bg-accent-soft text-accent-text ring-accent/20",
  success: "bg-success-soft text-success ring-success/20",
  warning: "bg-warning-soft text-warning ring-warning/25",
  danger: "bg-danger-soft text-danger ring-danger/20",
  info: "bg-info-soft text-info ring-info/20",
};

export function Badge({
  tone = "neutral",
  icon,
  children,
  className,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-sm px-1.5 text-2xs font-medium ring-1 ring-inset whitespace-nowrap [&_svg]:size-3",
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

interface StatusDef {
  tone: Tone;
  icon: ReactNode;
  label: string;
  hint: string;
}

const spin = <Loader2 className="animate-spin" />;

const STATUS: Record<string, StatusDef> = {
  // repositories
  pending: { tone: "neutral", icon: <Clock />, label: "Pending", hint: "Waiting for the first index." },
  indexing: { tone: "info", icon: spin, label: "Indexing", hint: "Reading code and generating docs." },
  ready: { tone: "success", icon: <CheckCircle2 />, label: "Ready", hint: "Indexed and up to date." },
  error: { tone: "danger", icon: <XCircle />, label: "Error", hint: "The last run failed. See Jobs for details." },
  empty: { tone: "neutral", icon: <Inbox />, label: "Empty", hint: "No indexable files found." },
  too_large: { tone: "warning", icon: <FileWarning />, label: "Too large", hint: "Over the size limits for indexing." },
  disconnected: { tone: "neutral", icon: <PlugZap />, label: "Disconnected", hint: "Removed or no longer accessible." },
  suspended: { tone: "warning", icon: <PauseCircle />, label: "Suspended", hint: "The GitHub App installation is suspended." },
  // jobs
  queued: { tone: "neutral", icon: <CircleDashed />, label: "Queued", hint: "Waiting for a worker." },
  running: { tone: "info", icon: spin, label: "Running", hint: "A worker is processing this job." },
  succeeded: { tone: "success", icon: <CheckCircle2 />, label: "Succeeded", hint: "Finished successfully." },
  failed: { tone: "danger", icon: <XCircle />, label: "Failed", hint: "Failed; will retry automatically if attempts remain." },
  dead: { tone: "danger", icon: <AlertOctagon />, label: "Dead", hint: "Out of retries. An admin can retry it manually." },
  blocked_budget: { tone: "warning", icon: <Wallet />, label: "Over budget", hint: "Paused until the AI budget resets." },
  // doc versions / review
  published: { tone: "success", icon: <CheckCircle2 />, label: "Published", hint: "Visible to everyone in the workspace." },
  pending_review: { tone: "warning", icon: <Clock />, label: "In review", hint: "Waiting for an admin to approve." },
  rejected: { tone: "neutral", icon: <Ban />, label: "Rejected", hint: "Rejected by an admin." },
  superseded: { tone: "neutral", icon: <CircleSlash />, label: "Superseded", hint: "Replaced by a newer version." },
};

/** Colour + icon status pill for repo / job / version statuses, with a hint tooltip. */
export function StatusPill({ status, hint, className }: { status: string; hint?: string | null; className?: string }) {
  const def = STATUS[status] ?? { tone: "neutral" as Tone, icon: <CircleDashed />, label: status, hint: "" };
  return (
    <Tooltip content={hint || def.hint || null}>
      <span className="inline-flex" tabIndex={0}>
        <Badge tone={def.tone} icon={def.icon} className={className}>
          {def.label}
        </Badge>
      </span>
    </Tooltip>
  );
}
