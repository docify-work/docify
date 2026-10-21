import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" className={cn("ui-skeleton rounded-sm", className ?? "h-3 w-full")} style={style} />;
}

const WIDTHS = ["92%", "78%", "86%", "64%", "88%", "72%"];

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className="h-3" style={{ width: WIDTHS[i % WIDTHS.length] }} />
      ))}
    </div>
  );
}

/** Placeholder for a list/table body. */
export function SkeletonRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("divide-y divide-border", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2.5">
          <Skeleton className="size-4 rounded-full" />
          <Skeleton className="h-3" style={{ width: WIDTHS[i % WIDTHS.length] === "92%" ? "40%" : "28%" }} />
          <Skeleton className="ml-auto h-3 w-16" />
        </div>
      ))}
    </div>
  );
}
