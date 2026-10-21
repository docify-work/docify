import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FileText, GitBranch, History, Lock, SearchX } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError } from "@/api/client";
import { docs, qk } from "@/api/endpoints";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  CopyButton,
  EmptyState,
  ErrorState,
  KeyValues,
  List,
  ListItem,
  PageHeader,
  PageSpinner,
  RelativeTime,
  SkeletonRows,
  StatusPill,
  Tooltip,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepo } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";
import { shortSha, summarizeError } from "@/lib/format";
import { docKind } from "@/lib/labels";
import { RepoActions } from "./Repos";

export default function RepoDetail() {
  const { ws, slug, isAdmin } = useWorkspace();
  const { repoId = "" } = useParams();
  const navigate = useNavigate();
  const repoQ = useRepo(repoId);
  const docsQ = useQuery({ queryKey: qk.docs(slug, repoId), queryFn: () => docs.list(slug, repoId) });
  const repo = repoQ.data;
  usePageMeta([
    { label: ws.name, to: `/w/${slug}` },
    { label: "Repositories", to: `/w/${slug}/repos` },
    { label: repo?.full_name ?? "Repository" },
  ]);

  if (repoQ.isPending) return <PageSpinner />;
  if (repoQ.isError) {
    return repoQ.error instanceof ApiError && repoQ.error.status === 404 ? (
      <EmptyState icon={<SearchX />} title="Repository not found" />
    ) : (
      <ErrorState error={repoQ.error} onRetry={() => void repoQ.refetch()} />
    );
  }
  const r = repoQ.data;
  const err = summarizeError(r.error);

  return (
    <>
      <PageHeader
        title={r.full_name}
        meta={
          <>
            <StatusPill status={r.status} hint={err} />
            {r.private && (
              <Tooltip content="Private repository">
                <Lock className="size-3.5" aria-label="Private" />
              </Tooltip>
            )}
            {r.archived && <Badge>Archived</Badge>}
          </>
        }
        actions={
          <>
            <Button asChild size="sm" variant="ghost">
              <Link to={`/w/${slug}/changelog/${r.id}`}>
                <History />
                Changelog
              </Link>
            </Button>
            <Button asChild size="sm" variant="ghost">
              <a href={r.html_url} target="_blank" rel="nofollow noopener noreferrer">
                <ExternalLink />
                GitHub
              </a>
            </Button>
            {isAdmin && <RepoActions repo={r} variant="buttons" onRemoved={() => navigate(`/w/${slug}/repos`)} />}
          </>
        }
      />

      {err && (r.status === "error" || r.status === "too_large") && (
        <Callout tone="danger" className="mb-4">
          {err}
        </Callout>
      )}

      <KeyValues
        className="mb-4"
        items={[
          {
            label: "Branch",
            value: (
              <span className="inline-flex items-center gap-1 font-mono text-xs">
                <GitBranch className="size-3 text-fg-subtle" aria-hidden="true" />
                {r.default_branch}
              </span>
            ),
          },
          {
            label: "Commit",
            info: "Last commit Docify processed.",
            value: r.last_processed_sha ? (
              <>
                <span className="font-mono text-xs">{shortSha(r.last_processed_sha)}</span>
                <CopyButton value={r.last_processed_sha} label="Copy SHA" />
              </>
            ) : (
              <span className="text-fg-subtle">—</span>
            ),
          },
          { label: "Synced", value: <RelativeTime iso={r.last_synced_at} /> },
          { label: "Added", value: <RelativeTime iso={r.created_at} /> },
        ]}
      />

      <Card>
        <CardHeader icon={<FileText />} title="Documents" meta={docsQ.data?.length} />
        {docsQ.isPending ? (
          <SkeletonRows rows={3} />
        ) : docsQ.isError ? (
          <ErrorState compact error={docsQ.error} onRetry={() => void docsQ.refetch()} />
        ) : docsQ.data.length === 0 ? (
          <EmptyState
            compact
            icon={<FileText />}
            title={r.status === "indexing" || r.status === "pending" ? "Generating docs…" : "No documents"}
            info="Overview, setup guide and API reference are generated after indexing."
          />
        ) : (
          <List label="Documents">
            {docsQ.data.map((d, i) => (
              <ListItem
                key={d.id}
                index={i}
                to={`/w/${slug}/docs/${d.id}`}
                icon={<FileText />}
                title={d.title}
                subtitle={docKind(d.kind)}
                meta={
                  <>
                    {d.published ? (
                      <span className="tabular">v{d.published.version}</span>
                    ) : (
                      <Badge>Unpublished</Badge>
                    )}
                    {d.published?.partial && (
                      <Tooltip content="Generated from a subset of files (input budget).">
                        <span tabIndex={0}>
                          <Badge tone="warning">Partial</Badge>
                        </span>
                      </Tooltip>
                    )}
                    {d.has_pending_review && isAdmin && <StatusPill status="pending_review" />}
                    <RelativeTime iso={d.updated_at} />
                  </>
                }
              />
            ))}
          </List>
        )}
      </Card>
    </>
  );
}
