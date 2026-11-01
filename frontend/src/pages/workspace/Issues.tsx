import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bug,
  CircleDot,
  Download,
  ExternalLink,
  FileCode2,
  Plus,
  ShieldAlert,
  Sparkles,
  Trash2,
  UserCheck,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import {
  insights,
  issues as issuesApi,
  qk,
  repos as reposApi,
} from "@/api/endpoints";
import type { Issue, IssueStatus, Severity, Suspect } from "@/api/types";
import { GitHubIcon } from "@/components/BrandIcons";
import { Markdown } from "@/components/Markdown";
import {
  Avatar,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  Dialog,
  Drawer,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  InfoTip,
  Input,
  PageHeader,
  RelativeTime,
  Select,
  SkeletonRows,
  Tabs,
  Textarea,
  Tooltip,
  useToast,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";
import {
  SEVERITIES,
  githubAvatar,
  issueStatusLabel,
  issueStatusTone,
  personLabel,
  severityLabel,
  severityTone,
} from "@/lib/quality";

type Filter = "active" | "open" | "in_progress" | "done" | "all";
const FILTER_STATUS: Record<Filter, string | undefined> = {
  active: "open,in_progress",
  open: "open",
  in_progress: "in_progress",
  done: "resolved,closed",
  all: undefined,
};

const SOURCE_ICON = {
  github: <GitHubIcon className="size-3.5" />,
  finding: <ShieldAlert className="size-3.5" />,
  docify: <CircleDot className="size-3.5" />,
};
const SOURCE_TIP = {
  github: "Imported from GitHub",
  finding: "Created from a policy finding",
  docify: "Reported in Docify",
};

export default function Issues() {
  const { ws, slug, isMember } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Issues" }]);
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("active");
  const [assignee, setAssignee] = useState("");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const openId = params.get("open");
  const status = FILTER_STATUS[filter];
  const key = `${status ?? "all"}|${assignee}`;
  const q = useQuery({
    queryKey: qk.issues(slug, key),
    queryFn: () =>
      issuesApi.list(slug, { status, assignee: assignee || undefined }),
  });
  const people = useQuery({
    queryKey: qk.contributors(slug),
    queryFn: () => insights.contributors(slug),
  });
  const open = (id: string | null) =>
    setParams(id ? { open: id } : {}, { replace: true });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Issues"
        icon={<Bug />}
        info="Report a bug or import one from GitHub. Docify reads the code and git history to suggest who most likely introduced it, with evidence, so you can assign it to the right person."
        actions={
          isMember && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setImporting(true)}
              >
                <GitHubIcon className="size-3.5" />{" "}
                <span className="hidden sm:inline">Import from GitHub</span>
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={() => setCreating(true)}
              >
                <Plus /> New issue
              </Button>
            </div>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <div className="-mx-1 max-w-full overflow-x-auto px-1 pb-0.5">
          <Tabs
            value={filter}
            onValueChange={setFilter}
            ariaLabel="Issue status"
            items={[
              { value: "active", label: "Active" },
              { value: "open", label: "Open" },
              { value: "in_progress", label: "In progress" },
              { value: "done", label: "Done" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
        <Select
          size="sm"
          aria-label="Assignee"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
          className="ml-auto w-44"
          options={[
            { value: "", label: "Any assignee" },
            ...(people.data ?? [])
              .filter((p) => p.login)
              .map((p) => ({ value: p.login!, label: `@${p.login}` })),
          ]}
        />
      </div>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <Card className="p-3">
          <SkeletonRows rows={5} />
        </Card>
      ) : q.data.length === 0 ? (
        <EmptyState
          icon={<Bug />}
          title="No issues here"
          info="Create one, import from GitHub, or turn a policy finding into an issue from Checks."
          action={
            isMember ? (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setCreating(true)}
              >
                <Plus /> New issue
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <motion.ul
            className="divide-y divide-border"
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.03 } } }}
          >
            {q.data.map((i) => (
              <motion.li
                key={i.id}
                variants={{
                  hidden: { opacity: 0, x: -6 },
                  show: { opacity: 1, x: 0 },
                }}
              >
                <IssueRow issue={i} onOpen={() => open(i.id)} />
              </motion.li>
            ))}
          </motion.ul>
        </Card>
      )}
      <Drawer
        open={!!openId}
        onOpenChange={(o) => !o && open(null)}
        title="Issue"
        className="w-full sm:w-[520px]"
      >
        {openId && <IssueDetail id={openId} onClose={() => open(null)} />}
      </Drawer>
      <NewIssueDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(i) => open(i.id)}
      />
      <ImportDialog
        open={importing}
        onOpenChange={setImporting}
        onImported={(i) => open(i.id)}
      />
    </div>
  );
}

