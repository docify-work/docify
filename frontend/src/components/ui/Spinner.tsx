import { cn } from "@/lib/cn";

export function Spinner({ size = 14, className, label }: { size?: number; className?: string; label?: string }) {
  return (
    <span role={label ? "status" : undefined} className={cn("inline-flex shrink-0", className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 16 16"
        fill="none"
        aria-hidden="true"
        className="animate-spin"
      >
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2" />
        <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      {label && <span className="sr-only">{label}</span>}
    </span>
  );
}

/** Centered spinner for whole-page/section loading. */
export function PageSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="grid min-h-40 place-items-center text-fg-subtle animate-fade-in">
      <Spinner size={18} label={label} />
    </div>
  );
}
