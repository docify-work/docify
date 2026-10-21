import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type CalloutTone = "info" | "success" | "warning" | "danger";

const tones: Record<CalloutTone, { cls: string; icon: ReactNode }> = {
  info: { cls: "border-info/25 bg-info-soft text-fg", icon: <Info className="text-info" /> },
  success: { cls: "border-success/25 bg-success-soft text-fg", icon: <CheckCircle2 className="text-success" /> },
  warning: { cls: "border-warning/30 bg-warning-soft text-fg", icon: <AlertTriangle className="text-warning" /> },
  danger: { cls: "border-danger/25 bg-danger-soft text-fg", icon: <XCircle className="text-danger" /> },
};

/** Single-line inline message (form errors, notices). Keep text short. */
export function Callout({
  tone = "info",
  children,
  action,
  onDismiss,
  className,
}: {
  tone?: CalloutTone;
  children: ReactNode;
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex animate-rise items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs [&>svg]:size-3.5", tones[tone].cls, className)}
    >
      <span className="shrink-0 [&_svg]:size-3.5">{tones[tone].icon}</span>
      <div className="min-w-0 flex-1 leading-5">{children}</div>
      {action}
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="grid size-5 shrink-0 place-items-center rounded-sm text-fg-subtle transition-colors hover:text-fg"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  );
}
