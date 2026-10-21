import { motion } from "motion/react";
import { Suspense, type ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router";
import { Logo } from "@/components/Logo";
import { Button, PageSpinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { useAppConfig } from "@/lib/config";

/** Marketing/auth layout: slim header, centered content, tiny footer. */
export function PublicLayout() {
  const { me } = useMe();
  const cfg = useAppConfig();
  const location = useLocation();
  const onAuthPage = /^\/(login|signup)/.test(location.pathname);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-12 max-w-5xl items-center gap-2 px-4">
          <Logo />
          <div className="ml-auto flex items-center gap-1.5">
            {cfg.demoWorkspaceSlug && (
              <Button asChild variant="ghost" size="sm">
                <Link to={`/w/${cfg.demoWorkspaceSlug}`}>View demo</Link>
              </Button>
            )}
            {me ? (
              <Button asChild variant="primary" size="sm">
                <Link to="/app">Open app</Link>
              </Button>
            ) : (
              !onAuthPage && (
                <Button asChild variant="secondary" size="sm">
                  <Link to="/login">Sign in</Link>
                </Button>
              )
            )}
          </div>
        </div>
      </header>
      <main id="main" className="flex flex-1 flex-col">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-1 flex-col"
        >
          <Suspense fallback={<PageSpinner />}>
            <Outlet />
          </Suspense>
        </motion.div>
      </main>
      <footer className="mx-auto flex h-10 w-full max-w-5xl items-center gap-3 px-4 text-2xs text-fg-subtle">
        <span>© Docify</span>
        <Link to="/privacy" className="hover:text-fg-muted">
          Privacy
        </Link>
        <span className="ml-auto tabular" title="Build">
          {cfg.env} · {cfg.version}
        </span>
      </footer>
    </div>
  );
}

/** Centered narrow card used by all auth pages. */
export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-1 items-start justify-center px-4 pb-10 pt-[8vh]">
      <div className="w-full max-w-[360px]">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-fg-muted">{subtitle}</div>}
        <div className="mt-5 rounded-xl border border-border bg-surface p-5 shadow-sm">{children}</div>
      </div>
    </div>
  );
}
