import { useQuery } from "@tanstack/react-query";
import { FileCode2, FileText, SearchX } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "@/api/client";
import { docs, qk } from "@/api/endpoints";
import { Markdown } from "@/components/Markdown";
import {
  Badge,
  Callout,
  Card,
  CardHeader,
  CopyButton,
  EmptyState,
  ErrorState,
  PageHeader,
  RelativeTime,
  Select,
  SkeletonText,
  StatusPill,
  TextLink,
  Tooltip,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";
import { formatDate, shortSha } from "@/lib/format";
import { docKind } from "@/lib/labels";

export default function DocPage() {
  const { ws, slug, isAdmin } = useWorkspace();
  const { docId = "" } = useParams();
  const docQ = useQuery({ queryKey: qk.doc(docId), queryFn: () => docs.get(docId) });
  const versionsQ = useQuery({ queryKey: qk.docVersions(docId), queryFn: () => docs.versions(docId) });
  const [versionId, setVersionId] = useState<string>("");
  const doc = docQ.data;
  usePageMeta([
    { label: ws.name, to: `/w/${slug}` },
    ...(doc ? [{ label: doc.repo_full_name, to: `/w/${slug}/repos/${doc.repo_id}` }] : []),
    { label: doc?.title ?? "Document" },
  ]);

  if (docQ.isError) {
    return docQ.error instanceof ApiError && docQ.error.status === 404 ? (
      <EmptyState icon={<SearchX />} title="Document not found" />
    ) : (
      <ErrorState error={docQ.error} onRetry={() => void docQ.refetch()} />
    );
  }

  const selected = versionsQ.data?.find((v) => v.id === versionId) ?? null;
  const shown = selected
    ? { content: selected.content_md, sha: selected.commit_sha, created: selected.created_at, model: selected.model, partial: selected.partial, status: selected.status, version: selected.version }
    : doc?.published
      ? { content: doc.content_md ?? "", sha: doc.published.commit_sha, created: doc.published.created_at, model: doc.published.model, partial: doc.published.partial, status: doc.published.status, version: doc.published.version }
      : null;

  const versionOptions = [
    { value: "", label: doc?.published ? `Latest · v${doc.published.version}` : "Latest" },
    ...(versionsQ.data ?? [])
      .filter((v) => v.id !== doc?.published?.id)
      .map((v) => ({ value: v.id, label: `v${v.version} · ${v.status.replace("_", " ")} · ${formatDate(v.created_at)}` })),
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px]">
      <div className="min-w-0">
        <PageHeader
          title={doc?.title ?? "…"}
          meta={doc && <Badge>{docKind(doc.kind)}</Badge>}
          actions={
            (versionsQ.data?.length ?? 0) > 1 && (
              <Select
                size="sm"
                aria-label="Version"
                options={versionOptions}
                value={versionId}
                onChange={(e) => setVersionId(e.target.value)}
                className="w-56"
              />
            )
          }
        />
        {doc?.has_pending_review && isAdmin && !selected && (
          <Callout tone="warning" className="mb-4" action={<TextLink to={`/w/${slug}/review`}>Review</TextLink>}>
            A newer version is waiting for approval.
          </Callout>
        )}
        {selected && selected.status !== "published" && (
          <Callout tone="info" className="mb-4" onDismiss={() => setVersionId("")}>
            Viewing v{selected.version} ({selected.status.replace("_", " ")}).
          </Callout>
        )}
        <Card className="px-5 py-5 sm:px-7">
          {docQ.isPending ? (
            <SkeletonText lines={8} />
          ) : !shown ? (
            <EmptyState compact icon={<FileText />} title="Not published yet" info="The first version is still generating or awaiting review." />
          ) : (
            <Markdown>{shown.content}</Markdown>
          )}
        </Card>
      </div>

      <aside className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-16 lg:self-start">
        {shown && doc && (
          <Card>
            <CardHeader title="Version" meta={`v${shown.version}`} />
            <dl className="flex flex-col gap-2 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-fg-subtle">Status</dt>
                <dd>
                  <StatusPill status={shown.status} />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-fg-subtle">Commit</dt>
                <dd className="flex items-center gap-0.5 font-mono">
                  {shortSha(shown.sha)}
                  <CopyButton value={shown.sha} label="Copy SHA" />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-fg-subtle">Generated</dt>
                <dd>
                  <RelativeTime iso={shown.created} />
                </dd>
              </div>
              {shown.model && (
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-fg-subtle">Model</dt>
                  <dd className="truncate font-mono">{shown.model}</dd>
                </div>
              )}
              {shown.partial && (
                <Tooltip content="Generated from a subset of files to stay within the input budget.">
                  <span tabIndex={0} className="self-start">
                    <Badge tone="warning">Partial</Badge>
                  </span>
                </Tooltip>
              )}
            </dl>
          </Card>
        )}
        {doc && doc.source_paths.length > 0 && (
          <Card>
            <CardHeader title="Sources" meta={doc.source_paths.length} info="Files this document was generated from." />
            <ul className="max-h-80 overflow-auto p-1.5">
              {doc.source_paths.map((p) => (
                <li key={p}>
                  <a
                    href={`https://github.com/${doc.repo_full_name}/blob/${shown?.sha ?? "HEAD"}/${p}`}
                    target="_blank"
                    rel="nofollow noopener noreferrer"
                    className="flex h-7 items-center gap-1.5 rounded-md px-1.5 font-mono text-2xs text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
                    title={p}
                  >
                    <FileCode2 className="size-3 shrink-0 text-fg-subtle" aria-hidden="true" />
                    <span className="truncate">{p}</span>
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        )}
        {doc && (
          <Link to={`/w/${slug}/changelog/${doc.repo_id}`} className="px-1 text-xs text-fg-subtle transition-colors hover:text-fg">
            View changelog →
          </Link>
        )}
      </aside>
    </div>
  );
}
