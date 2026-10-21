import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router";
import { cn } from "@/lib/cn";

/** Divided list with staggered first paint. */
export function List({ children, className, label }: { children: ReactNode; className?: string; label?: string }) {
  return (
    <ul aria-label={label} className={cn("ui-stagger divide-y divide-border", className)}>
      {children}
    </ul>
  );
}

export interface ListItemProps {
  /** Internal route; makes the whole row a link. */
  to?: string;
  /** External URL (opens in a new tab). */
  href?: string;
  icon?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Right-aligned compact metadata (badges, time). */
  meta?: ReactNode;
  /** Right-aligned buttons (not part of the link). */
  actions?: ReactNode;
  index?: number;
  className?: string;
}

export function ListItem({ to, href, icon, title, subtitle, meta, actions, index = 0, className }: ListItemProps) {
  const body = (
    <>
      {icon && <span className="shrink-0 text-fg-subtle [&_svg]:size-4">{icon}</span>}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-fg">{title}</span>
        {subtitle && <span className="block truncate text-xs text-fg-subtle">{subtitle}</span>}
      </span>
      {meta && <span className="flex shrink-0 items-center gap-2 text-xs text-fg-subtle">{meta}</span>}
    </>
  );
  const rowCls =
    "flex min-w-0 flex-1 items-center gap-3 px-3 py-2 outline-none transition-colors duration-150 focus-visible:bg-surface-2";
  return (
    <li
      style={{ "--i": Math.min(index, 12) } as CSSProperties}
      className={cn("group flex items-center transition-colors duration-150 hover:bg-surface-2/70", className)}
    >
      {to ? (
        <Link to={to} className={rowCls}>
          {body}
        </Link>
      ) : href ? (
        <a href={href} target="_blank" rel="nofollow noopener noreferrer" className={rowCls}>
          {body}
        </a>
      ) : (
        <div className={rowCls}>{body}</div>
      )}
      {actions && <div className="flex shrink-0 items-center gap-1 pr-2">{actions}</div>}
    </li>
  );
}
