import type { AnchorHTMLAttributes } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/cn";
import { CITE_TITLE, isExternal, safeUrl } from "@/lib/markdown";

function A({ href, children, title, node: _node, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { node?: unknown }) {
  if (!href) return <span>{children}</span>;
  const cite = title === CITE_TITLE;
  return (
    <a
      {...rest}
      href={href}
      title={cite ? "Open source" : title}
      rel="nofollow noopener noreferrer"
      {...(isExternal(href) ? { target: "_blank" } : {})}
      className={cite ? "md-cite" : undefined}
    >
      {children}
    </a>
  );
}

const components: Components = { a: A };

/** Safe Markdown renderer: GFM, no raw HTML, no images, filtered links. */
export function Markdown({ children, compact, className }: { children: string; compact?: boolean; className?: string }) {
  return (
    <div className={cn("md", compact && "md-compact", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={["img"]}
        urlTransform={safeUrl}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default Markdown;
