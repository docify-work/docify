import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText, GitMerge, MessageSquareQuote } from "lucide-react";
import { motion } from "motion/react";
import { Link, useSearchParams } from "react-router";
import { getDemo } from "@/api/endpoints";
import { Button, Callout } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { oauthErrorMessage } from "@/lib/messages";

const FEATURES = [
  { icon: FileText, title: "Generated docs", text: "Overview, setup guide and API reference for every repo." },
  { icon: GitMerge, title: "Always current", text: "Updated on every merge to the default branch." },
  { icon: MessageSquareQuote, title: "Search & chat", text: "Answers cite the exact file and lines." },
];

const ease = [0.22, 1, 0.36, 1] as const;

export default function Landing() {
  usePageMeta([{ label: "Living docs for your repos" }]);
  const { me } = useMe();
  const [params, setParams] = useSearchParams();
  const error = oauthErrorMessage(params.get("error"));
  const demo = useQuery({ queryKey: ["demo"], queryFn: getDemo, staleTime: 300_000, retry: false });
  const demoSlug = demo.data?.available ? demo.data.workspace_slug : null;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 pb-16 pt-[12vh]">
      {error && (
        <Callout tone="danger" className="mb-6 max-w-xl" onDismiss={() => setParams({}, { replace: true })}>
          {error}
        </Callout>
      )}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease }}>
        <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-2xs font-medium text-fg-muted shadow-xs">
          <span className="size-1.5 rounded-full bg-success" />
          GitHub App · RAG with citations
        </span>
        <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Documentation that keeps up with your code.
        </h1>
        <p className="mt-3 max-w-xl text-base text-fg-muted">
          Connect a repo. Docify writes the docs, updates them on every merge, and answers questions with line-level citations.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {demoSlug && (
            <Button asChild variant="primary">
              <Link to={`/w/${demoSlug}`}>
                View demo
                <ArrowRight />
              </Link>
            </Button>
          )}
          {me ? (
            <Button asChild variant={demoSlug ? "secondary" : "primary"}>
              <Link to="/app">Open app</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant={demoSlug ? "secondary" : "primary"}>
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link to="/signup">Create account</Link>
              </Button>
            </>
          )}
        </div>
      </motion.div>

      <div className="mt-14 grid gap-3 sm:grid-cols-3">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease, delay: 0.12 + i * 0.06 }}
            className="group rounded-lg border border-border bg-surface p-4 shadow-xs transition-[box-shadow,border-color] duration-200 hover:border-border-strong hover:shadow-md"
          >
            <span className="grid size-8 place-items-center rounded-md bg-accent-soft text-accent-text transition-transform duration-200 group-hover:scale-105">
              <f.icon className="size-4" aria-hidden="true" />
            </span>
            <h2 className="mt-3 text-sm font-semibold">{f.title}</h2>
            <p className="mt-0.5 text-xs text-fg-muted">{f.text}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
