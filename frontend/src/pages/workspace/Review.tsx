import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, X } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { ApiError, errorMessage } from "@/api/client";
import { qk, review } from "@/api/endpoints";
import type { ReviewItem } from "@/api/types";
import { Markdown } from "@/components/Markdown";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  RelativeTime,
  SkeletonText,
  Tabs,
  useToast,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";

type View = "split" | "proposed";

export default function Review() {
  const { ws, slug } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Review" }]);
  const q = useQuery({ queryKey: qk.review(slug), queryFn: () => review.list(slug) });

  return (
    <>
      <PageHeader
        title="Review"
        meta={q.data && <span className="tabular">{q.data.length}</span>}
        info="New doc versions and changelog entries wait here when “Require approval” is on in Settings."
      />
      {q.isPending ? (
        <Card className="p-5">
          <SkeletonText lines={6} />
        </Card>
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data.length === 0 ? (
        <Card>
          <EmptyState icon={<ClipboardCheck />} title="All caught up" info="Nothing is waiting for approval." />
        </Card>
      ) : (
        <ul className="ui-stagger flex flex-col gap-4">
          {q.data.map((item, i) => (
            <li key={`${item.kind}-${item.id}`} style={{ "--i": Math.min(i, 12) } as CSSProperties}>
              <ReviewCard item={item} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ReviewCard({ item }: { item: ReviewItem }) {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const hasBase = item.base_content_md != null;
  const [view, setView] = useState<View>(hasBase ? "split" : "proposed");

  const decide = useMutation({
    mutationFn: (decision: "approve" | "reject") => review.decide(item.kind, item.id, decision),
    onSuccess: (_d, decision) => {
      toast.success(decision === "approve" ? "Published" : "Rejected", item.title);
      void qc.invalidateQueries({ queryKey: qk.review(slug) });
      void qc.invalidateQueries({ queryKey: ["ws", slug, "docs"] });
      void qc.invalidateQueries({ queryKey: ["doc"] });
    },
    onError: (e) => {
      toast.error("Couldn't save decision", errorMessage(e));
      if (e instanceof ApiError && e.status === 409) void qc.invalidateQueries({ queryKey: qk.review(slug) });
    },
  });

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <Badge tone={item.kind === "doc" ? "accent" : "info"}>{item.kind === "doc" ? "Doc" : "Changelog"}</Badge>
        <h2 className="min-w-0 truncate text-sm font-semibold">{item.title}</h2>
        <span className="text-xs text-fg-subtle">{item.repo_full_name}</span>
        <RelativeTime iso={item.created_at} className="text-xs text-fg-subtle" />
        <div className="ml-auto flex items-center gap-1.5">
          {hasBase && (
            <Tabs<View>
              ariaLabel="View"
              value={view}
              onValueChange={setView}
              items={[
                { value: "split", label: "Compare" },
                { value: "proposed", label: "Proposed" },
              ]}
            />
          )}
          <Button
            size="sm"
            variant="ghost"
            icon={<X />}
            loading={decide.isPending && decide.variables === "reject"}
            disabled={decide.isPending}
            onClick={() => decide.mutate("reject")}
          >
            Reject
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Check />}
            loading={decide.isPending && decide.variables === "approve"}
            disabled={decide.isPending}
            onClick={() => decide.mutate("approve")}
          >
            Approve
          </Button>
        </div>
      </div>
      <div className={view === "split" ? "grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0" : undefined}>
        {view === "split" && (
          <section aria-label="Current version" className="min-w-0">
            <div className="sticky top-12 bg-surface-2/80 px-4 py-1.5 text-2xs font-medium uppercase tracking-wide text-fg-subtle backdrop-blur-sm">
              Current
            </div>
            <div className="max-h-[60vh] overflow-auto px-4 py-3">
              <Markdown compact>{item.base_content_md ?? ""}</Markdown>
            </div>
          </section>
        )}
        <section aria-label="Proposed version" className="min-w-0">
          <div className="sticky top-12 bg-accent-soft/60 px-4 py-1.5 text-2xs font-medium uppercase tracking-wide text-accent-text backdrop-blur-sm">
            Proposed
          </div>
          <div className="max-h-[60vh] overflow-auto px-4 py-3">
            <Markdown compact>{item.content_md}</Markdown>
          </div>
        </section>
      </div>
    </Card>
  );
}
