import { createContext, useContext } from "react";
import type { Workspace } from "@/api/types";

export interface WorkspaceCtx {
  ws: Workspace;
  slug: string;
  /** Workspace admin. */
  isAdmin: boolean;
  /** Signed-in member (admin or member). False for anonymous demo visitors. */
  isMember: boolean;
  /** Anonymous visitor (public demo). */
  isAnonymous: boolean;
}

export const WorkspaceContext = createContext<WorkspaceCtx | null>(null);

export function useWorkspace(): WorkspaceCtx {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside a workspace route");
  return ctx;
}

const LAST_WS_KEY = "docify.lastWorkspace";

export function rememberWorkspace(slug: string) {
  try {
    localStorage.setItem(LAST_WS_KEY, slug);
  } catch {
    /* storage unavailable */
  }
}

export function lastWorkspace(): string | null {
  try {
    return localStorage.getItem(LAST_WS_KEY);
  } catch {
    return null;
  }
}
