import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bug,
  CheckCircle2,
  CircleSlash,
  Eye,
  FlaskConical,
  GitCommitHorizontal,
  MoreHorizontal,
  Pencil,
  Plus,
  RotateCcw,
  ScanSearch,
  ShieldCheck,
  Trash2,
  UserPlus,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import {
  findings as findingsApi,
  insights,
  policies as policiesApi,
  qk,
  repos as reposApi,
} from "@/api/endpoints";
import type {
  Finding,
  FindingStatus,
  Policy,
  PolicyIn,
  Severity,
} from "@/api/types";
import {
  Avatar,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  Dialog,
  DropdownMenu,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  PageHeader,
  RelativeTime,
  Select,
  SkeletonRows,
  Switch,
  Tabs,
  Textarea,
  Tooltip,
  useToast,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";
import {
  SEVERITIES,
  findingStatusLabel,
  findingStatusTone,
  githubAvatar,
  personLabel,
  severityLabel,
  severityTone,
  shortSha,
} from "@/lib/quality";

type Tab = "findings" | "policies";
type StatusFilter =
  "open" | "acknowledged" | "resolved" | "false_positive" | "all";

export default function Checks() {
  const { ws, slug, isAdmin } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Checks" }]);
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "findings";
  const qc = useQueryClient();
  const toast = useToast();

  const scan = useMutation({
    mutationFn: () => policiesApi.scan(slug),
    onSuccess: (r) => {
      toast.success(
        r.findings_created
          ? `${r.findings_created} new finding${r.findings_created === 1 ? "" : "s"}`
          : "No new findings",
        `Scanned ${r.repos} repositor${r.repos === 1 ? "y" : "ies"}.`,
      );
      void qc.invalidateQueries({ queryKey: ["ws", slug, "findings"] });
    },
    onError: (e) => toast.error("Scan failed", errorMessage(e)),
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Checks"
        icon={<ShieldCheck />}
        info="Every push and merged PR is checked against your policies. Each finding shows who added the line and in which commit, so it can go straight to the right person."
        actions={
          isAdmin && (
            <Tooltip content="Check the current code of every repository against all enabled policies">
              <Button
                size="sm"
                variant="secondary"
                loading={scan.isPending}
                onClick={() => scan.mutate()}
              >
                <ScanSearch /> Scan now
              </Button>
            </Tooltip>
          )
        }
      />
      <Tabs
        variant="underline"
        value={tab}
        onValueChange={(v) => setParams({ tab: v }, { replace: true })}
        items={[
          { value: "findings", label: "Findings", icon: <Bug /> },
          { value: "policies", label: "Policies", icon: <ShieldCheck /> },
        ]}
      />
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.18 }}
        >
          {tab === "findings" ? <Findings /> : <Policies />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ----------------------------------------------------------------------------- findings

function Findings() {
  const { slug, isMember } = useWorkspace();
  const [status, setStatus] = useState<StatusFilter>("open");
  const [severity, setSeverity] = useState("");
  const [repo, setRepo] = useState("");
  const [author, setAuthor] = useState("");
  const filters = {
    status: status === "all" ? undefined : status,
    severity: severity || undefined,
    repo: repo || undefined,
    author: author || undefined,
  };
  const key = JSON.stringify(filters);
  const q = useQuery({
    queryKey: qk.findings(slug, key),
    queryFn: () => findingsApi.list(slug, filters),
  });
  const reposQ = useQuery({
    queryKey: qk.repos(slug),
    queryFn: () => reposApi.list(slug),
  });
  const people = useQuery({
    queryKey: qk.contributors(slug),
    queryFn: () => insights.contributors(slug),
  });
  const counts = q.data?.counts ?? {};

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="-mx-1 max-w-full overflow-x-auto px-1 pb-0.5">
          <Tabs
            value={status}
            onValueChange={setStatus}
            items={[
              { value: "open", label: "Open", count: counts.open ?? 0 },
              {
                value: "acknowledged",
                label: "Acknowledged",
                count: counts.acknowledged ?? 0,
              },
              {
                value: "resolved",
                label: "Resolved",
                count: counts.resolved ?? 0,
              },
              {
                value: "false_positive",
                label: "False positive",
                count: counts.false_positive ?? 0,
              },
              { value: "all", label: "All" },
            ]}
            ariaLabel="Finding status"
          />
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto">
          <Select
            size="sm"
            aria-label="Severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="w-32"
            options={[
              { value: "", label: "Any severity" },
              ...SEVERITIES.map((s) => ({ value: s, label: severityLabel[s] })),
            ]}
          />
          <Select
            size="sm"
            aria-label="Repository"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            className="w-44"
            options={[
              { value: "", label: "All repositories" },
              ...(reposQ.data ?? []).map((r) => ({
                value: r.id,
                label: r.full_name,
              })),
            ]}
          />
          <Select
            size="sm"
            aria-label="Author"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="w-40"
            options={[
              { value: "", label: "Anyone" },
              ...(people.data ?? []).map((p) => ({
                value: p.login ?? p.name,
                label: personLabel(p),
              })),
            ]}
          />
        </div>
      </div>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <Card className="p-3">
          <SkeletonRows rows={4} />
        </Card>
      ) : q.data.items.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 />}
          title={status === "open" ? "No open findings" : "Nothing here"}
          info="New pushes are checked automatically. Admins can also scan the current code with Scan now."
        />
      ) : (
        <motion.ul
          className="flex flex-col gap-2"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.035 } } }}
        >
          {q.data.items.map((f) => (
            <motion.li
              key={f.id}
              variants={{
                hidden: { opacity: 0, y: 6 },
                show: { opacity: 1, y: 0 },
              }}
            >
              <FindingCard
                f={f}
                canEdit={isMember}
                people={(people.data ?? []).map((p) => p.login ?? p.name)}
              />
            </motion.li>
          ))}
        </motion.ul>
      )}
    </div>
  );
}

