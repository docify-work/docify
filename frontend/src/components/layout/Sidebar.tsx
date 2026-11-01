import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronsUpDown,
  Eye,
  LogIn,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Shield,
  UserRound,
} from "lucide-react";
import { motion } from "motion/react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { loginUrl } from "@/api/client";
import {
  findings,
  issues as issuesApi,
  qk,
  review,
  workspaces,
} from "@/api/endpoints";
import { LogoMark } from "@/components/Logo";
import { ThemeSegmented, ThemeToggleButton } from "@/components/ThemeToggle";
import {
  Avatar,
  Badge,
  DropdownMenu,
  IconButton,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  Tooltip,
} from "@/components/ui";
import { useLogout, useMe } from "@/hooks/useMe";
import { cn } from "@/lib/cn";
import { useAppConfig } from "@/lib/config";
import { NAV_SECTIONS, canSee, type NavItem } from "./nav";

interface SidebarProps {
  slug: string | null;
  collapsed: boolean;
  onToggle?: () => void;
  /** Called after navigating (closes the mobile drawer). */
  onNavigate?: () => void;
}

export function Sidebar({
  slug,
  collapsed,
  onToggle,
  onNavigate,
}: SidebarProps) {
  const { me } = useMe();
  const membership = me?.workspaces.find((w) => w.slug === slug);
  const wsQuery = useQuery({
    queryKey: qk.workspace(slug ?? ""),
    queryFn: () => workspaces.get(slug!),
    enabled: !!slug && !membership,
    retry: false,
  });
  const role = membership?.role ?? wsQuery.data?.role ?? null;
  const name = membership?.name ?? wsQuery.data?.name ?? null;
  const isDemo =
    membership?.is_public_demo ?? wsQuery.data?.is_public_demo ?? false;

  const reviewQuery = useQuery({
    queryKey: qk.review(slug ?? ""),
    queryFn: () => review.list(slug!),
    enabled: !!slug && role === "admin",
    staleTime: 30_000,
  });
  const findingsQuery = useQuery({
    queryKey: qk.findings(slug ?? "", "badge"),
    queryFn: () => findings.list(slug!, { status: "open", limit: 1 }),
    enabled: !!slug,
    staleTime: 60_000,
  });
  const issuesQuery = useQuery({
    queryKey: qk.issues(slug ?? "", "badge"),
    queryFn: () => issuesApi.list(slug!, { status: "open,in_progress" }),
    enabled: !!slug,
    staleTime: 60_000,
  });
  const counts: Record<string, number> = {
    review: reviewQuery.data?.length ?? 0,
    checks: findingsQuery.data?.counts.open ?? 0,
    issues: issuesQuery.data?.length ?? 0,
  };

  return (
    <div className="flex h-full flex-col gap-3 p-2">
      <div className={cn("flex items-center gap-1", collapsed && "flex-col")}>
        <div className="min-w-0 flex-1">
          <WorkspaceSwitcher
            slug={slug}
            name={name}
            isDemo={isDemo}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        </div>
        {onToggle && (
          <IconButton
            size="sm"
            label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            tooltipSide="right"
            icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            onClick={onToggle}
            className="shrink-0 text-fg-subtle"
          />
        )}
      </div>

      {slug && (
        <nav
          aria-label="Workspace"
          className="-mx-0.5 flex flex-1 flex-col gap-3 overflow-y-auto px-0.5"
        >
          {NAV_SECTIONS.map((section) => {
            const items = section.items.filter((n) => canSee(n.access, role));
            if (!items.length) return null;
            return (
              <div key={section.key} className="flex flex-col gap-0.5">
                {section.label &&
                  (collapsed ? (
                    <div
                      className="mx-2 my-1 h-px bg-border"
                      aria-hidden="true"
                    />
                  ) : (
                    <div className="px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-fg-subtle">
                      {section.label}
                    </div>
                  ))}
                {items.map((n) => (
                  <NavEntry
                    key={n.key}
                    item={n}
                    slug={slug}
                    collapsed={collapsed}
                    count={counts[n.key] ?? 0}
                    onNavigate={onNavigate}
                  />
                ))}
              </div>
            );
          })}
        </nav>
      )}

      <div className="mt-auto flex flex-col gap-1 border-t border-border pt-2">
        {!me && (
          <div
            className={cn(
              "flex items-center justify-between gap-2 px-1",
              collapsed && "justify-center",
            )}
          >
            {!collapsed && (
              <span className="text-xs text-fg-subtle">Theme</span>
            )}
            {collapsed ? (
              <ThemeToggleButton />
            ) : (
              <ThemeSegmented className="w-28" />
            )}
          </div>
        )}
        <UserMenu collapsed={collapsed} onNavigate={onNavigate} />
      </div>
    </div>
  );
}

