import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ListChecks, RotateCcw } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import { jobs, qk } from "@/api/endpoints";
import type { Job, JobStatus } from "@/api/types";
import {
  Button,
  Card,
  CopyButton,
  DataTable,
  Drawer,
  EmptyState,
  ErrorState,
  IconButton,
  KeyValues,
  PageHeader,
  RelativeTime,
  StatusPill,
  Tabs,
  useToast,
  type Column,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";
import { summarizeError } from "@/lib/format";
import { jobType } from "@/lib/labels";

type Filter = "all" | JobStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "failed", label: "Failed" },
  { value: "dead", label: "Dead" },
  { value: "blocked_budget", label: "Over budget" },
  { value: "succeeded", label: "Succeeded" },
];

function duration(j: Job): string {
  if (!j.started_at) return "—";
  const end = j.finished_at ? new Date(j.finished_at).getTime() : Date.now();
  const s = Math.max(0, Math.round((end - new Date(j.started_at).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export default function Jobs() {
  const { ws, slug, isAdmin } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Jobs" }]);
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<Job | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const status = filter === "all" ? undefined : filter;

  const q = useInfiniteQuery({
    queryKey: qk.jobs(slug, status),
    queryFn: ({ pageParam }) => jobs.list(slug, { cursor: pageParam, status, limit: 30 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? null,
    refetchInterval: (query) =>
      query.state.data?.pages[0]?.items.some((j) => j.status === "queued" || j.status === "running") ? 5000 : false,
  });

  const retry = useMutation({
    mutationFn: (id: string) => jobs.retry(id),
    onSuccess: () => {
      toast.success("Retry queued");
      setOpen(null);
      void qc.invalidateQueries({ queryKey: qk.jobs(slug) });
      void qc.invalidateQueries({ queryKey: qk.repos(slug) });
    },
    onError: (e) => toast.error("Couldn't retry job", errorMessage(e)),
  });

  const rows = q.data?.pages.flatMap((p) => p.items);
  const retryable = (j: Job) => isAdmin && (j.status === "failed" || j.status === "dead");

  const columns: Column<Job>[] = [
    { key: "type", header: "Job", cell: (j) => <span className="font-medium">{jobType(j.type)}</span> },
    { key: "repo", header: "Repository", className: "hidden md:table-cell", cell: (j) => <span className="text-fg-muted">{j.repo_full_name ?? "—"}</span> },
    { key: "status", header: "Status", className: "w-32", cell: (j) => <StatusPill status={j.status} hint={summarizeError(j.error)} /> },
    {
      key: "attempts",
      header: "Tries",
      info: "Attempts used / maximum. Failed jobs retry automatically with backoff.",
      align: "right",
      className: "hidden sm:table-cell w-20",
      cell: (j) => (
        <span className="tabular text-fg-muted">
          {j.attempts}/{j.max_attempts}
        </span>
      ),
    },
    { key: "duration", header: "Took", align: "right", className: "hidden lg:table-cell w-24", cell: (j) => <span className="tabular text-fg-muted">{duration(j)}</span> },
    { key: "created", header: "Created", align: "right", className: "w-28", cell: (j) => <RelativeTime iso={j.created_at} className="text-fg-subtle" /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (j) =>
        retryable(j) ? (
          <IconButton
            size="xs"
            label="Retry"
            icon={<RotateCcw />}
            loading={retry.isPending && retry.variables === j.id}
            onClick={(e) => {
              e.stopPropagation();
              retry.mutate(j.id);
            }}
          />
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader title="Jobs" info="Background work: indexing, syncs after pushes, purges. Updates live while jobs run." />
      <div className="mb-3 overflow-x-auto">
        <Tabs<Filter> ariaLabel="Filter by status" value={filter} onValueChange={setFilter} items={FILTERS} />
      </div>
      <Card>
        {q.isError ? (
          <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        ) : (
          <DataTable
            caption="Jobs"
            columns={columns}
            rows={rows}
            loading={q.isPending}
            rowKey={(j) => j.id}
            onRowClick={setOpen}
            maxHeight="calc(100dvh - 15rem)"
            empty={<EmptyState icon={<ListChecks />} title={filter === "all" ? "No jobs yet" : "No jobs with this status"} />}
          />
        )}
      </Card>
      {q.hasNextPage && (
        <div className="mt-3 flex justify-center">
          <Button size="sm" loading={q.isFetchingNextPage} onClick={() => void q.fetchNextPage()}>
            Load more
          </Button>
        </div>
      )}

      <Drawer open={!!open} onOpenChange={(o) => !o && setOpen(null)} title={open ? jobType(open.type) : "Job"}>
        {open && (
          <div className="flex flex-col gap-3 p-3">
            <div className="flex items-center gap-2">
              <StatusPill status={open.status} />
              <span className="truncate text-sm text-fg-muted">{open.repo_full_name ?? "Workspace job"}</span>
              {retryable(open) && (
                <Button size="sm" className="ml-auto" icon={<RotateCcw />} loading={retry.isPending} onClick={() => retry.mutate(open.id)}>
                  Retry
                </Button>
              )}
            </div>
            <KeyValues
              className="sm:grid-cols-2"
              items={[
                { label: "Created", value: <RelativeTime iso={open.created_at} /> },
                { label: "Started", value: <RelativeTime iso={open.started_at} /> },
                { label: "Finished", value: <RelativeTime iso={open.finished_at} /> },
                { label: "Tries", value: <span className="tabular">{open.attempts}/{open.max_attempts}</span> },
              ]}
            />
            <div className="flex items-center gap-1 text-xs text-fg-subtle">
              <span className="font-mono">{open.id}</span>
              <CopyButton value={open.id} label="Copy job ID" />
            </div>
            {open.error != null && (
              <div>
                <div className="mb-1 text-2xs font-medium uppercase tracking-wide text-fg-subtle">Error</div>
                <pre className="max-h-80 overflow-auto rounded-md border border-border bg-code p-2.5 font-mono text-2xs leading-relaxed text-danger">
                  {JSON.stringify(open.error, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  );
}