function IssueRow({ issue: i, onOpen }: { issue: Issue; onOpen: () => void }) {
  const top = i.suspects[0];
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none"
    >
      <Tooltip content={SOURCE_TIP[i.source]}>
        <span className="text-fg-subtle">{SOURCE_ICON[i.source]}</span>
      </Tooltip>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="tabular text-xs text-fg-subtle">#{i.number}</span>
          <span className="truncate text-sm font-medium">{i.title}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-2xs text-fg-subtle">
          <Badge tone={severityTone[i.severity]}>
            {severityLabel[i.severity]}
          </Badge>
          <Badge tone={issueStatusTone[i.status]}>
            {issueStatusLabel[i.status]}
          </Badge>
          {i.repo_full_name && (
            <span className="truncate">{i.repo_full_name}</span>
          )}
          <RelativeTime iso={i.created_at} />
        </div>
      </div>
      {i.assignee_login ? (
        <Tooltip content={`Assigned to @${i.assignee_login}`}>
          <span className="flex items-center gap-1 text-xs text-fg-muted">
            <UserCheck className="size-3.5 text-success" />
            <Avatar
              src={githubAvatar(i.assignee_login)}
              name={i.assignee_login}
              size={22}
            />
          </span>
        </Tooltip>
      ) : top ? (
        <Tooltip
          content={`Likely owner: ${personLabel(top)} (${Math.round(top.confidence * 100)}%)`}
        >
          <span className="flex items-center gap-1 text-xs text-fg-subtle">
            <Sparkles className="size-3.5 text-accent-text" />
            <Avatar
              src={githubAvatar(top.login)}
              name={top.name}
              size={22}
              className="opacity-80"
            />
          </span>
        </Tooltip>
      ) : null}
    </button>
  );
}

function IssueDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { slug, isMember, isAdmin } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: qk.issue(id),
    queryFn: () => issuesApi.get(id),
  });
  const [deleting, setDeleting] = useState(false);
  const sync = (i: Issue) => {
    qc.setQueryData(qk.issue(id), i);
    void qc.invalidateQueries({ queryKey: ["ws", slug, "issues"] });
  };
  const update = useMutation({
    mutationFn: (body: Parameters<typeof issuesApi.update>[1]) =>
      issuesApi.update(id, body),
    onSuccess: (i, body) => {
      sync(i);
      if (body.assignee_login)
        toast.success(`Assigned to @${body.assignee_login}`);
    },
    onError: (e) => toast.error("Couldn't update the issue", errorMessage(e)),
  });
  const analyze = useMutation({
    mutationFn: () => issuesApi.analyze(id),
    onSuccess: (i) => {
      sync(i);
      toast.success("Analysis updated");
    },
    onError: (e) => toast.error("Analysis failed", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => issuesApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ws", slug, "issues"] });
      toast.success("Issue deleted");
      onClose();
    },
  });

  if (q.isError)
    return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data)
    return (
      <div className="p-4">
        <SkeletonRows rows={6} />
      </div>
    );
  const i = q.data;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <div className="flex items-center gap-2 text-xs text-fg-subtle">
          <span className="tabular">#{i.number}</span>
          <span className="flex items-center gap-1">
            {SOURCE_ICON[i.source]} {SOURCE_TIP[i.source]}
          </span>
          {i.github_url && (
            <a
              href={i.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-0.5 text-accent-text hover:underline"
            >
              GitHub #{i.github_number} <ExternalLink className="size-3" />
            </a>
          )}
        </div>
        <h2 className="mt-1 text-base font-semibold leading-snug">{i.title}</h2>
        <div className="mt-1 text-2xs text-fg-subtle">
          {i.repo_full_name ?? "All repositories"} · opened{" "}
          <RelativeTime iso={i.created_at} />
          {i.github_author && <> by @{i.github_author}</>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Status">
          <Select
            size="sm"
            disabled={!isMember}
            value={i.status}
            onChange={(e) =>
              update.mutate({ status: e.target.value as IssueStatus })
            }
            options={(
              ["open", "in_progress", "resolved", "closed"] as IssueStatus[]
            ).map((s) => ({ value: s, label: issueStatusLabel[s] }))}
          />
        </Field>
        <Field label="Severity">
          <Select
            size="sm"
            disabled={!isMember}
            value={i.severity}
            onChange={(e) =>
              update.mutate({ severity: e.target.value as Severity })
            }
            options={SEVERITIES.map((s) => ({
              value: s,
              label: severityLabel[s],
            }))}
          />
        </Field>
      </div>

      <Card className="flex items-center gap-2 px-3 py-2">
        {i.assignee_login ? (
          <>
            <Avatar
              src={githubAvatar(i.assignee_login)}
              name={i.assignee_login}
              size={26}
            />
            <div className="min-w-0 flex-1 text-sm">
              <div className="font-medium">@{i.assignee_login}</div>
              <div className="text-2xs text-fg-subtle">
                Assigned <RelativeTime iso={i.assigned_at} />
              </div>
            </div>
            {isMember && (
              <IconButton
                size="sm"
                label="Unassign"
                icon={<UserMinus />}
                onClick={() => update.mutate({ unassign: true })}
              />
            )}
          </>
        ) : (
          <>
            <UserPlus className="size-4 text-fg-subtle" />
            <span className="flex-1 text-sm text-fg-muted">
              Not assigned yet
            </span>
          </>
        )}
      </Card>

      <section>
        <div className="mb-2 flex items-center gap-1.5">
          <Sparkles className="size-4 text-accent-text" />
          <h3 className="text-sm font-semibold">Likely responsible</h3>
          <InfoTip>
            Ranked from: the author of a linked policy finding, git blame of the
            files the issue mentions, blame of the code that best matches the
            issue text, and commits whose message matches it. Check the evidence
            before assigning.
          </InfoTip>
          {isMember && (
            <Button
              size="xs"
              variant="ghost"
              className="ml-auto"
              loading={analyze.isPending}
              onClick={() => analyze.mutate()}
            >
              Re-analyse
            </Button>
          )}
        </div>
        {i.suspects.length === 0 ? (
          <p className="rounded-md bg-surface-2 px-3 py-2 text-xs text-fg-muted">
            No clear owner yet. Mention a file (e.g. <code>src/app.ts</code>) or
            more detail, then re-analyse.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {i.suspects.map((s, idx) => (
              <SuspectCard
                key={s.login ?? s.name}
                s={s}
                rank={idx}
                canAssign={
                  isMember && !!s.login && s.login !== i.assignee_login
                }
                onAssign={() =>
                  s.login && update.mutate({ assignee_login: s.login })
                }
              />
            ))}
          </ul>
        )}
      </section>

      {i.paths.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {i.paths.map((p) => (
            <span
              key={p}
              className="flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-fg-muted"
            >
              <FileCode2 className="size-3" /> {p}
            </span>
          ))}
        </div>
      )}
      {i.body && (
        <section>
          <h3 className="mb-1.5 text-sm font-semibold">Description</h3>
          <div className="rounded-md border border-border p-3">
            <Markdown compact>{i.body}</Markdown>
          </div>
        </section>
      )}
      {isAdmin && (
        <Button
          size="sm"
          variant="ghost"
          className="self-start text-danger"
          onClick={() => setDeleting(true)}
        >
          <Trash2 /> Delete issue
        </Button>
      )}
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={`Delete issue #${i.number}?`}
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

function SuspectCard({
  s,
  rank,
  canAssign,
  onAssign,
}: {
  s: Suspect;
  rank: number;
  canAssign: boolean;
  onAssign: () => void;
}) {
  const [more, setMore] = useState(rank === 0);
  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: rank * 0.06 }}
    >
      <Card className={rank === 0 ? "ring-1 ring-accent/30" : undefined}>
        <div className="flex items-center gap-2.5 px-3 py-2">
          <Avatar src={githubAvatar(s.login)} name={s.name} size={28} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-sm">
              <span className="truncate font-medium">{s.name}</span>
              {s.login && (
                <span className="truncate text-xs text-fg-subtle">
                  @{s.login}
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                <motion.div
                  className="h-full rounded-full bg-accent"
                  initial={{ width: 0 }}
                  animate={{ width: `${s.confidence * 100}%` }}
                  transition={{ duration: 0.6, delay: 0.1 + rank * 0.06 }}
                />
              </div>
              <Tooltip content="Relative confidence: 100% = the strongest candidate">
                <span className="tabular w-9 text-right text-2xs text-fg-subtle">
                  {Math.round(s.confidence * 100)}%
                </span>
              </Tooltip>
            </div>
          </div>
          {canAssign && (
            <Button
              size="xs"
              variant={rank === 0 ? "primary" : "secondary"}
              onClick={onAssign}
            >
              <UserPlus /> Assign
            </Button>
          )}
        </div>
        <AnimatePresence initial={false}>
          {more && (
            <motion.ul
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden border-t border-border"
            >
              {s.reasons.map((r) => (
                <li
                  key={r.text}
                  className="px-3 py-1.5 text-2xs leading-relaxed text-fg-muted"
                >
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-accent-text"
                    >
                      {r.text}
                    </a>
                  ) : (
                    r.text
                  )}
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
        <button
          type="button"
          onClick={() => setMore((m) => !m)}
          className="w-full border-t border-border py-1 text-2xs text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg-muted"
        >
          {more ? "Hide evidence" : `Show evidence (${s.reasons.length})`}
        </button>
      </Card>
    </motion.li>
  );
}

function NewIssueDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (i: Issue) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New issue" size="md">
      {open && (
        <NewIssueForm onOpenChange={onOpenChange} onCreated={onCreated} />
      )}
    </Dialog>
  );
}

function NewIssueForm({
  onOpenChange,
  onCreated,
}: {
  onOpenChange: (o: boolean) => void;
  onCreated: (i: Issue) => void;
}) {
  const open = true;
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const reposQ = useQuery({
    queryKey: qk.repos(slug),
    queryFn: () => reposApi.list(slug),
    enabled: open,
  });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [repo, setRepo] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [paths, setPaths] = useState("");
  const create = useMutation({
    mutationFn: () =>
      issuesApi.create(slug, {
        title,
        body: body || null,
        repo_id: repo || null,
        severity,
        paths: paths
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean),
      }),
    onSuccess: (i) => {
      void qc.invalidateQueries({ queryKey: ["ws", slug, "issues"] });
      toast.success(
        `Issue #${i.number} created`,
        i.suspects[0]
          ? `Likely owner: ${personLabel(i.suspects[0])}`
          : undefined,
      );
      onOpenChange(false);
      onCreated(i);
    },
    onError: (e) => toast.error("Couldn't create the issue", errorMessage(e)),
  });
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Field label="Title">
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Reset button doesn't clear the result"
          required
          minLength={3}
          autoFocus
        />
      </Field>
      <Field
        label="What happens?"
        info="Steps, expected vs actual. Mentioning files or functions helps Docify find who changed that code."
      >
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={5}
          placeholder="After clicking Reset the old total stays visible (script.js)."
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Repository">
          <Select
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            options={[
              { value: "", label: "Any" },
              ...(reposQ.data ?? []).map((r) => ({
                value: r.id,
                label: r.full_name,
              })),
            ]}
          />
        </Field>
        <Field label="Severity">
          <Select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity)}
            options={SEVERITIES.map((s) => ({
              value: s,
              label: severityLabel[s],
            }))}
          />
        </Field>
      </div>
      <Field
        label="Files (optional)"
        info="Comma-separated paths. Their git blame weighs most when ranking who's responsible."
      >
        <Input
          value={paths}
          onChange={(e) => setPaths(e.target.value)}
          placeholder="script.js, index.html"
        />
      </Field>
      <div className="flex justify-end gap-2 pt-1">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onOpenChange(false)}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          variant="primary"
          loading={create.isPending}
        >
          <Sparkles /> Create & analyse
        </Button>
      </div>
    </form>
  );
}

function ImportDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onImported: (i: Issue) => void;
}) {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const reposQ = useQuery({
    queryKey: qk.repos(slug),
    queryFn: () => reposApi.list(slug),
    enabled: open,
  });
  const ready = (reposQ.data ?? []).filter((r) => r.status === "ready");
  const [repo, setRepo] = useState("");
  const [state, setState] = useState<"open" | "closed" | "all">("open");
  const repoId = repo || ready[0]?.id || "";
  const list = useQuery({
    queryKey: qk.githubIssues(slug, repoId, state),
    queryFn: () => issuesApi.github(slug, repoId, state),
    enabled: open && !!repoId,
    retry: false,
  });
  const imp = useMutation({
    mutationFn: (n: number) => issuesApi.importGithub(slug, repoId, n),
    onSuccess: (i) => {
      void qc.invalidateQueries({ queryKey: ["ws", slug] });
      toast.success(`Imported as #${i.number}`);
      onOpenChange(false);
      onImported(i);
    },
    onError: (e) => toast.error("Import failed", errorMessage(e)),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Import from GitHub"
      size="md"
    >
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <Select
            size="sm"
            aria-label="Repository"
            value={repoId}
            onChange={(e) => setRepo(e.target.value)}
            options={ready.map((r) => ({ value: r.id, label: r.full_name }))}
          />
          <Select
            size="sm"
            aria-label="State"
            value={state}
            onChange={(e) => setState(e.target.value as typeof state)}
            options={[
              { value: "open", label: "Open" },
              { value: "closed", label: "Closed" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
        {list.isError ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        ) : !list.data ? (
          <SkeletonRows rows={4} />
        ) : list.data.length === 0 ? (
          <EmptyState
            compact
            icon={<GitHubIcon className="size-5" />}
            title="No GitHub issues"
            info="Nothing in this state on GitHub."
          />
        ) : (
          <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-md border border-border">
            {list.data.map((g) => (
              <li key={g.number} className="flex items-center gap-2 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">
                    <span className="text-fg-subtle">#{g.number}</span>{" "}
                    {g.title}
                  </div>
                  <div className="flex flex-wrap items-center gap-1 text-2xs text-fg-subtle">
                    {g.author && <span>@{g.author}</span>}
                    <RelativeTime iso={g.created_at} />
                    {g.labels.slice(0, 3).map((l) => (
                      <Badge key={l}>{l}</Badge>
                    ))}
                  </div>
                </div>
                {g.imported_issue_number != null ? (
                  <Badge tone="success">#{g.imported_issue_number}</Badge>
                ) : (
                  <Button
                    size="xs"
                    loading={imp.isPending && imp.variables === g.number}
                    onClick={() => imp.mutate(g.number)}
                  >
                    <Download /> Import
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
