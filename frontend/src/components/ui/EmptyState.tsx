import { AlertTriangle, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "@/api/client";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { InfoTip } from "./Tooltip";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  info?: ReactNode;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyState({ icon, title, info, action, className, compact }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex animate-rise flex-col items-center justify-center gap-2 text-center",
        compact ? "px-4 py-6" : "px-6 py-12",
        className,
      )}
    >
      {icon && (
        <span className="grid size-9 place-items-center rounded-lg border border-border bg-surface-2 text-fg-subtle [&_svg]:size-4">
          {icon}
        </span>
      )}
      <div className="flex items-center gap-1 text-sm font-medium text-fg">
        {title}
        {info && <InfoTip>{info}</InfoTip>}
      </div>
      {action && <div className="mt-1 flex items-center gap-2">{action}</div>}
    </div>
  );
}

/** Consistent error block for failed queries. */
export function ErrorState({
  error,
  onRetry,
  className,
  compact,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}) {
  return (
    <EmptyState
      compact={compact}
      className={className}
      icon={<AlertTriangle className="text-danger" />}
      title={<span role="alert">{errorMessage(error)}</span>}
      action={
        onRetry && (
          <Button size="sm" icon={<RotateCw />} onClick={onRetry}>
            Retry
          </Button>
        )
      }
    />
  );
}
