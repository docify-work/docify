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
import { qk, review, workspaces } from "@/api/endpoints";
import { LogoMark } from "@/components/Logo";
import { ThemeSegmented } from "@/components/ThemeToggle";
import { Avatar, Badge, DropdownMenu, IconButton, MenuItem, MenuLabel, MenuSeparator, Tooltip } from "@/components/ui";
import { useLogout, useMe } from "@/hooks/useMe";
import { cn } from "@/lib/cn";
import { useAppConfig } from "@/lib/config";
import { WORKSPACE_NAV, canSee } from "./nav";

interface SidebarProps {
  slug: string | null;
  collapsed: boolean;
  onToggle?: () => void;
  /** Called after navigating (closes the mobile drawer). */
  onNavigate?: () => void;
}

export function Sidebar({ slug, collapsed, onToggle, onNavigate }: SidebarProps) {
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
  const isDemo = membership?.is_public_demo ?? wsQuery.data?.is_public_demo ?? false;

  const reviewQuery = useQuery({
    queryKey: qk.review(slug ?? ""),
    queryFn: () => review.list(slug!),
    enabled: !!slug && role === "admin",
    staleTime: 30_000,
  });
  const pending = reviewQuery.data?.length ?? 0;

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      <WorkspaceSwitcher slug={slug} name={name} isDemo={isDemo} collapsed={collapsed} onNavigate={onNavigate} />

      {slug && (
        <nav aria-label="Workspace" className="flex flex-col gap-0.5">
          {WORKSPACE_NAV.filter((n) => canSee(n.access, role)).map((n) => {
            const Icon = n.icon;
            const link = (
              <NavLink
                key={n.key}
                to={n.path(slug)}
                end={n.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "relative flex h-8 items-center gap-2.5 rounded-md px-2 text-sm outline-none transition-colors duration-150 " +
                      "focus-visible:ring-2 focus-visible:ring-ring",
                    isActive ? "font-medium text-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
                    collapsed && "justify-center px-0",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-0 rounded-md bg-surface-2 ring-1 ring-border"
                        transition={{ type: "spring", duration: 0.3, bounce: 0.12 }}
                      />
                    )}
                    <Icon className={cn("relative size-4 shrink-0", isActive ? "text-accent-text" : undefined)} aria-hidden="true" />
                    {!collapsed && <span className="relative flex-1 truncate">{n.label}</span>}
                    {n.key === "review" && pending > 0 && (
                      <span
                        className={cn(
                          "tabular relative grid min-w-4 place-items-center rounded-full bg-accent px-1 text-2xs font-semibold text-accent-fg",
                          collapsed && "absolute right-1 top-1 h-3.5 min-w-3.5 text-[9px]",
                        )}
                      >
                        {pending}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
            return collapsed ? (
              <Tooltip key={n.key} content={n.label} side="right">
                {link}
              </Tooltip>
            ) : (
              link
            );
          })}
        </nav>
      )}

      <div className="mt-auto flex flex-col gap-1">
        {onToggle && (
          <div className={cn("flex", collapsed ? "justify-center" : "justify-end")}>
            <IconButton
              size="sm"
              label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              tooltipSide="right"
              icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
              onClick={onToggle}
            />
          </div>
        )}
        <UserMenu collapsed={collapsed} onNavigate={onNavigate} />
      </div>
    </div>
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
                <span className="block truncate text-sm font-semibold leading-tight">{slug ? label : "Docify"}</span>
                {isDemo && <span className="block text-2xs leading-tight text-fg-subtle">Public demo</span>}
              </span>
              <ChevronsUpDown className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
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
              icon={w.slug === slug ? <Check className="text-accent-text" /> : <span className="inline-block size-3.5" />}
              shortcut={w.role === "admin" ? <Shield className="size-3" aria-label="Admin" /> : undefined}
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

function UserMenu({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
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
              <span className="block truncate text-sm font-medium leading-tight">{me.name ?? me.email.split("@")[0]}</span>
              <span className="block truncate text-2xs leading-tight text-fg-subtle">{me.email}</span>
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
