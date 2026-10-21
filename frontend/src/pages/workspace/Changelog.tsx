import { useInfiniteQuery } from "@tanstack/react-query";
import { GitCommitHorizontal, History } from "lucide-react";
import type { CSSProperties } from "react";
import { useParams } from "react-router";
import { qk, repos } from "@/api/endpoints";
import { Markdown } from "@/components/Markdown";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, RelativeTime, SkeletonText } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepo } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";
import { shortSha } from "@/lib/format";

export default function Changelog() {
  const { ws, slug } = useWorkspace();
  const { repoId = "" } = useParams();
  const repoQ = useRepo(repoId);
  const q = useInfiniteQuery({
    queryKey: qk.changelog(repoId),
    queryFn: ({ pageParam }) => repos.changelog(repoId, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
  const name = repoQ.data?.full_name ?? "Repository";
  usePageMeta([
    { label: ws.name, to: `/w/${slug}` },
    { label: name, to: `/w/${slug}/repos/${repoId}` },
    { label: "Changelog" },
  ]);
  const entries = q.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Changelog" meta={repoQ.data && <span>{repoQ.data.full_name}</span>} info="One entry per sync, written from commits and merged PRs." />
      {q.isPending ? (
        <Card className="p-5">
          <SkeletonText lines={6} />
        </Card>
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : entries.length === 0 ? (
        <Card>
          <EmptyState icon={<History />} title="No changelog entries yet" info="Entries are added when new commits land on the default branch." />
        </Card>
      ) : (
        <ol className="ui-stagger relative flex flex-col gap-3 before:absolute before:bottom-2 before:left-[9px] before:top-2 before:w-px before:bg-border">
          {entries.map((e, i) => (
            <li key={e.id} className="relative pl-7" style={{ "--i": Math.min(i, 12) } as CSSProperties}>
              <span className="absolute left-0 top-3 grid size-[19px] place-items-center rounded-full border border-border bg-surface text-fg-subtle">
                <GitCommitHorizontal className="size-3" aria-hidden="true" />
              </span>
              <Card className="px-4 py-3">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
                  <RelativeTime iso={e.created_at} className="font-medium text-fg-muted" />
                  <span className="font-mono">
                    {e.from_sha ? `${shortSha(e.from_sha)}…` : ""}
                    {shortSha(e.to_sha)}
                  </span>
                  {e.pr_numbers.map((n) => (
                    <a
                      key={n}
                      href={repoQ.data ? `https://github.com/${repoQ.data.full_name}/pull/${n}` : undefined}
                      target="_blank"
                      rel="nofollow noopener noreferrer"
                    >
                      <Badge tone="accent">#{n}</Badge>
                    </a>
                  ))}
                </div>
                <Markdown compact>{e.content_md}</Markdown>
              </Card>
            </li>
          ))}
        </ol>
      )}
      {q.hasNextPage && (
        <div className="mt-4 flex justify-center">
          <Button size="sm" loading={q.isFetchingNextPage} onClick={() => void q.fetchNextPage()}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
