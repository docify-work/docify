import { Check, ChevronRight, Copy } from "lucide-react";
import { Avatar as RA } from "radix-ui";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { cn } from "@/lib/cn";
import { formatDateTime, initials, relativeTime } from "@/lib/format";
import { IconButton } from "./IconButton";
import { InfoTip, Tooltip } from "./Tooltip";

// ------------------------------------------------------------------ PageHeader

/** One-line page header: title · ⓘ · meta ……… actions. */
export function PageHeader({
  title,
  info,
  meta,
  actions,
  icon,
  className,
}: {
  title: ReactNode;
  info?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex min-h-8 flex-wrap items-center gap-x-2 gap-y-2", className)}>
      {icon && <span className="text-fg-subtle [&_svg]:size-4">{icon}</span>}
      <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
      {info && <InfoTip>{info}</InfoTip>}
      {meta != null && <div className="flex items-center gap-2 text-xs text-fg-subtle">{meta}</div>}
      {actions && <div className="ml-auto flex items-center gap-1.5">{actions}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ Avatar

export function Avatar({
  src,
  name,
  size = 24,
  className,
}: {
  src?: string | null;
  name?: string | null;
  size?: number;
  className?: string;
}) {
  return (
    <RA.Root
      className={cn(
        "inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full bg-accent-soft align-middle",
        className,
      )}
      style={{ width: size, height: size }}
    >
      {src && <RA.Image src={src} alt="" referrerPolicy="no-referrer" className="size-full object-cover" />}
      <RA.Fallback
        className="text-accent-text font-semibold"
        style={{ fontSize: Math.max(9, Math.round(size * 0.4)) }}
        delayMs={src ? 300 : 0}
      >
        {initials(name)}
      </RA.Fallback>
    </RA.Root>
  );
}

// ------------------------------------------------------------------ Kbd

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] border border-border bg-surface px-1 " +
          "font-sans text-2xs font-medium text-fg-subtle shadow-[0_1px_0_var(--border)]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

// ------------------------------------------------------------------ Breadcrumbs

export interface Crumb {
  label: ReactNode;
  to?: string;
}

export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <li key={i} className={cn("flex min-w-0 items-center gap-1", !last && "shrink-0")}>
              {c.to && !last ? (
                <Link to={c.to} className="truncate text-fg-muted transition-colors hover:text-fg">
                  {c.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={cn("truncate", last ? "font-medium text-fg" : "text-fg-muted")}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight aria-hidden="true" className="size-3.5 shrink-0 text-fg-subtle" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ------------------------------------------------------------------ CopyButton

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return (
    <IconButton
      size="xs"
      label={copied ? "Copied" : label}
      icon={copied ? <Check className="text-success" /> : <Copy />}
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          window.clearTimeout(timer.current);
          timer.current = window.setTimeout(() => setCopied(false), 1400);
        });
      }}
    />
  );
}

// ------------------------------------------------------------------ RelativeTime

/** "3m ago" with the full timestamp in a tooltip. */
export function RelativeTime({ iso, className }: { iso: string | null | undefined; className?: string }) {
  if (!iso) return <span className={cn("text-fg-subtle", className)}>—</span>;
  return (
    <Tooltip content={formatDateTime(iso)}>
      <time dateTime={iso} className={cn("tabular whitespace-nowrap", className)} tabIndex={-1}>
        {relativeTime(iso)}
      </time>
    </Tooltip>
  );
}

// ------------------------------------------------------------------ TextLink

/** Inline accent link. Internal paths use the router; external URLs open in a new tab. */
export function TextLink({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  const cls = cn("font-medium text-accent-text underline-offset-2 transition-colors hover:underline", className);
  if (/^https?:\/\//i.test(to)) {
    return (
      <a href={to} target="_blank" rel="nofollow noopener noreferrer" className={cls}>
        {children}
      </a>
    );
  }
  return (
    <Link to={to} className={cls}>
      {children}
    </Link>
  );
}
