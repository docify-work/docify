import { useQuery } from "@tanstack/react-query";
import { Code2, ExternalLink, FileText, History, Search as SearchIcon, SearchX } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router";
import { qk, search } from "@/api/endpoints";
import type { SearchHit } from "@/api/types";
import { CodeSnippet, Highlighted } from "@/components/Snippets";
import { Badge, Button, Card, EmptyState, ErrorState, Input, Kbd, PageHeader, Select, SkeletonText, Tabs } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepos } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";

type Scope = "code" | "docs";

export default function Search() {
  const { ws, slug } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Search" }]);
  const [params, setParams] = useSearchParams();
  const q = params.get("q")?.trim() ?? "";
  const scope: Scope = params.get("scope") === "docs" ? "docs" : "code";
  const repo = params.get("repo") ?? "";
  const [draft, setDraft] = useState(q);
  // Keep the input in sync when the URL query changes from outside (⌘K palette, back button).
  const [syncedQ, setSyncedQ] = useState(q);
  if (syncedQ !== q) {
    setSyncedQ(q);
    setDraft(q);
  }
  const reposQ = useRepos(slug);

  const results = useQuery({
    queryKey: qk.search(slug, q, scope, repo),
    queryFn: () => search(slug, q, scope, repo || undefined),
    enabled: q.length >= 2,
    staleTime: 60_000,
  });

  const update = (next: Partial<{ q: string; scope: Scope; repo: string }>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: next.q === undefined });
  };

  return (
    <>
      <PageHeader title="Search" info="Code search blends semantic and keyword matching. Docs search covers published docs and changelogs." />
      <form
        className="mb-4 flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          update({ q: draft.trim() });
        }}
        role="search"
      >
        <Input
          aria-label="Search query"
          icon={<SearchIcon />}
          placeholder={scope === "code" ? "e.g. where are sessions validated?" : "e.g. environment variables"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoFocus
          maxLength={300}
          className="min-w-0"
          fieldClassName="flex-1"
        />
        <Tabs<Scope>
          ariaLabel="Scope"
          value={scope}
          onValueChange={(v) => update({ scope: v })}
          items={[
            { value: "code", label: "Code", icon: <Code2 /> },
            { value: "docs", label: "Docs", icon: <FileText /> },
          ]}
        />
        <Select
          aria-label="Repository"
          size="md"
          className="w-48"
          value={repo}
          onChange={(e) => update({ repo: e.target.value })}
          options={[{ value: "", label: "All repositories" }, ...(reposQ.data ?? []).map((r) => ({ value: r.id, label: r.full_name }))]}
        />
        <Button type="submit" variant="primary" disabled={draft.trim().length < 2}>
          Search
        </Button>
      </form>

      {q.length < 2 ? (
        <Card>
          <EmptyState
            icon={<SearchIcon />}
            title="Search code and docs"
            info="Type at least 2 characters. Tip: open the command palette anywhere to search."
            action={
              <span className="flex items-center gap-1 text-xs text-fg-subtle">
                <Kbd>Ctrl</Kbd>
                <Kbd>K</Kbd>
              </span>
            }
          />
        </Card>
      ) : results.isPending ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="p-4">
              <SkeletonText lines={3} />
            </Card>
          ))}
        </div>
      ) : results.isError ? (
        <Card>
          <ErrorState error={results.error} onRetry={() => void results.refetch()} />
        </Card>
      ) : results.data.hits.length === 0 ? (
        <Card>
          <EmptyState icon={<SearchX />} title={`No results for “${q}”`} info="Try other words, or switch between Code and Docs." />
        </Card>
      ) : (
        <>
          <p className="tabular mb-2 text-xs text-fg-subtle">
            {results.data.hits.length} result{results.data.hits.length === 1 ? "" : "s"}
          </p>
          <ul className="ui-stagger flex flex-col gap-3">
            {results.data.hits.map((h, i) => (
              <li key={`${h.kind}-${h.repo_id}-${h.title}-${i}`} style={{ "--i": Math.min(i, 12) } as CSSProperties}>
                {h.kind === "code" ? <CodeHit hit={h} /> : <DocHit hit={h} slug={slug} />}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function CodeHit({ hit }: { hit: SearchHit }) {
  return (
    <Card className="overflow-hidden transition-shadow duration-200 hover:shadow-md">
      <div className="flex h-9 items-center gap-2 border-b border-border px-3">
        <Code2 className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
        {hit.url ? (
          <a href={hit.url} target="_blank" rel="nofollow noopener noreferrer" className="flex min-w-0 items-center gap-1 font-mono text-xs font-medium hover:text-accent-text">
            <span className="truncate">{hit.path ?? hit.title}</span>
            {hit.start_line != null && <span className="shrink-0 text-fg-subtle">:{hit.start_line}-{hit.end_line}</span>}
            <ExternalLink className="size-3 shrink-0 text-fg-subtle" aria-hidden="true" />
          </a>
        ) : (
          <span className="truncate font-mono text-xs font-medium">{hit.title}</span>
        )}
        <span className="ml-auto shrink-0 text-xs text-fg-subtle">{hit.repo_full_name}</span>
      </div>
      <CodeSnippet code={hit.snippet} startLine={hit.start_line ?? 1} />
    </Card>
  );
}

function DocHit({ hit, slug }: { hit: SearchHit; slug: string }) {
  const to = hit.doc_id ? `/w/${slug}/docs/${hit.doc_id}` : `/w/${slug}/changelog/${hit.repo_id}`;
  return (
    <Card className="px-4 py-3 transition-shadow duration-200 hover:shadow-md">
      <div className="flex items-center gap-2">
        {hit.kind === "changelog" ? (
          <History className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
        ) : (
          <FileText className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
        )}
        <Link to={to} className="truncate text-sm font-medium hover:text-accent-text">
          {hit.title}
        </Link>
        <Badge>{hit.kind === "changelog" ? "Changelog" : "Doc"}</Badge>
        <span className="ml-auto shrink-0 text-xs text-fg-subtle">{hit.repo_full_name}</span>
      </div>
      <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-fg-muted">
        <Highlighted text={hit.snippet} />
      </p>
    </Card>
  );
}
