import {
  BarChart3,
  Bug,
  ClipboardCheck,
  FolderGit2,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Search,
  Settings,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

export type Access = "all" | "member" | "admin";

export interface NavItem {
  key: string;
  label: string;
  icon: LucideIcon;
  path: (ws: string) => string;
  access: Access;
  /** Exact match for active state (dashboard). */
  end?: boolean;
  /** One-line hint shown as a tooltip (collapsed sidebar + command palette). */
  hint: string;
}

export interface NavSection {
  key: string;
  label: string | null;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    key: "main",
    label: null,
    items: [
      {
        key: "overview",
        label: "Overview",
        icon: LayoutDashboard,
        path: (ws) => `/w/${ws}`,
        access: "all",
        end: true,
        hint: "Workspace home",
      },
    ],
  },
  {
    key: "knowledge",
    label: "Knowledge",
    items: [
      {
        key: "repos",
        label: "Repositories",
        icon: FolderGit2,
        path: (ws) => `/w/${ws}/repos`,
        access: "all",
        hint: "Connected repos and their docs",
      },
      {
        key: "search",
        label: "Search",
        icon: Search,
        path: (ws) => `/w/${ws}/search`,
        access: "all",
        hint: "Search code and docs",
      },
      {
        key: "chat",
        label: "Chat",
        icon: MessageSquare,
        path: (ws) => `/w/${ws}/chat`,
        access: "all",
        hint: "Ask about the code",
      },
    ],
  },
  {
    key: "health",
    label: "Code health",
    items: [
      {
        key: "insights",
        label: "Insights",
        icon: BarChart3,
        path: (ws) => `/w/${ws}/insights`,
        access: "all",
        hint: "Contributors, activity and repo health",
      },
      {
        key: "checks",
        label: "Checks",
        icon: ShieldCheck,
        path: (ws) => `/w/${ws}/checks`,
        access: "all",
        hint: "Policy findings on every push",
      },
      {
        key: "issues",
        label: "Issues",
        icon: Bug,
        path: (ws) => `/w/${ws}/issues`,
        access: "all",
        hint: "Bugs and who should fix them",
      },
    ],
  },
  {
    key: "workspace",
    label: "Workspace",
    items: [
      {
        key: "jobs",
        label: "Jobs",
        icon: ListChecks,
        path: (ws) => `/w/${ws}/jobs`,
        access: "member",
        hint: "Background indexing jobs",
      },
      {
        key: "review",
        label: "Review",
        icon: ClipboardCheck,
        path: (ws) => `/w/${ws}/review`,
        access: "admin",
        hint: "Docs waiting for approval",
      },
      {
        key: "members",
        label: "Members",
        icon: Users,
        path: (ws) => `/w/${ws}/members`,
        access: "member",
        hint: "People and invites",
      },
      {
        key: "settings",
        label: "Settings",
        icon: Settings,
        path: (ws) => `/w/${ws}/settings`,
        access: "admin",
        hint: "Workspace settings",
      },
    ],
  },
];

/** Flat list (command palette, tests). */
export const WORKSPACE_NAV: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

export function canSee(
  access: Access,
  role: "admin" | "member" | null | undefined,
): boolean {
  if (access === "all") return true;
  if (access === "member") return role === "admin" || role === "member";
  return role === "admin";
}
