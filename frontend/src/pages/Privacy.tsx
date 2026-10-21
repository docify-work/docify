import { Archive, Clock, Database, KeyRound, Mail, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";

const ITEMS: { icon: ReactNode; title: string; body: ReactNode }[] = [
  {
    icon: <Database />,
    title: "What we store",
    body: "Your email, name and avatar; workspaces and memberships; the repositories you connect (code chunks, generated docs, changelog); chat history; job logs.",
  },
  {
    icon: <KeyRound />,
    title: "Credentials",
    body: "Passwords are hashed (Argon2id). Sessions are random tokens stored as hashes. OAuth provider tokens are discarded after sign-in.",
  },
  {
    icon: <Trash2 />,
    title: "Deletion",
    body: "Removing a repo, deleting a workspace or deleting your account deletes the related data from the live database right away.",
  },
  {
    icon: <Archive />,
    title: "Backups",
    body: "Database backups are kept for at most 14 days.",
  },
  {
    icon: <Clock />,
    title: "Snapshots",
    body: "Server disk snapshots are kept for at most 7 days.",
  },
  {
    icon: <Mail />,
    title: "Contact",
    body: "Questions or deletion requests: open an issue at github.com/docify-work/docify.",
  },
];

export default function Privacy() {
  usePageMeta([{ label: "Privacy" }]);
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Privacy</h1>
      <p className="mt-1 text-sm text-fg-muted">Docify is a learning project. Here's exactly what it keeps.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {ITEMS.map((it) => (
          <Card key={it.title} className="p-4">
            <div className="flex items-center gap-2">
              <span className="text-fg-subtle [&_svg]:size-4">{it.icon}</span>
              <h2 className="text-sm font-semibold">{it.title}</h2>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">{it.body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
