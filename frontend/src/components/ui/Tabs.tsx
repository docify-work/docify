import { motion } from "motion/react";
import { Tabs as RTabs } from "radix-ui";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem<V extends string> {
  value: V;
  label: ReactNode;
  icon?: ReactNode;
  count?: number;
  disabled?: boolean;
}

/**
 * Segmented tab bar with an animated active indicator. Controlled; the page renders the panel.
 * `variant="pills"` = segmented control (filters/scopes), `"underline"` = section tabs.
 */
export function Tabs<V extends string>({
  value,
  onValueChange,
  items,
  variant = "pills",
  className,
  ariaLabel,
}: {
  value: V;
  onValueChange: (value: V) => void;
  items: TabItem<V>[];
  variant?: "pills" | "underline";
  className?: string;
  ariaLabel?: string;
}) {
  const layoutId = useId();
  return (
    <RTabs.Root value={value} onValueChange={(v) => onValueChange(v as V)} activationMode="manual">
      <RTabs.List
        aria-label={ariaLabel}
        className={cn(
          "inline-flex items-center",
          variant === "pills" ? "gap-0.5 rounded-md border border-border bg-surface-2 p-0.5" : "gap-3 border-b border-border",
          className,
        )}
      >
        {items.map((it) => {
          const active = it.value === value;
          return (
            <RTabs.Trigger
              key={it.value}
              value={it.value}
              disabled={it.disabled}
              className={cn(
                "relative inline-flex select-none items-center gap-1.5 whitespace-nowrap text-xs font-medium outline-none " +
                  "transition-colors duration-150 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-ring [&_svg]:size-3.5",
                variant === "pills" ? "h-6 rounded-[5px] px-2.5" : "h-8 px-0.5",
                active ? "text-fg" : "text-fg-muted hover:text-fg",
              )}
            >
              {active && (
                <motion.span
                  layoutId={layoutId}
                  transition={{ type: "spring", duration: 0.28, bounce: 0.12 }}
                  className={cn(
                    "absolute",
                    variant === "pills"
                      ? "inset-0 rounded-[5px] bg-surface shadow-sm ring-1 ring-border"
                      : "inset-x-0 -bottom-px h-0.5 rounded-full bg-accent",
                  )}
                />
              )}
              <span className="relative inline-flex items-center gap-1.5">
                {it.icon}
                {it.label}
                {it.count != null && <span className="tabular text-2xs text-fg-subtle">{it.count}</span>}
              </span>
            </RTabs.Trigger>
          );
        })}
      </RTabs.List>
    </RTabs.Root>
  );
}
