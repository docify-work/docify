import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ExternalLink,
  FolderGit2,
  GitBranch,
  Link2,
  Lock,
  MoreHorizontal,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import { github, qk, repos } from "@/api/endpoints";
import type { Installation, Repo } from "@/api/types";
import { GitHubIcon } from "@/components/BrandIcons";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  DataTable,
  DropdownMenu,
  EmptyState,
  ErrorState,
  IconButton,
  MenuItem,
  MenuSeparator,
  PageHeader,
  RelativeTime,
  SkeletonRows,
  StatusPill,
  Tooltip,
  useToast,
  type Column,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepos } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";
import { useAppConfig } from "@/lib/config";
import { summarizeError } from "@/lib/format";
import { installErrorMessage } from "@/lib/messages";

export default function Repos() {
  const { ws, slug, isAdmin } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Repositories" }]);
  const [params, setParams] = useSearchParams();
  const installError = installErrorMessage(params.get("error"));
  const connected = params.get("connected") === "1";
  const toast = useToast();
  const reposQ = useRepos(slug);
  const navigate = useNavigate();

  useEffect(() => {
    if (connected) {
      toast.success("GitHub connected", "Pick repositories to add.");
      setParams((p) => {
        p.delete("connected");
        return p;
      }, { replace: true });
    }
  }, [connected, setParams, toast]);

  const columns: Column<Repo>[] = [
    {
      key: "name",
      header: "Repository",
      cell: (r) => (
        <span className="flex min-w-0 items-center gap-2">
          <Link to={`/w/${slug}/repos/${r.id}`} className="truncate font-medium hover:text-accent-text" onClick={(e) => e.stopPropagation()}>
            {r.full_name}
          </Link>
          {r.private && (
            <Tooltip content="Private repository">
              <Lock className="size-3 shrink-0 text-fg-subtle" aria-label="Private" />
            </Tooltip>
          )}
          {r.archived && <Badge>Archived</Badge>}
        </span>
      ),
    },
    {
      key: "branch",
      header: "Branch",
      className: "hidden md:table-cell w-32",
      cell: (r) => (
        <span className="inline-flex items-center gap-1 font-mono text-xs text-fg-muted">
          <GitBranch className="size-3" aria-hidden="true" />
          {r.default_branch}
        </span>
      ),
    },
    { key: "status", header: "Status", className: "w-32", cell: (r) => <StatusPill status={r.status} hint={summarizeError(r.error)} /> },
    {
      key: "synced",
      header: "Synced",
      className: "hidden sm:table-cell w-28",
      cell: (r) => <RelativeTime iso={r.last_synced_at} className="text-fg-subtle" />,
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (r) => (isAdmin ? <RepoActions repo={r} /> : (
        <IconButton size="xs" label="Open on GitHub" icon={<ExternalLink />} onClick={(e) => { e.stopPropagation(); window.open(r.html_url, "_blank", "noopener,noreferrer"); }} />
      )),
    },
  ];

  return (
    <>
      <PageHeader
        title="Repositories"
        meta={reposQ.data && <span className="tabular">{reposQ.data.length}</span>}
        info="Docify indexes each repo's default branch and refreshes its docs on every push."
        actions={isAdmin && <ConnectGitHubButton />}
      />
      {installError && (
        <Callout tone="danger" className="mb-4" onDismiss={() => setParams({}, { replace: true })}>
          {installError}
        </Callout>
      )}

      {isAdmin && <Installations />}

      <Card>
        {reposQ.isError ? (
          <ErrorState error={reposQ.error} onRetry={() => void reposQ.refetch()} />
        ) : (
          <DataTable
            caption="Repositories"
            columns={columns}
            rows={reposQ.data}
            loading={reposQ.isPending}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(`/w/${slug}/repos/${r.id}`)}
            empty={
              <EmptyState
                icon={<FolderGit2 />}
                title="No repositories yet"
                info={isAdmin ? "Connect the Docify GitHub App, then pick repositories to add." : "An admin can connect repositories."}
                action={isAdmin && <ConnectGitHubButton />}
              />
            }
          />
        )}
      </Card>
    </>
  );
}

