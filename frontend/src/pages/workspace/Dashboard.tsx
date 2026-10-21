import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText, FolderGit2, ListChecks, Plus, Users } from "lucide-react";
import { Link } from "react-router";
import { docs, jobs, qk } from "@/api/endpoints";
import type { Job } from "@/api/types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  ErrorState,
  List,
  ListItem,
  PageHeader,
  RelativeTime,
  SkeletonRows,
  Stat,
  StatusPill,
  type Column,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepos } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";
import { docKind, jobType } from "@/lib/labels";

export default function Dashboard() {
  const { ws, slug, isAdmin, isMember } = useWorkspace();
  usePageMeta([{ label: ws.name }]);
  const reposQ = useRepos(slug);
  const docsQ = useQuery({ queryKey: qk.docs(slug), queryFn: () => docs.list(slug) });
  const jobsQ = useQuery({
    queryKey: [...qk.jobs(slug), "recent"],
    queryFn: () => jobs.list(slug, { limit: 6 }),
    enabled: isMember,
    refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === "queued" || j.status === "running") ? 5000 : false),
  });

  const ready = reposQ.data?.filter((r) => r.status === "ready").length;
  const recentDocs = [...(docsQ.data ?? [])]
    .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
    .slice(0, 6);

  const jobCols: Column<Job>[] = [
    { key: "type", header: "Job", cell: (j) => <span className="font-medium">{jobType(j.type)}</span> },
    { key: "repo", header: "Repo", cell: (j) => <span className="text-fg-muted">{j.repo_full_name ?? "—"}</span>, className: "hidden sm:table-cell" },
    { key: "status", header: "Status", cell: (j) => <StatusPill status={j.status} /> },
    { key: "when", header: "Created", align: "right", cell: (j) => <RelativeTime iso={j.created_at} className="text-fg-subtle" /> },
  ];

  return (
    <>
      <PageHeader
        title={ws.name}
        meta={
          <>
            {ws.is_public_demo && <Badge tone="accent">Demo</Badge>}
            {ws.role && <Badge className="capitalize">{ws.role}</Badge>}
          </>
        }
        actions={
          isAdmin && (
            <Button asChild size="sm" variant="primary">
              <Link to={`/w/${slug}/repos`}>
                <Plus />
                Add repositories
              </Link>
            </Button>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Repositories" icon={<FolderGit2 />} value={ws.repo_count ?? reposQ.data?.length ?? "—"} />
        <Stat label="Ready" icon={<FolderGit2 />} value={ready ?? "—"} info="Indexed and documented." />
        <Stat label="Documents" icon={<FileText />} value={docsQ.data?.length ?? "—"} />
        <Stat label="Members" icon={<Users />} value={ws.member_count ?? "—"} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            icon={<FileText />}
            title="Recent docs"
            actions={
              <Button asChild size="xs" variant="ghost">
                <Link to={`/w/${slug}/repos`}>
                  All <ArrowRight />
                </Link>
              </Button>
            }
          />
          {docsQ.isPending ? (
            <SkeletonRows rows={4} />
          ) : docsQ.isError ? (
            <ErrorState compact error={docsQ.error} onRetry={() => void docsQ.refetch()} />
          ) : recentDocs.length === 0 ? (
            <EmptyState compact icon={<FileText />} title="No docs yet" info="Docs appear after a repository finishes indexing." />
          ) : (
            <List label="Recent docs">
              {recentDocs.map((d, i) => (
                <ListItem
                  key={d.id}
                  index={i}
                  to={`/w/${slug}/docs/${d.id}`}
                  title={d.title}
                  subtitle={d.repo_full_name}
                  meta={
                    <>
                      <Badge>{docKind(d.kind)}</Badge>
                      {d.has_pending_review && isAdmin && <StatusPill status="pending_review" />}
                      <RelativeTime iso={d.updated_at} />
                    </>
                  }
                />
              ))}
            </List>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            icon={<FolderGit2 />}
            title="Repositories"
            meta={reposQ.data?.length}
            actions={
              <Button asChild size="xs" variant="ghost">
                <Link to={`/w/${slug}/repos`}>
                  Manage <ArrowRight />
                </Link>
              </Button>
            }
          />
          {reposQ.isPending ? (
            <SkeletonRows rows={4} />
          ) : reposQ.isError ? (
            <ErrorState compact error={reposQ.error} onRetry={() => void reposQ.refetch()} />
          ) : reposQ.data.length === 0 ? (
            <EmptyState
              compact
              icon={<FolderGit2 />}
              title="No repositories"
              action={
                isAdmin && (
                  <Button asChild size="sm" variant="primary">
                    <Link to={`/w/${slug}/repos`}>Connect GitHub</Link>
                  </Button>
                )
              }
            />
          ) : (
            <List label="Repositories">
              {reposQ.data.slice(0, 6).map((r, i) => (
                <ListItem
                  key={r.id}
                  index={i}
                  to={`/w/${slug}/repos/${r.id}`}
                  title={r.full_name}
                  meta={<StatusPill status={r.status} />}
                />
              ))}
            </List>
          )}
        </Card>
      </div>

      {isMember && (
        <Card className="mt-4">
          <CardHeader
            icon={<ListChecks />}
            title="Recent jobs"
            actions={
              <Button asChild size="xs" variant="ghost">
                <Link to={`/w/${slug}/jobs`}>
                  All <ArrowRight />
                </Link>
              </Button>
            }
          />
          {jobsQ.isError ? (
            <ErrorState compact error={jobsQ.error} onRetry={() => void jobsQ.refetch()} />
          ) : (
            <DataTable
              caption="Recent jobs"
              columns={jobCols}
              rows={jobsQ.data?.items}
              loading={jobsQ.isPending}
              skeletonRows={3}
              rowKey={(j) => j.id}
              empty={<EmptyState compact icon={<ListChecks />} title="No jobs yet" />}
            />
          )}
        </Card>
      )}
    </>
  );
}
