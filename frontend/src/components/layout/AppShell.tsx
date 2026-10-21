import { Menu, Search } from "lucide-react";
import { motion } from "motion/react";
import { Suspense, useCallback, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useMatch } from "react-router";
import { Breadcrumbs, Drawer, IconButton, Kbd, PageSpinner } from "@/components/ui";
import { ShellContext, type MetaCrumb } from "@/hooks/usePageMeta";
import { lastWorkspace } from "@/hooks/useWorkspace";
import { cn } from "@/lib/cn";
import { useCommandShortcut } from "@/hooks/useCommandShortcut";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";

const COLLAPSE_KEY = "docify.sidebarCollapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Signed-in / workspace layout: slim collapsible sidebar + compact top bar with breadcrumbs and ⌘K. */
export function AppShell() {
  const match = useMatch("/w/:ws/*");
  const slug = match?.params.ws ?? lastWorkspace();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [crumbs, setCrumbs] = useState<MetaCrumb[]>([]);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  };
  const togglePalette = useCallback(() => setPaletteOpen((o) => !o), []);
  useCommandShortcut(togglePalette);

  const shell = useMemo(() => ({ setCrumbs }), []);
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

  return (
    <ShellContext.Provider value={shell}>
      <div className="flex min-h-0 flex-1">
        <aside
          className={cn(
            "sticky top-0 hidden h-dvh shrink-0 border-r border-border bg-surface transition-[width] duration-200 ease-out md:block",
            collapsed ? "w-14" : "w-56",
          )}
        >
          <Sidebar slug={slug} collapsed={collapsed} onToggle={toggleCollapsed} />
        </aside>

        <Drawer open={mobileOpen} onOpenChange={setMobileOpen} title="Navigation" side="left" bare className="w-64">
          <Sidebar slug={slug} collapsed={false} onNavigate={() => setMobileOpen(false)} />
        </Drawer>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-12 shrink-0 items-center gap-2 border-b border-border bg-canvas/85 px-3 backdrop-blur-md md:px-5">
            <IconButton className="md:hidden" label="Open navigation" icon={<Menu />} onClick={() => setMobileOpen(true)} />
            <Breadcrumbs items={crumbs} className="flex-1" />
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className={
                "flex h-7 w-8 items-center gap-2 rounded-md border border-border bg-surface px-2 text-xs text-fg-subtle shadow-xs " +
                "transition-colors hover:border-border-strong hover:text-fg-muted sm:w-56"
              }
              aria-label="Open command palette"
            >
              <Search className="size-3.5 shrink-0" aria-hidden="true" />
              <span className="hidden flex-1 text-left sm:inline">Search or jump to…</span>
              <span className="hidden items-center gap-0.5 sm:flex">
                <Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd>
                <Kbd>K</Kbd>
              </span>
            </button>
          </header>

          <main id="main" className="min-w-0 flex-1">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto w-full max-w-6xl px-4 py-5 md:px-6"
            >
              <Suspense fallback={<PageSpinner />}>
                <Outlet />
              </Suspense>
            </motion.div>
          </main>
          <footer className="flex h-9 items-center justify-end gap-3 px-6 text-2xs text-fg-subtle">
            <Link to="/privacy" className="hover:text-fg-muted">
              Privacy
            </Link>
          </footer>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} slug={slug} />
    </ShellContext.Provider>
  );
}
