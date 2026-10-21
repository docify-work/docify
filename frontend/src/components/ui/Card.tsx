import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { InfoTip } from "./Tooltip";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-border bg-surface shadow-xs", className)} {...rest} />;
}

export interface CardHeaderProps {
  title: ReactNode;
  info?: ReactNode;
  /** Muted inline text after the title (counts etc.). */
  meta?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  className?: string;
}

/** One-line card header: icon · title · ⓘ · meta ……… actions */
export function CardHeader({ title, info, meta, actions, icon, className }: CardHeaderProps) {
  return (
    <div className={cn("flex h-10 items-center gap-2 border-b border-border px-3", className)}>
      {icon && <span className="text-fg-subtle [&_svg]:size-3.5">{icon}</span>}
      <h2 className="truncate text-sm font-semibold">{title}</h2>
      {info && <InfoTip>{info}</InfoTip>}
      {meta != null && <span className="tabular text-xs text-fg-subtle">{meta}</span>}
      {actions && <div className="ml-auto flex items-center gap-1">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-3", className)} {...rest} />;
}

/** Small KPI tile: label + big tabular number. */
export function Stat({ label, value, info, icon }: { label: string; value: ReactNode; info?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="flex items-center gap-3 px-3 py-2.5">
      {icon && (
        <span className="grid size-7 place-items-center rounded-md bg-surface-2 text-fg-muted [&_svg]:size-3.5">{icon}</span>
      )}
      <div className="min-w-0">
        <div className="flex items-center gap-1 text-xs text-fg-subtle">
          {label}
          {info && <InfoTip>{info}</InfoTip>}
        </div>
        <div className="tabular text-lg font-semibold leading-tight">{value}</div>
      </div>
    </Card>
  );
}

/** Settings-style row inside a card: label (+ⓘ) on the left, control on the right. */
export function Row({
  label,
  info,
  children,
  className,
}: {
  label: ReactNode;
  info?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-3 py-2 last:border-b-0", className)}>
      <div className="flex min-w-36 items-center gap-1 text-sm text-fg">
        {label}
        {info && <InfoTip>{info}</InfoTip>}
      </div>
      <div className="ml-auto flex min-w-0 items-center gap-2">{children}</div>
    </div>
  );
}

/** Compact key/value strip (e.g. repo facts). */
export function KeyValues({ items, className }: { items: { label: string; value: ReactNode; info?: ReactNode }[]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4", className)}>
      {items.map((it) => (
        <div key={it.label} className="bg-surface px-3 py-2">
          <dt className="flex items-center gap-1 text-2xs uppercase tracking-wide text-fg-subtle">
            {it.label}
            {it.info && <InfoTip>{it.info}</InfoTip>}
          </dt>
          <dd className="mt-0.5 flex min-w-0 items-center gap-1 truncate text-sm">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
