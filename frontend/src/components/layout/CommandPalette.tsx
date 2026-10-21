import { ArrowRight, CornerDownLeft, FileText, MessageSquare, Plus, Search, UserRound, type LucideIcon } from "lucide-react";
import { Dialog as RD } from "radix-ui";
import { useId, useMemo, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router";
import { Kbd } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { cn } from "@/lib/cn";
import { WORKSPACE_NAV, canSee } from "./nav";

interface Command {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
  to: string;
}

/** ⌘K / Ctrl+K palette: jump to pages, switch workspace, search or ask. */
export function CommandPalette({ open, onOpenChange, slug }: { open: boolean; onOpenChange: (o: boolean) => void; slug: string | null }) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="ui-overlay fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]" />
        <RD.Content
          className={
            "ui-pop fixed left-1/2 top-[14vh] z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl " +
            "border border-border bg-surface shadow-lg focus:outline-none"
          }
        >
          <RD.Title className="sr-only">Command palette</RD.Title>
          <RD.Description className="sr-only">Type to search pages and actions</RD.Description>
          {open && <PaletteBody slug={slug} close={() => onOpenChange(false)} />}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

function PaletteBody({ slug, close }: { slug: string | null; close: () => void }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const { me } = useMe();
  const navigate = useNavigate();
  const listId = useId();
  const role = me?.workspaces.find((w) => w.slug === slug)?.role ?? null;

  const commands = useMemo<Command[]>(() => {
    const q = query.trim();
    const out: Command[] = [];
    if (slug && q.length >= 2) {
      const enc = encodeURIComponent(q);
      out.push(
        { id: "s-code", group: "Actions", label: `Search code for “${q}”`, icon: Search, to: `/w/${slug}/search?q=${enc}&scope=code` },
        { id: "s-docs", group: "Actions", label: `Search docs for “${q}”`, icon: FileText, to: `/w/${slug}/search?q=${enc}&scope=docs` },
        { id: "ask", group: "Actions", label: `Ask “${q}”`, icon: MessageSquare, to: `/w/${slug}/chat?q=${enc}` },
      );
    }
    const lower = q.toLowerCase();
    const match = (s: string) => !lower || s.toLowerCase().includes(lower);
    if (slug) {
      for (const n of WORKSPACE_NAV) {
        if (canSee(n.access, role) && match(n.label)) {
          out.push({ id: `nav-${n.key}`, group: "Go to", label: n.label, icon: n.icon, to: n.path(slug) });
        }
      }
    }
    for (const w of me?.workspaces ?? []) {
      if (w.slug !== slug && match(w.name)) {
        out.push({ id: `ws-${w.slug}`, group: "Workspaces", label: w.name, icon: ArrowRight, to: `/w/${w.slug}` });
      }
    }
    if (me) {
      if (match("Account")) out.push({ id: "account", group: "General", label: "Account", icon: UserRound, to: "/account" });
      if (match("Create workspace")) out.push({ id: "new", group: "General", label: "Create workspace", icon: Plus, to: "/new" });
    }
    return out;
  }, [query, slug, role, me]);

  const current = Math.min(active, Math.max(commands.length - 1, 0));

  const run = (c: Command | undefined) => {
    if (!c) return;
    close();
    navigate(c.to);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((current + 1) % Math.max(commands.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((current - 1 + commands.length) % Math.max(commands.length, 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(commands[current]);
    }
  };

  let lastGroup = "";
  return (
    <div>
      <div className="flex h-11 items-center gap-2 border-b border-border px-3">
        <Search className="size-4 text-fg-subtle" aria-hidden="true" />
        <input
          autoFocus
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={commands[current] ? `${listId}-${commands[current].id}` : undefined}
          aria-label="Search pages and actions"
          placeholder={slug ? "Search, ask, or jump to…" : "Jump to…"}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
          className="h-full flex-1 bg-transparent text-sm outline-none placeholder:text-fg-subtle"
        />
        <Kbd>Esc</Kbd>
      </div>
      <ul id={listId} role="listbox" aria-label="Results" className="max-h-80 overflow-auto p-1.5">
        {commands.length === 0 && <li className="px-2 py-6 text-center text-xs text-fg-subtle">No matches</li>}
        {commands.map((c, i) => {
          const header = c.group !== lastGroup ? c.group : null;
          lastGroup = c.group;
          const Icon = c.icon;
          return (
            <li key={c.id} role="presentation">
              {header && <div className="px-2 pb-1 pt-2 text-2xs font-medium uppercase tracking-wide text-fg-subtle">{header}</div>}
              <div
                id={`${listId}-${c.id}`}
                role="option"
                aria-selected={i === current}
                onMouseMove={() => setActive(i)}
                onClick={() => run(c)}
                className={cn(
                  "flex h-8 cursor-pointer items-center gap-2.5 rounded-md px-2 text-sm transition-colors duration-100",
                  i === current ? "bg-surface-2 text-fg" : "text-fg-muted",
                )}
              >
                <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden="true" />
                <span className="flex-1 truncate">{c.label}</span>
                {i === current && <CornerDownLeft className="size-3.5 text-fg-subtle" aria-hidden="true" />}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
