import { Moon, RotateCw, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { SLEEPING_MESSAGE, probeBackend, type BackendState } from "@/lib/health";

/** Non-blocking top banner shown when the backend doesn't answer. */
export function SleepingBanner({ timeoutMs = 4000 }: { timeoutMs?: number }) {
  const [state, setState] = useState<BackendState>("unknown");
  const [dismissed, setDismissed] = useState(false);
  const [checking, setChecking] = useState(false);

  const check = useCallback(async () => {
    setChecking(true);
    const s = await probeBackend(timeoutMs);
    setState(s);
    setChecking(false);
  }, [timeoutMs]);

  useEffect(() => {
    let alive = true;
    void probeBackend(timeoutMs).then((s) => {
      if (alive) setState(s);
    });
    return () => {
      alive = false;
    };
  }, [timeoutMs]);

  const show = state === "sleeping" && !dismissed;
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div
          key="sleeping"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden border-b border-warning/30 bg-warning-soft"
        >
          <div role="status" className="mx-auto flex h-9 max-w-screen-2xl items-center gap-2 px-3 text-xs text-fg">
            <Moon className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate">{SLEEPING_MESSAGE}</span>
            <button
              type="button"
              onClick={() => void check()}
              disabled={checking}
              className="inline-flex h-6 items-center gap-1 rounded-md px-2 font-medium text-fg-muted transition-colors hover:bg-warning/10 hover:text-fg disabled:opacity-60"
            >
              <RotateCw className={checking ? "size-3 animate-spin" : "size-3"} aria-hidden="true" />
              Retry
            </button>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => setDismissed(true)}
              className="grid size-6 place-items-center rounded-md text-fg-subtle transition-colors hover:bg-warning/10 hover:text-fg"
            >
              <X className="size-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
