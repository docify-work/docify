import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Eye,
  FileCode2,
  FolderGit2,
  GitCommitHorizontal,
  GitFork,
  GitMerge,
  GitPullRequest,
  RefreshCw,
  Scale,
  ShieldAlert,
  Star,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { insights, qk, repos as reposApi } from "@/api/endpoints";
import type { Insights as InsightsData } from "@/api/types";
import {
  BarList,
  ColumnChart,
  CountUp,
  Heatmap,
  ScoreRing,
} from "@/components/charts";
import {
  Avatar,
  Badge,
  Card,
  CardBody,
  CardHeader,
  Drawer,
  EmptyState,
  ErrorState,
  IconButton,
  InfoTip,
  PageHeader,
  RelativeTime,
  Select,
  Skeleton,
  Tooltip,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";
import { githubAvatar, personLabel, shortSha } from "@/lib/quality";

type Person = InsightsData["contributors"][number];

const fade = (i: number) => ({
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: {
    duration: 0.35,
    delay: i * 0.05,
    ease: [0.22, 1, 0.36, 1] as const,
  },
});

export default function Insights() {
  const { ws, slug, isMember } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Insights" }]);
  const [params, setParams] = useSearchParams();
  const reposQ = useQuery({
    queryKey: qk.repos(slug),
    queryFn: () => reposApi.list(slug),
  });
  const ready = (reposQ.data ?? []).filter(
    (r) => r.status === "ready" || r.status === "indexing",
  );
  const repoId = params.get("repo") ?? ready[0]?.id ?? "";
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [person, setPerson] = useState<Person | null>(null);

  const q = useQuery({
    queryKey: qk.insights(repoId),
    queryFn: () => insights.repo(repoId),
    enabled: !!repoId,
  });

  const refresh = async () => {
    setRefreshing(true);
    try {
      qc.setQueryData(qk.insights(repoId), await insights.repo(repoId, true));
    } finally {
      setRefreshing(false);
    }
  };

  if (reposQ.isSuccess && !ready.length) {
    return (
      <>
        <PageHeader title="Insights" icon={<BarChart3 />} />
        <EmptyState
          icon={<FolderGit2 />}
          title="No repositories yet"
          info="Connect a repository to see who builds what, how active it is and how healthy it looks."
        />
      </>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Insights"
        icon={<BarChart3 />}
        info="Built from the default branch history Docify indexed, plus live GitHub data (stars, languages, pull requests) refreshed hourly."
        actions={
          <div className="flex items-center gap-2">
            <Select
              size="sm"
              aria-label="Repository"
              value={repoId}
              onChange={(e) =>
                setParams({ repo: e.target.value }, { replace: true })
              }
              options={ready.map((r) => ({ value: r.id, label: r.full_name }))}
              className="w-56"
            />
            {isMember && (
              <IconButton
                size="sm"
                label="Refresh GitHub data"
                icon={
                  <RefreshCw
                    className={refreshing ? "animate-spin" : undefined}
                  />
                }
                onClick={() => void refresh()}
              />
            )}
          </div>
        }
      />
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <InsightsSkeleton />
      ) : (
        <InsightsBody data={q.data} onPerson={setPerson} />
      )}
      <Drawer
        open={!!person}
        onOpenChange={(o) => !o && setPerson(null)}
        title={person ? personLabel(person) : ""}
        className="w-full sm:w-[420px]"
      >
        {person && q.data && (
          <PersonDetail p={person} repo={q.data.repo.full_name} />
        )}
      </Drawer>
    </div>
  );
}

function InsightsSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className={i < 4 ? "h-16" : "h-48 sm:col-span-2"} />
      ))}
    </div>
  );
}

