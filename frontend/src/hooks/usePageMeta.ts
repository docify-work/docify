import { createContext, useContext, useEffect } from "react";

export interface MetaCrumb {
  label: string;
  to?: string;
}

export interface ShellApi {
  setCrumbs: (crumbs: MetaCrumb[]) => void;
}

export const ShellContext = createContext<ShellApi | null>(null);

/**
 * Sets the document title and the top-bar breadcrumbs for the current page.
 * The last crumb is the page title.
 */
export function usePageMeta(crumbs: MetaCrumb[]) {
  const shell = useContext(ShellContext);
  const key = JSON.stringify(crumbs);
  useEffect(() => {
    const parsed = JSON.parse(key) as MetaCrumb[];
    const title = parsed[parsed.length - 1]?.label;
    document.title = title ? `${title} · Docify` : "Docify";
    shell?.setCrumbs(parsed);
  }, [key, shell]);
}
