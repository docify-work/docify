import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { auth, getMe, qk } from "@/api/endpoints";

/** Current user (null = anonymous). */
export function useMe() {
  const q = useQuery({ queryKey: qk.me, queryFn: getMe, staleTime: 60_000 });
  return { me: q.data ?? null, isLoading: q.isPending, isError: q.isError, error: q.error, refetch: q.refetch };
}

export function useLogout() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: auth.logout,
    onSettled: () => {
      qc.clear();
      qc.setQueryData(qk.me, null);
      navigate("/", { replace: true });
    },
  });
}

/** Sanitize a `next` param to an in-app path. */
export function safeNext(next: string | null | undefined, fallback = "/app"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return fallback;
  return next;
}
