import { useQuery } from "@tanstack/react-query";
import { qk, repos } from "@/api/endpoints";
import type { Repo } from "@/api/types";

export const POLL_MS = 5000;
const BUSY = new Set(["pending", "indexing"]);

export const isBusy = (r: Pick<Repo, "status">) => BUSY.has(r.status);

/** Workspace repos; polls every 5 s while any repo is pending/indexing. */
export function useRepos(slug: string) {
  return useQuery({
    queryKey: qk.repos(slug),
    queryFn: () => repos.list(slug),
    refetchInterval: (q) => (q.state.data?.some(isBusy) ? POLL_MS : false),
  });
}

/** Single repo; same polling rule. */
export function useRepo(id: string) {
  return useQuery({
    queryKey: qk.repo(id),
    queryFn: () => repos.get(id),
    refetchInterval: (q) => (q.state.data && isBusy(q.state.data) ? POLL_MS : false),
  });
}