function ConnectGitHubButton() {
  const { slug } = useWorkspace();
  const cfg = useAppConfig();
  const toast = useToast();
  const connect = useMutation({
    mutationFn: () => github.installUrl(slug),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (e) => toast.error("Couldn't start GitHub connect", errorMessage(e)),
  });
  const button = (
    <Button size="sm" variant="primary" loading={connect.isPending || connect.isSuccess} disabled={!cfg.githubEnabled} onClick={() => connect.mutate()}>
      <GitHubIcon className="size-3.5" />
      Connect GitHub
    </Button>
  );
  return cfg.githubEnabled ? button : (
    <Tooltip content="The GitHub App isn't configured on this server.">
      <span tabIndex={0}>{button}</span>
    </Tooltip>
  );
}

function Installations() {
  const { slug } = useWorkspace();
  const cfg = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: qk.installations(slug),
    queryFn: () => github.installations(slug),
    enabled: cfg.githubEnabled,
    retry: false,
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const attach = useMutation({
    mutationFn: async () => {
      const byInst = new Map<number, number[]>();
      for (const key of selected) {
        const [inst, repo] = key.split(":").map(Number) as [number, number];
        byInst.set(inst, [...(byInst.get(inst) ?? []), repo]);
      }
      let added = 0;
      for (const [inst, ids] of byInst) added += (await github.attach(slug, inst, ids)).length;
      return added;
    },
    onSuccess: async (n) => {
      setSelected(new Set());
      toast.success(`Added ${n} ${n === 1 ? "repository" : "repositories"}`, "Indexing starts shortly.");
      await Promise.all([
        qc.invalidateQueries({ queryKey: qk.repos(slug) }),
        qc.invalidateQueries({ queryKey: qk.installations(slug) }),
        qc.invalidateQueries({ queryKey: qk.workspace(slug) }),
      ]);
    },
    onError: (e) => toast.error("Couldn't add repositories", errorMessage(e)),
  });

  if (!cfg.githubEnabled) return null;
  if (q.isPending) {
    return (
      <Card className="mb-4">
        <SkeletonRows rows={2} />
      </Card>
    );
  }
  if (q.isError) return <Callout tone="danger" className="mb-4">{errorMessage(q.error)}</Callout>;
  const available = q.data.flatMap((i) => i.repos.filter((r) => r.attached_workspace == null));
  if (q.data.length === 0) return null;

  const toggle = (key: string, on: boolean) =>
    setSelected((s) => {
      const n = new Set(s);
      if (on) n.add(key);
      else n.delete(key);
      return n;
    });

  return (
    <Card className="mb-4">
      <CardHeader
        icon={<GitHubIcon />}
        title="Available on GitHub"
        meta={available.length}
        info="Repositories the Docify GitHub App can access. To add more, change the app's repository access on GitHub, then reload."
        actions={
          <Button size="sm" variant="primary" disabled={selected.size === 0} loading={attach.isPending} onClick={() => attach.mutate()}>
            <Link2 />
            Add {selected.size > 0 ? selected.size : ""}
          </Button>
        }
      />
      <div className="max-h-72 overflow-auto">
        {q.data.map((inst) => (
          <InstallationGroup key={inst.installation_id} inst={inst} slug={slug} selected={selected} onToggle={toggle} />
        ))}
      </div>
    </Card>
  );
}

