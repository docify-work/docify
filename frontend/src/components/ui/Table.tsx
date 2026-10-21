import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Skeleton } from "./Skeleton";
import { InfoTip } from "./Tooltip";

export interface Column<T> {
  key: string;
  header: ReactNode;
  info?: ReactNode;
  cell: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** Tailwind width/visibility classes, e.g. "w-28 hidden md:table-cell". */
  className?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  loading?: boolean;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  /** Max height before the body scrolls (header stays sticky). */
  maxHeight?: string;
  className?: string;
  skeletonRows?: number;
  caption?: string;
}

const alignClass = { left: "text-left", right: "text-right", center: "text-center" } as const;

/** Compact table: sticky header, row hover, skeleton loading, empty state, staggered first paint. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  empty,
  onRowClick,
  maxHeight,
  className,
  skeletonRows = 5,
  caption,
}: DataTableProps<T>) {
  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (onRowClick && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onRowClick(row);
    }
  };
  const showSkeleton = loading && !rows;
  return (
    <div className={cn("overflow-auto", className)} style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full border-separate border-spacing-0 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cn(
                  "sticky top-0 z-[1] h-8 border-b border-border bg-surface-2/80 px-3 text-2xs font-medium uppercase " +
                    "tracking-wide text-fg-subtle backdrop-blur-sm whitespace-nowrap",
                  alignClass[c.align ?? "left"],
                  c.className,
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {c.header}
                  {c.info && <InfoTip>{c.info}</InfoTip>}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={showSkeleton ? undefined : "ui-stagger"}>
          {showSkeleton &&
            Array.from({ length: skeletonRows }, (_, i) => (
              <tr key={`sk-${i}`} aria-hidden="true">
                {columns.map((c, j) => (
                  <td key={c.key} className={cn("h-10 border-b border-border px-3", c.className)}>
                    <Skeleton className="h-3" style={{ width: j === 0 ? "60%" : "45%" }} />
                  </td>
                ))}
              </tr>
            ))}
          {!showSkeleton && rows && rows.length === 0 && (
            <tr>
              <td colSpan={columns.length}>{empty}</td>
            </tr>
          )}
          {!showSkeleton &&
            rows?.map((row, i) => (
              <tr
                key={rowKey(row)}
                style={{ "--i": Math.min(i, 12) } as CSSProperties}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (e) => onKey(e, row) : undefined}
                className={cn(
                  "group transition-colors duration-150 hover:bg-surface-2/70",
                  onRowClick && "cursor-pointer focus-visible:bg-surface-2 focus-visible:outline-none",
                )}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "h-10 border-b border-border px-3 align-middle group-last:border-b-0",
                      alignClass[c.align ?? "left"],
                      c.className,
                    )}
                  >
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
