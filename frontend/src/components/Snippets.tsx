import { Fragment } from "react";
import { cn } from "@/lib/cn";
import { parseHighlights } from "@/lib/highlight";

export function Highlighted({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className}>
      {parseHighlights(text).map((s, i) =>
        s.hit ? (
          <mark key={i} className="hit">
            {s.text}
          </mark>
        ) : (
          <Fragment key={i}>{s.text}</Fragment>
        ),
      )}
    </span>
  );
}

/** Read-only code excerpt with line numbers. */
export function CodeSnippet({ code, startLine = 1, className }: { code: string; startLine?: number; className?: string }) {
  const lines = code.replace(/\n$/, "").split("\n");
  return (
    <pre className={cn("overflow-x-auto bg-code py-2 font-mono text-xs leading-5", className)}>
      <code className="grid min-w-max grid-cols-[auto_1fr]">
        {lines.map((line, i) => (
          <Fragment key={i}>
            <span className="tabular select-none border-r border-border pl-3 pr-2 text-right text-fg-subtle" aria-hidden="true">
              {line === "…" ? "" : startLine + i}
            </span>
            <span className="whitespace-pre pl-3 pr-4">{line || " "}</span>
          </Fragment>
        ))}
      </code>
    </pre>
  );
}
