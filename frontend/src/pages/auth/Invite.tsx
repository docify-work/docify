import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, MailOpen, SearchX } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, errorMessage, loginUrl } from "@/api/client";
import { invites, qk } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { Badge, Button, Callout, EmptyState, ErrorState, PageSpinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function Invite() {
  usePageMeta([{ label: "Invitation" }]);
  const { token = "" } = useParams();
  const { me, isLoading: meLoading } = useMe();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: qk.invite(token), queryFn: () => invites.get(token), retry: false });
  const accept = useMutation({
    mutationFn: () => invites.accept(token),
    onSuccess: async (ws) => {
      await qc.invalidateQueries({ queryKey: qk.me });
      navigate(`/w/${ws.slug}`, { replace: true });
    },
  });

  if (q.isPending || meLoading) return <AuthCard title="Invitation"><PageSpinner /></AuthCard>;
  if (q.isError) {
    const notFound = q.error instanceof ApiError && q.error.status === 404;
    return (
      <AuthCard title="Invitation">
        {notFound ? (
          <EmptyState compact icon={<SearchX />} title="This invite is invalid or was revoked." />
        ) : (
          <ErrorState compact error={q.error} onRetry={() => void q.refetch()} />
        )}
      </AuthCard>
    );
  }
  const inv = q.data;
  const here = `/invite/${encodeURIComponent(token)}`;
  const wrongUser = me && me.email.toLowerCase() !== inv.email.toLowerCase();

  return (
    <AuthCard title={`Join ${inv.workspace_name}`}>
      {inv.expired ? (
        <EmptyState compact icon={<Clock />} title="This invite has expired" info="Ask an admin to send a new one." />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm">
            <MailOpen className="size-4 text-fg-subtle" aria-hidden="true" />
            <span className="truncate">{inv.email}</span>
            <Badge tone={inv.role === "admin" ? "accent" : "neutral"} className="ml-auto capitalize">
              {inv.role}
            </Badge>
          </div>
          {!me ? (
            <>
              <Button asChild variant="primary" className="w-full">
                <Link to={loginUrl(here)}>Sign in to accept</Link>
              </Button>
              <Button asChild variant="ghost" className="w-full">
                <Link to={`/signup?next=${encodeURIComponent(here)}`}>Create account</Link>
              </Button>
            </>
          ) : (
            <>
              {wrongUser && (
                <Callout tone="warning">
                  You're signed in as {me.email}. Sign in with {inv.email} to accept.
                </Callout>
              )}
              {accept.isError && <Callout tone="danger">{errorMessage(accept.error)}</Callout>}
              <Button variant="primary" className="w-full" loading={accept.isPending} onClick={() => accept.mutate()}>
                Accept invitation
              </Button>
            </>
          )}
        </div>
      )}
    </AuthCard>
  );
}
