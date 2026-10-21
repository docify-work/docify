import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { ToastContext, type ToastApi, type ToastInput } from "./toast-context";
import { cn } from "@/lib/cn";

interface ToastItem extends ToastInput {
  id: number;
}

const icons: Record<NonNullable<ToastInput["tone"]>, ReactNode> = {
  success: <CheckCircle2 className="text-success" />,
  error: <XCircle className="text-danger" />,
  info: <Info className="text-info" />,
  warning: <AlertTriangle className="text-warning" />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);

  const toast = useCallback(
    (t: ToastInput) => {
      const id = nextId.current++;
      setItems((xs) => [...xs.slice(-3), { ...t, id }]);
      const duration = t.duration ?? (t.tone === "error" ? 6000 : 4000);
      if (duration > 0) window.setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      toast,
      dismiss,
      success: (title, description) => toast({ title, description, tone: "success" }),
      error: (title, description) => toast({ title, description, tone: "error" }),
    }),
    [toast, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-relevant="additions"
        className="pointer-events-none fixed bottom-3 right-3 z-[60] flex w-[min(360px,calc(100vw-1.5rem))] flex-col gap-2"
      >
        <AnimatePresence initial={false}>
          {items.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 24, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, transition: { duration: 0.14 } }}
              transition={{ type: "spring", duration: 0.3, bounce: 0.1 }}
              role={t.tone === "error" ? "alert" : "status"}
              className={cn(
                "pointer-events-auto flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3 py-2.5 shadow-lg",
              )}
            >
              <span className="mt-0.5 [&_svg]:size-4">{icons[t.tone ?? "info"]}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-5">{t.title}</p>
                {t.description && <p className="mt-0.5 text-xs text-fg-muted">{t.description}</p>}
              </div>
              <button
                type="button"
                aria-label="Dismiss"
                onClick={() => dismiss(t.id)}
                className="-mr-1 grid size-6 place-items-center rounded-md text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
