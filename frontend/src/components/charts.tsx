// Small dependency-free charts for Insights. One hue (accent) for magnitude, text stays in text tokens,
// thin marks with 4px rounded data-ends and 2px gaps, hover tooltip on every mark, aria summary for screen readers.
import { animate, motion, useMotionValue, useTransform } from "motion/react";
import { useEffect, type ReactNode } from "react";
import { Tooltip } from "@/components/ui";
import { cn } from "@/lib/cn";

export interface ColumnDatum {
  key: string;
  label: string;
  value: number;
  tip?: ReactNode;
}

/** Vertical columns anchored to a baseline (e.g. commits per week). */
export function ColumnChart({
  data,
  height = 120,
  ariaLabel,
  xLabels = [],
}: {
  data: ColumnDatum[];
  height?: number;
  ariaLabel: string;
  /** Indexes that get an x-axis label (keep it sparse). */
  xLabels?: number[];
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure aria-label={ariaLabel} className="w-full">
      <div className="relative pr-7">
        <div className="relative flex items-end gap-[2px]" style={{ height }}>
          {/* recessive gridlines at 50 % and 100 %, values in the right gutter */}
          {[0.5, 1].map((g) => (
            <div
              key={g}
              className="pointer-events-none absolute inset-x-0 border-t border-dashed border-border/70"
              style={{ bottom: `${g * 100}%` }}
            >
              <span className="tabular absolute -right-7 -top-1.5 w-6 text-left text-[10px] leading-none text-fg-subtle">
                {Math.round(max * g)}
              </span>
            </div>
          ))}
          {data.map((d, i) => (
            <Tooltip key={d.key} content={d.tip ?? `${d.label}: ${d.value}`}>
              <div className="group relative flex h-full flex-1 cursor-default items-end">
                <motion.div
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{
                    duration: 0.5,
                    delay: i * 0.015,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  style={{
                    height: d.value ? `${(d.value / max) * 100}%` : 2,
                    transformOrigin: "bottom",
                  }}
                  className={cn(
                    "w-full rounded-t-[4px] transition-colors",
                    d.value
                      ? "bg-accent/80 group-hover:bg-accent"
                      : "bg-border",
                  )}
                />
              </div>
            </Tooltip>
          ))}
        </div>
        <div className="relative mt-1.5 h-4 border-t border-border">
          {xLabels.map((i) =>
            data[i] ? (
              <span
                key={i}
                className="absolute top-1 whitespace-nowrap text-[10px] text-fg-subtle"
                style={{
                  left: `${((i + 0.5) / data.length) * 100}%`,
                  transform:
                    i === 0
                      ? "translateX(-25%)"
                      : i === data.length - 1
                        ? "translateX(-75%)"
                        : "translateX(-50%)",
                }}
              >
                {data[i].label}
              </span>
            ) : null,
          )}
        </div>
      </div>
      <figcaption className="sr-only">
        {data.map((d) => `${d.label}: ${d.value}`).join(", ")}
      </figcaption>
    </figure>
  );
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** 7 × 24 activity grid (UTC). Sequential single hue: more commits = stronger accent. */
export function Heatmap({
  cells,
}: {
  cells: { weekday: number; hour: number; commits: number }[];
}) {
  const grid = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c.commits]));
  const max = Math.max(1, ...cells.map((c) => c.commits));
  return (
    <figure
      aria-label="Commits by weekday and hour (UTC)"
      className="overflow-x-auto"
    >
      <div className="inline-grid min-w-full grid-cols-[2rem_repeat(24,minmax(10px,1fr))] gap-[2px]">
        {DAYS.map((day, d) => (
          <Row key={day} label={day}>
            {Array.from({ length: 24 }, (_, h) => {
              const n = grid.get(`${d}-${h}`) ?? 0;
              return (
                <Tooltip
                  key={h}
                  content={`${day} ${String(h).padStart(2, "0")}:00 UTC · ${n} commit${n === 1 ? "" : "s"}`}
                >
                  <motion.span
                    initial={{ opacity: 0, scale: 0.6 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, delay: (d * 24 + h) * 0.002 }}
                    className="block aspect-square rounded-[3px]"
                    style={{
                      background: n
                        ? `color-mix(in srgb, var(--accent) ${Math.round(18 + (n / max) * 82)}%, var(--surface-2))`
                        : "var(--surface-2)",
                    }}
                  />
                </Tooltip>
              );
            })}
          </Row>
        ))}
        <span />
        {Array.from({ length: 24 }, (_, h) => (
          <span key={h} className="text-center text-[9px] text-fg-subtle">
            {h % 6 === 0 ? h : ""}
          </span>
        ))}
      </div>
    </figure>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span className="self-center text-[10px] text-fg-subtle">{label}</span>
      {children}
    </>
  );
}

/** Horizontal bars with the label + value in text ink (languages, hot files, PR authors). */
export function BarList({
  items,
  format = (n) => n.toLocaleString(),
  mono = false,
}: {
  items: {
    key: string;
    label: ReactNode;
    value: number;
    sub?: ReactNode;
    tip?: ReactNode;
  }[];
  format?: (n: number) => string;
  mono?: boolean;
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((it, i) => (
        <li key={it.key}>
          <Tooltip
            content={
              it.tip ??
              `${typeof it.label === "string" ? it.label : ""} ${format(it.value)}`
            }
          >
            <div className="group relative flex h-7 items-center overflow-hidden rounded-md">
              <motion.span
                initial={{ width: 0 }}
                animate={{ width: `${(it.value / max) * 100}%` }}
                transition={{
                  duration: 0.55,
                  delay: i * 0.04,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className="absolute inset-y-0 left-0 rounded-md bg-accent/15 transition-colors group-hover:bg-accent/25"
              />
              <span
                className={cn(
                  "relative min-w-0 flex-1 truncate px-2 text-xs text-fg",
                  mono && "font-mono",
                )}
              >
                {it.label}
              </span>
              {it.sub && (
                <span className="relative mr-2 shrink-0 text-2xs text-fg-subtle">
                  {it.sub}
                </span>
              )}
              <span className="tabular relative shrink-0 pr-2 text-xs font-medium text-fg-muted">
                {format(it.value)}
              </span>
            </div>
          </Tooltip>
        </li>
      ))}
    </ul>
  );
}

/** Radial score 0-100 (one value, so a ring + hero number, not a chart). */
export function ScoreRing({
  score,
  size = 76,
  label,
}: {
  score: number;
  size?: number;
  label: ReactNode;
}) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const tone =
    score >= 85
      ? "var(--success)"
      : score >= 70
        ? "var(--accent)"
        : score >= 50
          ? "var(--warning)"
          : "var(--danger)";
  return (
    <div
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth={6}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - score / 100) }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute text-center leading-none">
        <div className="tabular text-xl font-semibold">
          <CountUp value={score} />
        </div>
        <div className="mt-0.5 text-[10px] text-fg-subtle">{label}</div>
      </div>
    </div>
  );
}

/** Number that counts up on mount (no in-view wait: hidden tabs never fire IntersectionObserver). */
export function CountUp({
  value,
  format = (n: number) => Math.round(n).toLocaleString(),
}: {
  value: number;
  format?: (n: number) => string;
}) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => format(v));
  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [mv, value]);
  return <motion.span aria-label={format(value)}>{text}</motion.span>;
}