function InstallationGroup({
  inst,
  slug,
  selected,
  onToggle,
}: {
  inst: Installation;
  slug: string;
  selected: Set<string>;
  onToggle: (key: string, on: boolean) => void;
}) {
  return (
    <div>
      <div className="sticky top-0 z-[1] flex h-8 items-center gap-2 border-b border-border bg-surface-2/80 px-3 text-xs backdrop-blur-sm">
        <span className="font-medium">{inst.account_login}</span>
        <span className="text-fg-subtle">{inst.account_type}</span>
        {inst.suspended && <StatusPill status="suspended" />}
      </div>
      {inst.repos.length === 0 ? (
        <p className="px-3 py-2 text-xs text-fg-subtle">No repositories shared with the app.</p>
      ) : (
        <ul className="divide-y divide-border">
          {inst.repos.map((r) => {
            const key = `${inst.installation_id}:${r.github_repo_id}`;
            const here = r.attached_workspace === slug;
            const elsewhere = r.attached_workspace != null && !here;
            return (
              <li key={key} className="flex h-9 items-center gap-2 px-3 transition-colors hover:bg-surface-2/60">
                <Checkbox
                  checked={here || selected.has(key)}
                  disabled={here || elsewhere || inst.suspended}
                  onCheckedChange={(v) => onToggle(key, v)}
                  label={<span className="font-mono text-xs">{r.full_name}</span>}
                />
                {r.private && <Lock className="size-3 text-fg-subtle" aria-label="Private" />}
                <span className="ml-auto">
                  {here && <Badge tone="success">Added</Badge>}
                  {elsewhere && (
                    <Tooltip content="A repository can belong to one workspace at a time.">
                      <span tabIndex={0}>
                        <Badge>In another workspace</Badge>
                      </span>
                    </Tooltip>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Admin actions for one repo (menu + confirm). Shared with the repo detail page. */
export function RepoActions({ repo, variant = "menu", onRemoved }: { repo: Repo; variant?: "menu" | "buttons"; onRemoved?: () => void }) {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const inactive = repo.status === "disconnected" || repo.status === "suspended";

  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: qk.repos(slug) }),
      qc.invalidateQueries({ queryKey: qk.repo(repo.id) }),
      qc.invalidateQueries({ queryKey: qk.jobs(slug) }),
    ]);
  const resync = useMutation({
    mutationFn: () => repos.resync(repo.id),
    onSuccess: () => {
      toast.success("Sync queued", repo.full_name);
      void refresh();
    },
    onError: (e) => toast.error("Couldn't queue sync", errorMessage(e)),
  });
  const reindex = useMutation({
    mutationFn: () => repos.reindex(repo.id),
    onSuccess: () => {
      toast.success("Full re-index queued", repo.full_name);
      void refresh();
    },
    onError: (e) => toast.error("Couldn't queue re-index", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => repos.remove(repo.id),
    onSuccess: async () => {
      setConfirmOpen(false);
      toast.success("Repository removed", "Its data will be deleted shortly.");
      await refresh();
      await qc.invalidateQueries({ queryKey: qk.workspace(slug) });
      onRemoved?.();
    },
    onError: (e) => toast.error("Couldn't remove repository", errorMessage(e)),
  });

  const confirm = (
    <ConfirmDialog
      open={confirmOpen}
      onOpenChange={setConfirmOpen}
      title={`Remove ${repo.full_name}?`}
      description="Its docs, search index and chat sources are deleted."
      confirmLabel="Remove"
      loading={remove.isPending}
      onConfirm={() => remove.mutate()}
    />
  );

  if (variant === "buttons") {
    return (
      <>
        <Tooltip content="Pull the latest commits and update changed docs.">
          <Button size="sm" icon={<RefreshCw />} loading={resync.isPending} disabled={inactive} onClick={() => resync.mutate()}>
            Sync
          </Button>
        </Tooltip>
        <Tooltip content="Rebuild the index and regenerate all docs from scratch.">
          <Button size="sm" icon={<RotateCcw />} loading={reindex.isPending} disabled={inactive} onClick={() => reindex.mutate()}>
            Re-index
          </Button>
        </Tooltip>
        <IconButton label="Remove repository" icon={<Trash2 />} onClick={() => setConfirmOpen(true)} />
        {confirm}
      </>
    );
  }

  return (
    <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
      <DropdownMenu
        align="end"
        trigger={<IconButton size="xs" label="Repository actions" tooltip={false} icon={<MoreHorizontal />} />}
      >
        <MenuItem icon={<RefreshCw />} disabled={inactive} onSelect={() => resync.mutate()}>
          Sync now
        </MenuItem>
        <MenuItem icon={<RotateCcw />} disabled={inactive} onSelect={() => reindex.mutate()}>
          Full re-index
        </MenuItem>
        <MenuItem icon={<ExternalLink />} onSelect={() => window.open(repo.html_url, "_blank", "noopener,noreferrer")}>
          Open on GitHub
        </MenuItem>
        <MenuSeparator />
        <MenuItem icon={<Trash2 />} danger onSelect={() => setConfirmOpen(true)}>
          Remove
        </MenuItem>
      </DropdownMenu>
      {confirm}
    </span>
  );
}
