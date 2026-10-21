import { Monitor, Moon, Sun } from "lucide-react";
import { motion } from "motion/react";
import { IconButton, Tooltip } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useThemePref, type ThemePref } from "@/lib/theme";

const OPTIONS: { value: ThemePref; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

/** One-click toggle for the top bar: light ⇄ dark (System stays available in the account menu). */
export function ThemeToggleButton() {
  const [pref, setPref] = useThemePref();
  const isDark =
    pref === "dark" || (pref === "system" && typeof window !== "undefined" && document.documentElement.dataset.theme === "dark");
  return (
    <Tooltip content={isDark ? "Light mode" : "Dark mode"}>
      <IconButton
        label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        onClick={() => setPref(isDark ? "light" : "dark")}
        icon={
          <motion.span key={isDark ? "moon" : "sun"} initial={{ rotate: -90, scale: 0.6, opacity: 0 }} animate={{ rotate: 0, scale: 1, opacity: 1 }} transition={{ duration: 0.25 }} className="grid place-items-center">
            {isDark ? <Moon /> : <Sun />}
          </motion.span>
        }
      />
    </Tooltip>
  );
}

/** Segmented Light / Dark / System control (account menu + Account page). */
export function ThemeSegmented({ className }: { className?: string }) {
  const [pref, setPref] = useThemePref();
  return (
    <div role="radiogroup" aria-label="Theme" className={cn("relative flex rounded-md bg-surface-2 p-0.5", className)}>
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const on = pref === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={on}
            aria-label={label}
            title={label}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setPref(value);
            }}
            className={cn(
              "relative z-10 grid h-6 flex-1 place-items-center rounded px-2 text-fg-muted outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
              on && "text-fg",
            )}
          >
            {on && (
              <motion.span layoutId="theme-pill" className="absolute inset-0 -z-10 rounded bg-surface shadow-xs" transition={{ type: "spring", stiffness: 500, damping: 35 }} />
            )}
            <Icon className="size-3.5" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