function InsightsBody({
  data,
  onPerson,
}: {
  data: InsightsData;
  onPerson: (p: Person) => void;
}) {
  const t = data.totals;
  const gh = data.github;
  const weeks = data.weekly_commits.map((w, i) => ({
    key: w.week_start,
    label: new Date(w.week_start).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }),
    value: w.commits,
    tip: `Week of ${new Date(w.week_start).toLocaleDateString()} · ${w.commits} commit${w.commits === 1 ? "" : "s"}`,
    i,
  }));
  const languages = useMemo(() => {
    if (gh && Object.keys(gh.languages).length) {
      const total = Object.values(gh.languages).reduce((a, b) => a + b, 0) || 1;
      return Object.entries(gh.languages)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(([lang, bytes]) => ({
          key: lang,
          label: lang,
          value: Math.round((bytes / total) * 1000) / 10,
          tip: `${lang}: ${(bytes / 1024).toFixed(1)} KB`,
        }));
    }
    return data.languages
      .slice(0, 8)
      .map((l) => ({
        key: l.language,
        label: l.language,
        value: l.lines,
        sub: `${l.files} files`,
      }));
  }, [gh, data.languages]);
  const usingBytes = !!(gh && Object.keys(gh.languages).length);

  const kpis = [
    {
      label: "Commits",
      value: t.commits,
      icon: <GitCommitHorizontal />,
      info: "Commits on the default branch that Docify has indexed (up to the latest 300 at first connect).",
    },
    {
      label: "Contributors",
      value: t.contributors,
      icon: <Users />,
      info: "People with at least one commit.",
    },
    {
      label: "Merged PRs",
      value: gh?.pulls.merged ?? t.prs_merged,
      icon: <GitMerge />,
      info: "Merged pull requests (GitHub), or PR numbers seen in commit messages.",
    },
    {
      label: "Lines of code",
      value: t.lines,
      icon: <FileCode2 />,
      info: `${t.files} indexed files (generated, vendored and binary files are skipped).`,
    },
  ];

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {/* Health + KPIs */}
      <motion.div {...fade(0)} className="lg:col-span-1">
        <Card className="flex h-full items-center gap-4 p-4">
          <ScoreRing
            score={data.health.score}
            label={`Grade ${data.health.grade}`}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1 text-sm font-semibold">
              Repository health
              <InfoTip>
                Starts at 100 and loses points for: no recent commits, bus
                factor 1, unpublished docs, open policy findings and open
                issues.
              </InfoTip>
            </div>
            <ul className="mt-1.5 flex flex-col gap-1">
              {data.health.notes.slice(0, 3).map((n) => (
                <li key={n} className="flex gap-1.5 text-xs text-fg-muted">
                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-fg-subtle" />
                  {n}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </motion.div>
      <div className="grid grid-cols-2 gap-3 lg:col-span-2">
        {kpis.map((k, i) => (
          <motion.div key={k.label} {...fade(i + 1)}>
            <Kpi {...k} />
          </motion.div>
        ))}
      </div>

      {/* Activity */}
      <motion.div {...fade(5)} className="lg:col-span-2">
        <Card className="h-full">
          <CardHeader
            title="Commit activity"
            icon={<Activity />}
            info="Commits per week over the last 26 weeks."
            meta={
              t.last_commit ? (
                <span>
                  Last commit <RelativeTime iso={t.last_commit} />
                </span>
              ) : undefined
            }
          />
          <CardBody>
            <ColumnChart
              data={weeks}
              ariaLabel="Commits per week, last 26 weeks"
              xLabels={[0, 8, 17, 25]}
            />
          </CardBody>
        </Card>
      </motion.div>
      <motion.div {...fade(6)}>
        <Card className="h-full">
          <CardHeader title="At a glance" icon={<Eye />} />
          <CardBody className="grid grid-cols-2 gap-x-3 gap-y-2.5 text-xs">
            <Fact icon={<Star />} label="Stars" value={gh?.stars} />
            <Fact icon={<GitFork />} label="Forks" value={gh?.forks} />
            <Fact
              icon={<GitPullRequest />}
              label="Open PRs"
              value={gh?.pulls.open}
            />
            <Fact
              icon={<ShieldAlert />}
              label="Open findings"
              value={t.open_findings}
            />
            <Fact
              icon={<Users />}
              label="Bus factor"
              value={t.bus_factor}
              info="Fewest people who wrote half of the commits. 1 = a single point of failure."
            />
            <Fact
              icon={<GitMerge />}
              label="Avg. time to merge"
              value={
                gh?.pulls.avg_hours_to_merge != null
                  ? `${gh.pulls.avg_hours_to_merge} h`
                  : undefined
              }
            />
            <Fact icon={<Scale />} label="License" value={gh?.license ?? "—"} />
            <Fact
              icon={<GitCommitHorizontal />}
              label="+ / − lines"
              value={`+${t.additions.toLocaleString()} / −${t.deletions.toLocaleString()}`}
            />
          </CardBody>
          {gh?.topics?.length ? (
            <div className="flex flex-wrap gap-1 border-t border-border px-3 py-2">
              {gh.topics.slice(0, 8).map((tp) => (
                <Badge key={tp} tone="accent">
                  {tp}
                </Badge>
              ))}
            </div>
          ) : null}
        </Card>
      </motion.div>

      {/* Contributors */}
      <motion.div {...fade(7)} className="lg:col-span-2">
        <Card>
          <CardHeader
            title="Who did what"
            icon={<Users />}
            info="Share of commits, lines added/removed, files and the areas (top-level folders) each person works on. Click a person for their recent commits."
          />
          <ul className="divide-y divide-border">
            {data.contributors.slice(0, 12).map((p, i) => (
              <motion.li key={p.login ?? p.name} {...fade(i)}>
                <button
                  type="button"
                  onClick={() => onPerson(p)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none"
                >
                  <Avatar src={githubAvatar(p.login)} name={p.name} size={28} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {p.name}
                      </span>
                      {p.login && (
                        <span className="truncate text-xs text-fg-subtle">
                          @{p.login}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                        <motion.div
                          className="h-full rounded-full bg-accent"
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(2, p.share * 100)}%` }}
                          transition={{ duration: 0.6, delay: 0.1 + i * 0.04 }}
                        />
                      </div>
                      <span className="tabular w-10 text-right text-2xs text-fg-subtle">
                        {Math.round(p.share * 100)}%
                      </span>
                    </div>
                    <div className="mt-1 hidden flex-wrap gap-1 sm:flex">
                      {p.top_areas.map((a) => (
                        <span
                          key={a.area}
                          className="rounded bg-surface-2 px-1.5 py-px font-mono text-[10px] text-fg-muted"
                        >
                          {a.area}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="hidden shrink-0 text-right text-xs sm:block">
                    <div className="tabular font-medium">
                      {p.commits} commits
                    </div>
                    <div className="tabular text-fg-subtle">
                      <span className="text-success">
                        +{p.additions.toLocaleString()}
                      </span>{" "}
                      <span className="text-danger">
                        −{p.deletions.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </button>
              </motion.li>
            ))}
          </ul>
        </Card>
      </motion.div>

      <motion.div {...fade(8)} className="flex flex-col gap-3">
        <Card>
          <CardHeader
            title="Languages"
            icon={<FileCode2 />}
            info={
              usingBytes
                ? "Share of code by bytes (GitHub)."
                : "Lines of code per language in the indexed files."
            }
          />
          <CardBody>
            <BarList
              items={languages}
              format={usingBytes ? (n) => `${n}%` : undefined}
            />
          </CardBody>
        </Card>
        {gh && gh.pulls.total > 0 && (
          <Card>
            <CardHeader
              title="Pull requests"
              icon={<GitPullRequest />}
              meta={`${gh.pulls.total} recent`}
            />
            <ul className="divide-y divide-border">
              {gh.pulls.recent.slice(0, 5).map((pr) => (
                <li key={pr.number}>
                  <a
                    href={pr.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-surface-2"
                  >
                    {pr.merged ? (
                      <GitMerge className="size-3.5 shrink-0 text-accent-text" />
                    ) : (
                      <GitPullRequest className="size-3.5 shrink-0 text-fg-subtle" />
                    )}
                    <span className="min-w-0 flex-1 truncate">
                      <span className="text-fg-subtle">#{pr.number}</span>{" "}
                      {pr.title}
                    </span>
                    {pr.author && (
                      <span className="shrink-0 text-fg-subtle">
                        @{pr.author}
                      </span>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </motion.div>

      <motion.div {...fade(9)} className="lg:col-span-2">
        <Card>
          <CardHeader
            title="When people commit"
            icon={<Activity />}
            info="Commits by weekday and hour, in UTC."
          />
          <CardBody>
            <Heatmap cells={data.heatmap} />
          </CardBody>
        </Card>
      </motion.div>
      <motion.div {...fade(10)}>
        <Card className="h-full">
          <CardHeader
            title="Hot files"
            icon={<FileCode2 />}
            info="Files changed most often. Many changes by many people = a good place for tests and docs."
          />
          <CardBody>
            <BarList
              mono
              items={data.hot_files.slice(0, 8).map((f) => ({
                key: f.path,
                label: f.path,
                value: f.changes,
                tip: `${f.path}: ${f.changes} changes by ${f.authors} ${f.authors === 1 ? "person" : "people"}`,
              }))}
            />
          </CardBody>
        </Card>
      </motion.div>
    </div>
  );
}

function Kpi({
  label,
  value,
  icon,
  info,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  info: string;
}) {
  return (
    <Card className="group flex h-full items-center gap-3 px-3 py-3 transition-shadow hover:shadow-md">
      <span className="grid size-8 place-items-center rounded-lg bg-accent-soft text-accent-text transition-transform group-hover:scale-105 [&_svg]:size-4">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-1 text-xs text-fg-subtle">
          {label}
          <InfoTip>{info}</InfoTip>
        </div>
        <div className="tabular text-xl font-semibold leading-tight">
          <CountUp value={value} />
        </div>
      </div>
    </Card>
  );
}

function Fact({
  icon,
  label,
  value,
  info,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  info?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-fg-subtle [&_svg]:size-3.5">{icon}</span>
      <div className="min-w-0">
        <div className="flex items-center gap-1 text-2xs text-fg-subtle">
          {label}
          {info && <InfoTip>{info}</InfoTip>}
        </div>
        <div className="tabular truncate text-sm font-medium">
          {value ?? "—"}
        </div>
      </div>
    </div>
  );
}

function PersonDetail({ p, repo }: { p: Person; repo: string }) {
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-3">
        <Avatar src={githubAvatar(p.login, 96)} name={p.name} size={48} />
        <div>
          <div className="font-semibold">{p.name}</div>
          {p.login && (
            <a
              className="text-xs text-accent-text hover:underline"
              href={`https://github.com/${p.login}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              @{p.login}
            </a>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          ["Commits", p.commits],
          ["Files", p.files_touched],
          ["PRs", p.prs],
        ].map(([l, v]) => (
          <div key={l} className="rounded-md bg-surface-2 py-2">
            <div className="tabular text-lg font-semibold">{v}</div>
            <div className="text-2xs text-fg-subtle">{l}</div>
          </div>
        ))}
      </div>
      <div className="text-xs text-fg-muted">
        Active <RelativeTime iso={p.first_commit} /> →{" "}
        <RelativeTime iso={p.last_commit} /> ·{" "}
        <span className="text-success">+{p.additions.toLocaleString()}</span>{" "}
        <span className="text-danger">−{p.deletions.toLocaleString()}</span>
      </div>
      <div>
        <div className="mb-1.5 text-xs font-medium text-fg-subtle">
          Works on
        </div>
        <BarList
          mono
          items={p.top_areas.map((a) => ({
            key: a.area,
            label: a.area,
            value: a.changes,
          }))}
        />
      </div>
      <div>
        <div className="mb-1.5 text-xs font-medium text-fg-subtle">
          Recent commits
        </div>
        <ul className="flex flex-col gap-1">
          {p.recent_commits.map((c) => (
            <li key={c.sha}>
              <Tooltip content={new Date(c.date).toLocaleString()}>
                <a
                  href={`https://github.com/${repo}/commit/${c.sha}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors hover:bg-surface-2"
                >
                  <code className="shrink-0 text-accent-text">
                    {shortSha(c.sha)}
                  </code>
                  <span className="min-w-0 flex-1 truncate">{c.title}</span>
                  {c.pr && <Badge>#{c.pr}</Badge>}
                </a>
              </Tooltip>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
