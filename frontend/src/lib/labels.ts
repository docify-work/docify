export const DOC_KIND: Record<string, string> = {
  overview: "Overview",
  setup: "Setup guide",
  api: "API reference",
};

export const JOB_TYPE: Record<string, string> = {
  repo_index: "Full index",
  repo_sync: "Sync",
  repo_purge: "Purge",
  installation_sync: "Installation sync",
  reembed: "Re-embed",
};

export const docKind = (k: string) => DOC_KIND[k] ?? k;
export const jobType = (t: string) => JOB_TYPE[t] ?? t;

export const MIN_PASSWORD = 10;
