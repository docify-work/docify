import { useQuery } from "@tanstack/react-query";
import { SearchX } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Outlet, useParams } from "react-router";
import { ApiError } from "@/api/client";
import { qk, workspaces } from "@/api/endpoints";
import { Button, Callout, EmptyState, ErrorState, PageSpinner, TextLink } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { WorkspaceContext, rememberWorkspace, type WorkspaceCtx } from "@/hooks/useWorkspace";
import { Link } from "react-router";

/** Loads `/workspaces/{ws}` once and provides it (+ role flags) to every workspace page. */
export function WorkspaceLayout() {
  const { ws: slug = "" } = useParams();
  const { me } = useMe();
  const q = useQuery({ queryKey: qk.workspace(slug), queryFn: () => workspaces.get(slug), retry: false });

  useEffect(() => {
    if (q.data && me) rememberWorkspace(q.data.slug);
  }, [q.data, me]);

  const ctx = useMemo<WorkspaceCtx | null>(() => {
    if (!q.data) return null;
    const role = q.data.role ?? null;
    return {
      ws: q.data,
      slug: q.data.slug,
      isAdmin: role === "admin",
      isMember: role === "admin" || role === "member",
      isAnonymous: !me,
    };
  }, [q.data, me]);

  if (q.isPending) return <PageSpinner />;
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404) {
      return (
        <EmptyState
          icon={<SearchX />}
          title="Workspace not found"
          info="It doesn't exist or you don't have access."
          action={
            <Button asChild size="sm">
              <Link to="/app">Go to my workspaces</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  }
  if (!ctx) return null;

  return (
    <WorkspaceContext.Provider value={ctx}>
      {ctx.isAnonymous && ctx.ws.is_public_demo && (
        <Callout tone="info" className="mb-4">
          Public demo · read-only.{" "}
          <TextLink to="/signup">Create your own workspace</TextLink>
        </Callout>
      )}
      <Outlet />
    </WorkspaceContext.Provider>
  );
}