function FindingCard({
  f,
  canEdit,
  people,
}: {
  f: Finding;
  canEdit: boolean;
  people: string[];
}) {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: ["ws", slug, "findings"] });
  const update = useMutation({
    mutationFn: (body: { status?: FindingStatus; assignee_login?: string }) =>
      findingsApi.update(f.id, body),
    onSuccess: () => refresh(),
    onError: (e) => toast.error("Couldn't update the finding", errorMessage(e)),
  });
  const toIssue = useMutation({
    mutationFn: () => findingsApi.toIssue(f.id),
    onSuccess: (issue) => {
      toast.success(
        `Issue #${issue.number} created`,
        issue.suspects[0]
          ? `Suggested owner: ${personLabel(issue.suspects[0])}`
          : undefined,
      );
      refresh();
      void qc.invalidateQueries({ queryKey: ["ws", slug, "issues"] });
      navigate(`/w/${slug}/issues?open=${issue.id}`);
    },
    onError: (e) => toast.error("Couldn't create the issue", errorMessage(e)),
  });
  const who = f.author_login || f.author_name;

  return (
    <Card className="group overflow-hidden transition-shadow hover:shadow-md">
      <div className="flex items-start gap-3 p-3">
        <span
          className={`mt-1 h-8 w-1 shrink-0 rounded-full ${f.severity === "critical" || f.severity === "high" ? "bg-danger" : f.severity === "medium" ? "bg-warning" : "bg-info"}`}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={severityTone[f.severity]}>
              {severityLabel[f.severity]}
            </Badge>
            <span className="text-sm font-medium">{f.policy_name}</span>
            {f.status !== "open" && (
              <Badge tone={findingStatusTone[f.status]}>
                {findingStatusLabel[f.status]}
              </Badge>
            )}
            {f.issue_number != null && (
              <Link
                to={`/w/${slug}/issues`}
                className="text-xs text-accent-text hover:underline"
              >
                Issue #{f.issue_number}
              </Link>
            )}
          </div>
          <a
            href={f.url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 block truncate font-mono text-xs text-fg-muted hover:text-accent-text"
          >
            {f.repo_full_name} · {f.path}
            {f.line ? `:${f.line}` : ""}
          </a>
          <pre className="mt-2 overflow-x-auto rounded-md bg-surface-2 px-2.5 py-1.5 font-mono text-xs leading-relaxed">
            <code>{f.snippet}</code>
          </pre>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-subtle">
            {who ? (
              <span className="flex items-center gap-1.5">
                <Avatar
                  src={githubAvatar(f.author_login)}
                  name={f.author_name}
                  size={16}
                />
                <span className="text-fg-muted">
                  {personLabel({ login: f.author_login, name: f.author_name })}
                </span>
              </span>
            ) : (
              <span>Unknown author</span>
            )}
            {f.commit_sha && (
              <Tooltip content={f.commit_message ?? "Commit"}>
                <a
                  className="flex items-center gap-1 hover:text-accent-text"
                  href={`https://github.com/${f.repo_full_name}/commit/${f.commit_sha}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <GitCommitHorizontal className="size-3" />
                  {shortSha(f.commit_sha)}
                </a>
              </Tooltip>
            )}
            {f.pr_number != null && (
              <a
                className="hover:text-accent-text"
                href={`https://github.com/${f.repo_full_name}/pull/${f.pr_number}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                PR #{f.pr_number}
              </a>
            )}
            <span>·</span>
            <Tooltip
              content={
                f.source === "push"
                  ? "Found when this commit was pushed"
                  : "Found by a full scan (author from git blame)"
              }
            >
              <span>{f.source === "push" ? "on push" : "by scan"}</span>
            </Tooltip>
            <RelativeTime iso={f.committed_at ?? f.created_at} />
            {f.assignee_login && (
              <Badge tone="accent" icon={<UserPlus />}>
                @{f.assignee_login}
              </Badge>
            )}
          </div>
        </div>
        {canEdit && (
          <DropdownMenu
            align="end"
            trigger={
              <IconButton
                size="sm"
                label="Finding actions"
                icon={<MoreHorizontal />}
                loading={update.isPending || toIssue.isPending}
              />
            }
          >
            {f.issue_number == null && (
              <MenuItem icon={<Bug />} onSelect={() => toIssue.mutate()}>
                Create issue
              </MenuItem>
            )}
            {f.status !== "acknowledged" && f.status === "open" && (
              <MenuItem
                icon={<Eye />}
                onSelect={() => update.mutate({ status: "acknowledged" })}
              >
                Acknowledge
              </MenuItem>
            )}
            {f.status !== "resolved" && (
              <MenuItem
                icon={<CheckCircle2 />}
                onSelect={() => update.mutate({ status: "resolved" })}
              >
                Mark resolved
              </MenuItem>
            )}
            {f.status !== "false_positive" && (
              <MenuItem
                icon={<CircleSlash />}
                onSelect={() => update.mutate({ status: "false_positive" })}
              >
                False positive
              </MenuItem>
            )}
            {f.status !== "open" && (
              <MenuItem
                icon={<RotateCcw />}
                onSelect={() => update.mutate({ status: "open" })}
              >
                Reopen
              </MenuItem>
            )}
            {people.length > 0 && (
              <>
                <MenuSeparator />
                <MenuLabel>Assign to</MenuLabel>
                {people.slice(0, 8).map((p) => (
                  <MenuItem
                    key={p}
                    icon={<UserPlus />}
                    onSelect={() => update.mutate({ assignee_login: p })}
                  >
                    {p.includes(" ") ? p : `@${p}`}
                  </MenuItem>
                ))}
              </>
            )}
          </DropdownMenu>
        )}
      </div>
    </Card>
  );
}

// ----------------------------------------------------------------------------- policies

function Policies() {
  const { slug, isAdmin } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: qk.policies(slug),
    queryFn: () => policiesApi.list(slug),
  });
  const [editing, setEditing] = useState<Policy | "new" | null>(null);
  const [deleting, setDeleting] = useState<Policy | null>(null);
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: qk.policies(slug) });
  const toggle = useMutation({
    mutationFn: (p: Policy) =>
      policiesApi.update(p.id, { enabled: !p.enabled }),
    onSuccess: (p) => {
      refresh();
      toast.success(p.enabled ? `"${p.name}" is on` : `"${p.name}" is off`);
    },
    onError: (e) => toast.error("Couldn't update the policy", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => policiesApi.remove(id),
    onSuccess: () => {
      setDeleting(null);
      refresh();
      toast.success("Policy deleted");
    },
    onError: (e) => toast.error("Couldn't delete", errorMessage(e)),
  });

  if (q.isError)
    return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return (
    <div className="flex flex-col gap-3">
      {isAdmin && (
        <div className="flex justify-end">
          <Button size="sm" variant="primary" onClick={() => setEditing("new")}>
            <Plus /> New policy
          </Button>
        </div>
      )}
      {!q.data ? (
        <Card className="p-3">
          <SkeletonRows rows={4} />
        </Card>
      ) : (
        <div className="grid gap-2 md:grid-cols-2">
          {[...q.data]
            .sort(
              (a, b) =>
                Number(b.enabled) - Number(a.enabled) ||
                SEVERITIES.indexOf(a.severity) -
                  SEVERITIES.indexOf(b.severity) ||
                a.name.localeCompare(b.name),
            )
            .map((p, i) => (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card
                  className={`group flex h-full flex-col gap-2 p-3 transition-all hover:shadow-md ${p.enabled ? "" : "opacity-60"}`}
                >
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-sm font-medium">{p.name}</span>
                        <Badge tone={severityTone[p.severity]}>
                          {severityLabel[p.severity]}
                        </Badge>
                        {p.template && <Badge>Built-in</Badge>}
                      </div>
                      {p.description && (
                        <p className="mt-1 line-clamp-2 text-xs text-fg-muted">
                          {p.description}
                        </p>
                      )}
                    </div>
                    <Switch
                      checked={p.enabled}
                      disabled={!isAdmin || toggle.isPending}
                      onCheckedChange={() => toggle.mutate(p)}
                      aria-label={`${p.enabled ? "Disable" : "Enable"} ${p.name}`}
                    />
                  </div>
                  <div className="mt-auto flex items-center gap-2 text-2xs text-fg-subtle">
                    <Tooltip
                      content={
                        <code className="break-all">
                          {p.pattern.replaceAll("\n", " · ")}
                        </code>
                      }
                    >
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono">
                        {p.kind === "terms"
                          ? `${p.pattern.split("\n").filter(Boolean).length} terms`
                          : "regex"}
                      </span>
                    </Tooltip>
                    <span className="truncate">
                      {p.paths ? `files: ${p.paths}` : "all files"}
                    </span>
                    {isAdmin && (
                      <span className="ml-auto flex gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
                        <IconButton
                          size="xs"
                          label="Edit policy"
                          icon={<Pencil />}
                          onClick={() => setEditing(p)}
                        />
                        <IconButton
                          size="xs"
                          label="Delete policy"
                          icon={<Trash2 />}
                          onClick={() => setDeleting(p)}
                        />
                      </span>
                    )}
                  </div>
                </Card>
              </motion.div>
            ))}
        </div>
      )}
      <PolicyDialog
        policy={editing}
        onClose={() => setEditing(null)}
        onSaved={refresh}
      />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete "${deleting?.name ?? ""}"?`}
        description="Existing findings stay; new pushes are no longer checked against it."
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </div>
  );
}

const EMPTY: PolicyIn = {
  name: "",
  description: "",
  kind: "terms",
  pattern: "",
  severity: "medium",
  paths: "",
  enabled: true,
};

function PolicyDialog({
  policy,
  onClose,
  onSaved,
}: {
  policy: Policy | "new" | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const open = policy !== null;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={policy === "new" ? "New policy" : "Edit policy"}
      size="md"
    >
      {open && (
        <PolicyForm
          key={policy === "new" ? "new" : policy.id}
          policy={policy === "new" ? null : policy}
          onClose={onClose}
          onSaved={onSaved}
        />
      )}
    </Dialog>
  );
}

function PolicyForm({
  policy,
  onClose,
  onSaved,
}: {
  policy: Policy | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { slug } = useWorkspace();
  const toast = useToast();
  const [form, setForm] = useState<PolicyIn>(
    policy
      ? {
          ...policy,
          description: policy.description ?? "",
          paths: policy.paths ?? "",
        }
      : EMPTY,
  );
  const [sample, setSample] = useState("");
  const set = <K extends keyof PolicyIn>(k: K, v: PolicyIn[K]) =>
    setForm((f) => ({ ...f, [k]: v }));
  const save = useMutation({
    mutationFn: () =>
      policy
        ? policiesApi.update(policy.id, form)
        : policiesApi.create(slug, form),
    onSuccess: () => {
      toast.success(
        policy ? "Policy saved" : "Policy created",
        "New pushes are checked against it. Use Scan now to check existing code.",
      );
      onSaved();
      onClose();
    },
    onError: (e) => toast.error("Couldn't save", errorMessage(e)),
  });
  const test = useMutation({
    mutationFn: () =>
      policiesApi.test({
        kind: form.kind ?? "terms",
        pattern: form.pattern,
        sample,
      }),
  });
  const matches = useMemo(() => test.data, [test.data]);

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Name">
        <Input
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="No internal URLs"
          required
          minLength={2}
        />
      </Field>
      <Field
        label="Description"
        info="Shown on every finding so the author knows why it was flagged."
      >
        <Input
          value={form.description ?? ""}
          onChange={(e) => set("description", e.target.value)}
          placeholder="Why this matters"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Match"
          info="Terms: whole words, case-insensitive, one per line. Regex: Python syntax; nested quantifiers are refused."
        >
          <Select
            value={form.kind ?? "terms"}
            onChange={(e) => set("kind", e.target.value as "terms" | "regex")}
            options={[
              { value: "terms", label: "Terms" },
              { value: "regex", label: "Regular expression" },
            ]}
          />
        </Field>
        <Field label="Severity">
          <Select
            value={form.severity ?? "medium"}
            onChange={(e) => set("severity", e.target.value as Severity)}
            options={SEVERITIES.map((s) => ({
              value: s,
              label: severityLabel[s],
            }))}
          />
        </Field>
      </div>
      <Field label={form.kind === "regex" ? "Pattern" : "Terms"}>
        <Textarea
          value={form.pattern}
          onChange={(e) => set("pattern", e.target.value)}
          rows={3}
          className="font-mono text-xs"
          placeholder={
            form.kind === "regex"
              ? "internal\\.example\\.com"
              : "staging-only\ndo-not-ship"
          }
          required
        />
      </Field>
      <Field
        label="Files"
        info="Comma-separated globs, e.g. *.ts,src/**. Empty = every file."
      >
        <Input
          value={form.paths ?? ""}
          onChange={(e) => set("paths", e.target.value)}
          placeholder="*.ts,*.tsx"
        />
      </Field>
      <div className="rounded-lg border border-dashed border-border p-2.5">
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-fg-muted">
          <FlaskConical className="size-3.5" /> Try it
        </div>
        <Textarea
          value={sample}
          onChange={(e) => setSample(e.target.value)}
          rows={3}
          className="font-mono text-xs"
          placeholder="Paste a few lines of code"
        />
        <div className="mt-2 flex items-center gap-2">
          <Button
            type="button"
            size="xs"
            disabled={!form.pattern || !sample}
            loading={test.isPending}
            onClick={() => test.mutate()}
          >
            Test
          </Button>
          {matches && (
            <span
              className={`text-xs ${matches.ok ? "text-fg-muted" : "text-danger"}`}
            >
              {!matches.ok
                ? matches.error
                : matches.matches?.length
                  ? `${matches.matches.length} line(s) match: ${matches.matches.map((m) => `L${m.line} “${m.match}”`).join(", ")}`
                  : "No matches"}
            </span>
          )}
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          size="sm"
          loading={save.isPending}
        >
          {policy ? "Save" : "Create policy"}
        </Button>
      </div>
    </form>
  );
}
