import { useQuery } from "@tanstack/react-query";
import { getPublicConfig, qk } from "@/api/endpoints";

/** Runtime config: `/config.json` (per-env file uploaded at deploy) merged with `GET /api/config`. */
export interface AppConfig {
  env: string;
  version: string;
  apiVersion: string | null;
  githubEnabled: boolean;
  googleEnabled: boolean;
  githubAppSlug: string | null;
  demoWorkspaceSlug: string | null;
}

export const DEFAULT_CONFIG: AppConfig = {
  env: "local",
  version: "dev",
  apiVersion: null,
  githubEnabled: false,
  googleEnabled: false,
  githubAppSlug: null,
  demoWorkspaceSlug: null,
};

async function loadStaticConfig(): Promise<Partial<{ env: string; version: string }>> {
  const res = await fetch("/config.json", { cache: "no-cache", credentials: "same-origin" });
  if (!res.ok) return {};
  return (await res.json()) as { env?: string; version?: string };
}

export async function loadConfig(): Promise<AppConfig> {
  const [file, api] = await Promise.allSettled([loadStaticConfig(), getPublicConfig()]);
  const f = file.status === "fulfilled" ? file.value : {};
  const a = api.status === "fulfilled" ? api.value : null;
  return {
    env: f.env ?? a?.env ?? DEFAULT_CONFIG.env,
    version: f.version ?? DEFAULT_CONFIG.version,
    apiVersion: a?.version ?? null,
    githubEnabled: a?.github_enabled ?? false,
    googleEnabled: a?.google_enabled ?? false,
    githubAppSlug: a?.github_app_slug ?? null,
    demoWorkspaceSlug: a?.demo_workspace_slug ?? null,
  };
}

export function useAppConfig(): AppConfig {
  const { data } = useQuery({ queryKey: qk.config, queryFn: loadConfig, staleTime: Infinity, retry: 1 });
  return data ?? DEFAULT_CONFIG;
}
