import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { loginUrl } from "@/api/client";
import { useMe } from "@/hooks/useMe";
import { useWorkspace } from "@/hooks/useWorkspace";
import { EmptyState, ErrorState, PageSpinner } from "./ui";

/** Renders children only for signed-in users; otherwise redirects to /login?next=<here>. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, isLoading, isError, error, refetch } = useMe();
  const location = useLocation();
  if (isLoading) return <PageSpinner />;
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (!me) return <Navigate to={loginUrl(location.pathname + location.search)} replace />;
  return <>{children}</>;
}

/** Workspace admins only (inside a workspace route). Members see a compact notice. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin, isAnonymous } = useWorkspace();
  const location = useLocation();
  if (isAnonymous) return <Navigate to={loginUrl(location.pathname + location.search)} replace />;
  if (!isAdmin) {
    return (
      <EmptyState
        icon={<ShieldAlert />}
        title="Admins only"
        info="Ask a workspace admin to change your role."
      />
    );
  }
  return <>{children}</>;
}

/** Signed-in workspace members only (hides member-only pages from anonymous demo visitors). */
export function RequireMember({ children }: { children: ReactNode }) {
  const { isMember } = useWorkspace();
  const location = useLocation();
  if (!isMember) return <Navigate to={loginUrl(location.pathname + location.search)} replace />;
  return <>{children}</>;
}