function NavEntry({
  item: n,
  slug,
  collapsed,
  count,
  onNavigate,
}: {
  item: NavItem;
  slug: string;
  collapsed: boolean;
  count: number;
  onNavigate?: () => void;
}) {
  const Icon = n.icon;
  const link = (
    <NavLink
      to={n.path(slug)}
      end={n.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex h-8 items-center gap-2.5 rounded-lg px-2 text-sm outline-none transition-colors duration-150 " +
            "focus-visible:ring-2 focus-visible:ring-ring",
          isActive
            ? "font-medium text-fg"
            : "text-fg-muted hover:bg-surface-2/70 hover:text-fg",
          collapsed && "justify-center px-0",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-active"
              className="absolute inset-0 rounded-lg bg-accent-soft/70 ring-1 ring-accent/15"
              transition={{ type: "spring", duration: 0.35, bounce: 0.15 }}
            >
              <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-accent" />
            </motion.span>
          )}
          <Icon
            className={cn(
              "relative size-4 shrink-0 transition-transform duration-200 group-hover:scale-110",
              isActive ? "text-accent-text" : undefined,
            )}
            aria-hidden="true"
          />
          {!collapsed && (
            <span className="relative flex-1 truncate">{n.label}</span>
          )}
          {count > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className={cn(
                "tabular grid min-w-4 place-items-center rounded-full px-1 text-2xs font-semibold",
                collapsed ? "absolute right-1 top-0.5 h-3.5 min-w-3.5 px-0.5 text-[9px] leading-none" : "relative",
                n.key === "checks"
                  ? "bg-warning-soft text-warning"
                  : "bg-accent text-accent-fg",
              )}
            >
              {count > 99 ? "99+" : count}
            </motion.span>
          )}
        </>
      )}
    </NavLink>
  );
  return (
    <Tooltip
      content={collapsed ? `${n.label} · ${n.hint}` : n.hint}
      side="right"
    >
      {link}
    </Tooltip>
  );
}

