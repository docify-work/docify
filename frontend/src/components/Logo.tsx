import { Link } from "react-router";
import { cn } from "@/lib/cn";

export function LogoMark({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={cn("shrink-0", className)}>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <path d="M10 8h7a7 7 0 0 1 0 14h-7z" fill="none" stroke="#fff" strokeWidth="3" strokeLinejoin="round" />
      <path d="M10 25h12" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ to = "/", collapsed = false }: { to?: string; collapsed?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2 rounded-md font-semibold tracking-tight text-fg" aria-label="Docify home">
      <LogoMark />
      {!collapsed && <span className="text-[15px]">Docify</span>}
    </Link>
  );
}
