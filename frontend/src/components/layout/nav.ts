import {
  ClipboardCheck,
  FolderGit2,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Search,
  Settings,
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
}

export const WORKSPACE_NAV: NavItem[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard, path: (ws) => `/w/${ws}`, access: "all", end: true },
  { key: "repos", label: "Repositories", icon: FolderGit2, path: (ws) => `/w/${ws}/repos`, access: "all" },
  { key: "search", label: "Search", icon: Search, path: (ws) => `/w/${ws}/search`, access: "all" },
  { key: "chat", label: "Chat", icon: MessageSquare, path: (ws) => `/w/${ws}/chat`, access: "all" },
  { key: "jobs", label: "Jobs", icon: ListChecks, path: (ws) => `/w/${ws}/jobs`, access: "member" },
  { key: "review", label: "Review", icon: ClipboardCheck, path: (ws) => `/w/${ws}/review`, access: "admin" },
  { key: "members", label: "Members", icon: Users, path: (ws) => `/w/${ws}/members`, access: "member" },
  { key: "settings", label: "Settings", icon: Settings, path: (ws) => `/w/${ws}/settings`, access: "admin" },
];

export function canSee(access: Access, role: "admin" | "member" | null | undefined): boolean {
  if (access === "all") return true;
  if (access === "member") return role === "admin" || role === "member";
  return role === "admin";
}