function WorkspaceSwitcher({
  slug,
  name,
  isDemo,
  collapsed,
  onNavigate,
}: {
  slug: string | null;
  name: string | null;
  isDemo: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { me } = useMe();
  const cfg = useAppConfig();
  const navigate = useNavigate();
  const go = (to: string) => {
    navigate(to);
    onNavigate?.();
  };
  const label = name ?? (slug ? slug : "Select workspace");
  const demoSlug = cfg.demoWorkspaceSlug;
  const memberOfDemo = me?.workspaces.some((w) => w.slug === demoSlug);

  return (
    <DropdownMenu
      align="start"
      trigger={
        <button
          type="button"
          aria-label="Switch workspace"
          className={cn(
            "flex h-10 w-full items-center gap-2 rounded-md px-1.5 text-left outline-none transition-colors duration-150 " +
              "hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-surface-2",
            collapsed && "justify-center px-0",
          )}
        >
          {slug ? (
            <span className="grid size-6 shrink-0 place-items-center rounded-md bg-accent text-xs font-semibold text-accent-fg">
              {label.charAt(0).toUpperCase()}
            </span>
          ) : (
            <LogoMark size={24} />
          )}
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold leading-tight">
                  {slug ? label : "Docify"}
                </span>
                {isDemo && (
                  <span className="block text-2xs leading-tight text-fg-subtle">
                    Public demo
                  </span>
                )}
              </span>
              <ChevronsUpDown
                className="size-3.5 shrink-0 text-fg-subtle"
                aria-hidden="true"
              />
            </>
          )}
        </button>
      }
    >
      {me && me.workspaces.length > 0 && (
        <>
          <MenuLabel>Workspaces</MenuLabel>
          {me.workspaces.map((w) => (
            <MenuItem
              key={w.slug}
              onSelect={() => go(`/w/${w.slug}`)}
              icon={
                w.slug === slug ? (
                  <Check className="text-accent-text" />
                ) : (
                  <span className="inline-block size-3.5" />
                )
              }
              shortcut={
                w.role === "admin" ? (
                  <Shield className="size-3" aria-label="Admin" />
                ) : undefined
              }
            >
              {w.name}
            </MenuItem>
          ))}
          <MenuSeparator />
        </>
      )}
      {me && (
        <MenuItem icon={<Plus />} onSelect={() => go("/new")}>
          Create workspace
        </MenuItem>
      )}
      {demoSlug && !memberOfDemo && slug !== demoSlug && (
        <MenuItem icon={<Eye />} onSelect={() => go(`/w/${demoSlug}`)}>
          View demo
        </MenuItem>
      )}
      {!me && (
        <MenuItem icon={<LogIn />} onSelect={() => go("/login")}>
          Sign in
        </MenuItem>
      )}
    </DropdownMenu>
  );
}

function UserMenu({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();

  if (!me) {
    const btn = (
      <NavLink
        to={loginUrl(location.pathname + location.search)}
        onClick={onNavigate}
        className={cn(
          "flex h-8 items-center justify-center gap-2 rounded-md bg-accent px-2 text-sm font-medium text-accent-fg shadow-sm " +
            "transition-colors hover:bg-accent-hover active:scale-[0.98]",
        )}
      >
        <LogIn className="size-4" aria-hidden="true" />
        {!collapsed && "Sign in"}
      </NavLink>
    );
    return collapsed ? (
      <Tooltip content="Sign in" side="right">
        {btn}
      </Tooltip>
    ) : (
      btn
    );
  }

  return (
    <DropdownMenu
      side="top"
      align="start"
      trigger={
        <button
          type="button"
          aria-label="Account menu"
          className={cn(
            "flex h-10 w-full items-center gap-2 rounded-md px-1.5 text-left outline-none transition-colors duration-150 " +
              "hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-surface-2",
            collapsed && "justify-center px-0",
          )}
        >
          <Avatar src={me.avatar_url} name={me.name ?? me.email} size={24} />
          {!collapsed && (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium leading-tight">
                {me.name ?? me.email.split("@")[0]}
              </span>
              <span className="block truncate text-2xs leading-tight text-fg-subtle">
                {me.email}
              </span>
            </span>
          )}
        </button>
      }
    >
      <MenuItem
        icon={<UserRound />}
        onSelect={() => {
          navigate("/account");
          onNavigate?.();
        }}
      >
        Account
      </MenuItem>
      <MenuItem
        icon={<Shield />}
        onSelect={() => {
          navigate("/privacy");
          onNavigate?.();
        }}
      >
        Privacy
      </MenuItem>
      <MenuSeparator />
      <div className="flex items-center justify-between gap-3 px-2 py-1.5 text-sm">
        <span className="text-fg-muted">Theme</span>
        <ThemeSegmented className="w-28" />
      </div>
      <MenuSeparator />
      <MenuItem icon={<LogOut />} onSelect={() => logout.mutate()}>
        Sign out
      </MenuItem>
    </DropdownMenu>
  );
}

export function DemoBadge() {
  return (
    <Badge tone="accent" icon={<Eye />}>
      Demo · read-only
    </Badge>
  );
}
