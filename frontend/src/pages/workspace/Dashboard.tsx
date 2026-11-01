import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bug,
  FileText,
  FolderGit2,
  ListChecks,
  Plus,
  ShieldCheck,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router";
import { docs, findings, issues, jobs, qk } from "@/api/endpoints";
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
import {
  issueStatusLabel,
  issueStatusTone,
  personLabel,
  severityLabel,
  severityTone,
} from "@/lib/quality";

export default function Dashboard() {
  const { ws, slug, isAdmin, isMember } = useWorkspace();
  usePageMeta([{ label: ws.name }]);
  const reposQ = useRepos(slug);
  const docsQ = useQuery({
    queryKey: qk.docs(slug),
    queryFn: () => docs.list(slug),
  });
  const jobsQ = useQuery({
    queryKey: [...qk.jobs(slug), "recent"],
    queryFn: () => jobs.list(slug, { limit: 6 }),
    enabled: isMember,
    refetchInterval: (q) =>
      q.state.data?.items.some(
        (j) => j.status === "queued" || j.status === "running",
      )
        ? 5000
        : false,
  });

  const ready = reposQ.data?.filter((r) => r.status === "ready").length;
  const findingsQ = useQuery({
    queryKey: qk.findings(slug, "dashboard"),
    queryFn: () => findings.list(slug, { status: "open", limit: 4 }),
  });
  const issuesQ = useQuery({
    queryKey: qk.issues(slug, "dashboard"),
    queryFn: () => issues.list(slug, { status: "open,in_progress" }),
  });
  const recentDocs = [...(docsQ.data ?? [])]
    .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
    .slice(0, 6);

  const jobCols: Column<Job>[] = [
    {
      key: "type",
      header: "Job",
      cell: (j) => <span className="font-medium">{jobType(j.type)}</span>,
    },
    {
      key: "repo",
      header: "Repo",
      cell: (j) => (
        <span className="text-fg-muted">{j.repo_full_name ?? "—"}</span>
      ),
      className: "hidden sm:table-cell",
    },
    {
      key: "status",
      header: "Status",
      cell: (j) => <StatusPill status={j.status} />,
    },
    {
      key: "when",
      header: "Created",
      align: "right",
      cell: (j) => (
        <RelativeTime iso={j.created_at} className="text-fg-subtle" />
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title={ws.name}
        meta={
          <>
            {ws.is_public_demo && <Badge tone="accent">Demo</Badge>}
            {ws.role && <Badge className="capitalize">{ws.role}</Badge>}
            {ws.member_count != null && (
              <Badge icon={<Users />}>
                {ws.member_count} member{ws.member_count === 1 ? "" : "s"}
              </Badge>
            )}
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
        {[
          {
            to: `/w/${slug}/repos`,
            label: "Repositories",
            icon: <FolderGit2 />,
            value: ws.repo_count ?? reposQ.data?.length ?? "—",
            info:
              ready != null ? `${ready} indexed and documented.` : undefined,
          },
          {
            to: `/w/${slug}/repos`,
            label: "Documents",
            icon: <FileText />,
            value: docsQ.data?.length ?? "—",
          },
          {
            to: `/w/${slug}/checks`,
            label: "Open findings",
            icon: <ShieldCheck />,
            value: findingsQ.data?.counts.open ?? 0,
            info: "Policy violations found in pushed code.",
          },
          {
            to: `/w/${slug}/issues`,
            label: "Active issues",
            icon: <Bug />,
            value: issuesQ.data?.length ?? "—",
            info: "Open or in-progress issues.",
          },
        ].map((t, i) => (
          <motion.div
            key={t.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.3 }}
          >
            <Link
              to={t.to}
              className="block rounded-lg transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Stat
                label={t.label}
                icon={t.icon}
                value={t.value}
                info={t.info}
              />
            </Link>
          </motion.div>
        ))}
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
            <ErrorState
              compact
              error={docsQ.error}
              onRetry={() => void docsQ.refetch()}
            />
          ) : recentDocs.length === 0 ? (
            <EmptyState
              compact
              icon={<FileText />}
              title="No docs yet"
              info="Docs appear after a repository finishes indexing."
            />
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
                      {d.has_pending_review && isAdmin && (
                        <StatusPill status="pending_review" />
                      )}
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
            <ErrorState
              compact
              error={reposQ.error}
              onRetry={() => void reposQ.refetch()}
            />
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

      <Card className="mt-4">
        <CardHeader
          icon={<ShieldCheck />}
          title="Code health"
          info="Latest open policy findings and active issues across all repositories."
          actions={
            <Button asChild size="xs" variant="ghost">
              <Link to={`/w/${slug}/insights`}>
                Insights <ArrowRight />
              </Link>
            </Button>
          }
        />
        <div className="grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0">
          <div>
            {findingsQ.data && findingsQ.data.items.length === 0 ? (
              <EmptyState
                compact
                icon={<ShieldCheck />}
                title="No open findings"
              />
            ) : (
              <List label="Open findings">
                {(findingsQ.data?.items ?? []).map((f, i) => (
                  <ListItem
                    key={f.id}
                    index={i}
                    to={`/w/${slug}/checks`}
                    title={f.policy_name}
                    subtitle={`${f.path}${f.line ? `:${f.line}` : ""} · ${personLabel({ login: f.author_login, name: f.author_name })}`}
                    meta={
                      <Badge tone={severityTone[f.severity]}>
                        {severityLabel[f.severity]}
                      </Badge>
                    }
                  />
                ))}
              </List>
            )}
          </div>
          <div>
            {issuesQ.data && issuesQ.data.length === 0 ? (
              <EmptyState compact icon={<Bug />} title="No active issues" />
            ) : (
              <List label="Active issues">
                {(issuesQ.data ?? []).slice(0, 4).map((it, i) => (
                  <ListItem
                    key={it.id}
                    index={i}
                    to={`/w/${slug}/issues?open=${it.id}`}
                    title={`#${it.number} ${it.title}`}
                    subtitle={
                      it.assignee_login
                        ? `Assigned to @${it.assignee_login}`
                        : it.suspects[0]
                          ? `Likely ${personLabel(it.suspects[0])}`
                          : "Unassigned"
                    }
                    meta={
                      <Badge tone={issueStatusTone[it.status]}>
                        {issueStatusLabel[it.status]}
                      </Badge>
                    }
                  />
                ))}
              </List>
            )}
          </div>
        </div>
      </Card>

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
            <ErrorState
              compact
              error={jobsQ.error}
              onRetry={() => void jobsQ.refetch()}
            />
          ) : (
            <DataTable
              caption="Recent jobs"
              columns={jobCols}
              rows={jobsQ.data?.items}
              loading={jobsQ.isPending}
              skeletonRows={3}
              rowKey={(j) => j.id}
              empty={
                <EmptyState compact icon={<ListChecks />} title="No jobs yet" />
              }
            />
          )}
        </Card>
      )}
    </>
  );
}
