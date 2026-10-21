import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, FileCode2, History, MessageSquare, MessageSquareOff, Plus, Square, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import { qk, streamChat, threads } from "@/api/endpoints";
import type { ChatSource, Thread } from "@/api/types";
import { LogoMark } from "@/components/Logo";
import { Markdown } from "@/components/Markdown";
import { linkCitations } from "@/lib/markdown";
import {
  Avatar,
  Badge,
  Button,
  Callout,
  Card,
  ConfirmDialog,
  Drawer,
  EmptyState,
  IconButton,
  InfoTip,
  Kbd,
  RelativeTime,
  Select,
  SkeletonRows,
  useToast,
} from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useRepos } from "@/hooks/useRepos";
import { useWorkspace } from "@/hooks/useWorkspace";
import { cn } from "@/lib/cn";

interface UIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[] | null;
  streaming?: boolean;
  error?: string | null;
}

const MAX_LEN = 2000;
const SUGGESTIONS = ["How do I run this project locally?", "Where is authentication handled?", "Which HTTP endpoints exist?"];

let seq = 0;
const uid = () => `m${Date.now().toString(36)}${(seq++).toString(36)}`;

export default function Chat() {
  const { ws, slug, isMember } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Chat" }]);
  const { me } = useMe();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const toast = useToast();
  const reposQ = useRepos(slug);

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [input, setInput] = useState(() => params.get("q") ?? "");
  const [repo, setRepo] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loadingThread, setLoadingThread] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const threadsQ = useQuery({ queryKey: qk.threads(slug), queryFn: () => threads.list(slug), enabled: isMember });

  // Stop any in-flight stream when leaving the page.
  useEffect(() => () => abortRef.current?.abort(), []);

  // Keep the newest message in view while the user is at the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const patch = (id: string, fn: (m: UIMessage) => Partial<UIMessage>) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)));

  const send = async (raw: string) => {
    const text = raw.trim();
    if (!text || streaming) return;
    const asstId = uid();
    setMessages((ms) => [...ms, { id: uid(), role: "user", content: text }, { id: asstId, role: "assistant", content: "", streaming: true }]);
    setInput("");
    stickRef.current = true;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);
    try {
      await streamChat(
        slug,
        { message: text, thread_id: threadId, repo_ids: repo ? [repo] : null },
        {
          onMeta: (id) => setThreadId(id),
          onToken: (t) => patch(asstId, (m) => ({ content: m.content + t })),
          onSources: (s) => patch(asstId, () => ({ sources: s })),
          onError: (msg) => patch(asstId, () => ({ error: msg })),
        },
        ctrl.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        patch(asstId, (m) => ({ error: m.content ? null : "Stopped." }));
      } else {
        patch(asstId, () => ({ error: errorMessage(err) }));
      }
    } finally {
      patch(asstId, () => ({ streaming: false }));
      setStreaming(false);
      abortRef.current = null;
      if (isMember) void qc.invalidateQueries({ queryKey: qk.threads(slug) });
      inputRef.current?.focus();
    }
  };

  const openThread = async (t: Thread) => {
    if (streaming) abortRef.current?.abort();
    setHistoryOpen(false);
    setLoadingThread(t.id);
    try {
      const detail = await qc.fetchQuery({ queryKey: qk.thread(t.id), queryFn: () => threads.get(t.id), staleTime: 0 });
      setMessages(detail.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, sources: m.sources })));
      setThreadId(detail.id);
      stickRef.current = true;
    } catch (err) {
      toast.error("Couldn't open conversation", errorMessage(err));
    } finally {
      setLoadingThread(null);
    }
  };

  const newChat = () => {
    if (streaming) abortRef.current?.abort();
    setMessages([]);
    setThreadId(null);
    setHistoryOpen(false);
    inputRef.current?.focus();
  };

  if (!ws.settings.chat_enabled) {
    return (
      <Card>
        <EmptyState icon={<MessageSquareOff />} title="Chat is turned off for this workspace" info="An admin can enable it in Settings." />
      </Card>
    );
  }

  const threadList = isMember && (
    <ThreadList
      threads={threadsQ.data}
      loading={threadsQ.isPending}
      activeId={threadId}
      loadingId={loadingThread}
      onOpen={(t) => void openThread(t)}
      onDeleted={(id) => {
        if (id === threadId) newChat();
      }}
    />
  );

  return (
    <div className="flex h-[calc(100dvh-8.5rem)] min-h-[440px] gap-4">
      {isMember && (
        <aside className="hidden w-56 shrink-0 flex-col lg:flex">
          <Button size="sm" icon={<Plus />} onClick={newChat} className="mb-2 w-full justify-start">
            New chat
          </Button>
          <div className="min-h-0 flex-1 overflow-auto">{threadList}</div>
        </aside>
      )}

      <Card className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3">
          <MessageSquare className="size-3.5 text-fg-subtle" aria-hidden="true" />
          <h1 className="text-sm font-semibold">Ask about the code</h1>
          <InfoTip>Answers come only from indexed code and cite sources as [n]. Sources open the exact lines on GitHub.</InfoTip>
          {!me && (
            <Badge tone="accent" className="ml-1">
              Demo · limited
            </Badge>
          )}
          <div className="ml-auto flex items-center gap-1">
            <Select
              size="sm"
              aria-label="Limit to repository"
              className="w-44"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              options={[{ value: "", label: "All repositories" }, ...(reposQ.data ?? []).map((r) => ({ value: r.id, label: r.full_name }))]}
            />
            {isMember && (
              <>
                <IconButton className="lg:hidden" label="History" icon={<History />} onClick={() => setHistoryOpen(true)} />
                <IconButton className="lg:hidden" label="New chat" icon={<Plus />} onClick={newChat} />
              </>
            )}
          </div>
        </div>

        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
          }}
          className="min-h-0 flex-1 overflow-y-auto"
          aria-live="polite"
          aria-busy={streaming}
        >
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
              <LogoMark size={32} />
              <p className="text-sm font-medium">What do you want to know?</p>
              <div className="flex max-w-lg flex-wrap justify-center gap-1.5">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void send(s)}
                    className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-fg-muted transition-[color,border-color,transform] duration-150 hover:border-border-strong hover:text-fg active:scale-[0.97]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-5">
              <AnimatePresence initial={false}>
                {messages.map((m) => (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                  >
                    {m.role === "user" ? (
                      <div className="flex justify-end gap-2">
                        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg rounded-tr-sm bg-accent-soft px-3 py-2 text-sm text-fg">
                          {m.content}
                        </div>
                        <Avatar src={me?.avatar_url} name={me?.name ?? me?.email ?? "You"} size={24} />
                      </div>
                    ) : (
                      <AssistantMessage m={m} />
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>

        <form
          className="shrink-0 border-t border-border p-2.5"
          onSubmit={(e) => {
            e.preventDefault();
            void send(input);
          }}
        >
          <div className="flex items-end gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 shadow-xs transition-[border-color,box-shadow] duration-150 focus-within:border-accent focus-within:ring-3 focus-within:ring-accent/15">
            <textarea
              ref={inputRef}
              aria-label="Message"
              rows={1}
              maxLength={MAX_LEN}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void send(input);
                }
              }}
              placeholder="Ask a question…"
              className="max-h-40 min-h-7 flex-1 resize-none bg-transparent py-1 text-sm leading-5 outline-none [field-sizing:content] placeholder:text-fg-subtle"
            />
            {input.length > MAX_LEN - 200 && <span className="tabular pb-1.5 text-2xs text-fg-subtle">{MAX_LEN - input.length}</span>}
            {streaming ? (
              <IconButton size="sm" variant="secondary" label="Stop" icon={<Square className="fill-current" />} onClick={() => abortRef.current?.abort()} />
            ) : (
              <IconButton size="sm" variant="primary" type="submit" label="Send" icon={<ArrowUp />} disabled={!input.trim()} />
            )}
          </div>
          <p className="mt-1 hidden px-1 text-2xs text-fg-subtle sm:block">
            <Kbd>Enter</Kbd> send · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> new line
          </p>
        </form>
      </Card>

      {isMember && (
        <Drawer open={historyOpen} onOpenChange={setHistoryOpen} title="Conversations" side="right">
          <div className="p-2">{threadList}</div>
        </Drawer>
      )}
    </div>
  );
}

function AssistantMessage({ m }: { m: UIMessage }) {
  const text = linkCitations(m.content, m.sources);
  return (
    <div className="flex gap-2.5">
      <LogoMark size={24} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        {m.content ? (
          <div className={cn(m.streaming && "ui-streaming")}>
            <Markdown compact>{text}</Markdown>
          </div>
        ) : m.streaming ? (
          <span className="ui-caret text-sm text-fg-subtle" aria-label="Thinking" />
        ) : null}
        {m.error && (
          <Callout tone={m.error === "Stopped." ? "info" : "danger"} className="mt-2">
            {m.error}
          </Callout>
        )}
        {!!m.sources?.length && <Sources sources={m.sources} />}
      </div>
    </div>
  );
}

function Sources({ sources }: { sources: ChatSource[] }) {
  return (
    <motion.ol
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      aria-label="Sources"
      className="mt-3 flex flex-wrap gap-1.5"
    >
      {sources.map((s) => (
        <li key={s.n}>
          <a
            href={s.url}
            target="_blank"
            rel="nofollow noopener noreferrer"
            title={`${s.repo}/${s.path}:${s.start_line}-${s.end_line} @ ${s.commit_sha.slice(0, 7)}`}
            className="group inline-flex h-6 max-w-72 items-center gap-1.5 rounded-md border border-border bg-surface-2/60 pl-1 pr-2 text-2xs text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
          >
            <span className="tabular grid h-4 min-w-4 place-items-center rounded-sm bg-accent-soft px-1 font-semibold text-accent-text">{s.n}</span>
            <FileCode2 className="size-3 shrink-0 text-fg-subtle" aria-hidden="true" />
            <span className="truncate font-mono">
              {s.path}:{s.start_line}-{s.end_line}
            </span>
          </a>
        </li>
      ))}
    </motion.ol>
  );
}

function ThreadList({
  threads: items,
  loading,
  activeId,
  loadingId,
  onOpen,
  onDeleted,
}: {
  threads: Thread[] | undefined;
  loading: boolean;
  activeId: string | null;
  loadingId: string | null;
  onOpen: (t: Thread) => void;
  onDeleted: (id: string) => void;
}) {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState<Thread | null>(null);
  const del = useMutation({
    mutationFn: (id: string) => threads.remove(id),
    onSuccess: (_d, id) => {
      setConfirm(null);
      onDeleted(id);
      void qc.invalidateQueries({ queryKey: qk.threads(slug) });
    },
    onError: (e) => toast.error("Couldn't delete conversation", errorMessage(e)),
  });

  if (loading) return <SkeletonRows rows={4} />;
  if (!items?.length) return <p className="px-2 py-3 text-xs text-fg-subtle">No conversations yet.</p>;
  return (
    <>
      <ul className="ui-stagger flex flex-col gap-0.5" aria-label="Conversations">
        {items.map((t, i) => (
          <li key={t.id} style={{ ["--i" as string]: Math.min(i, 12) }} className="group relative">
            <button
              type="button"
              onClick={() => onOpen(t)}
              aria-current={t.id === activeId ? "true" : undefined}
              className={cn(
                "flex w-full flex-col rounded-md px-2 py-1.5 pr-8 text-left transition-colors duration-150",
                t.id === activeId ? "bg-surface-2 text-fg ring-1 ring-border" : "text-fg-muted hover:bg-surface-2/70 hover:text-fg",
                loadingId === t.id && "animate-pulse",
              )}
            >
              <span className="truncate text-xs font-medium">{t.title || "Untitled"}</span>
              <RelativeTime iso={t.created_at} className="text-2xs text-fg-subtle" />
            </button>
            <IconButton
              size="xs"
              label="Delete conversation"
              icon={<Trash2 />}
              className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
              onClick={() => setConfirm(t)}
            />
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="Delete conversation?"
        description={confirm?.title ?? undefined}
        confirmLabel="Delete"
        loading={del.isPending}
        onConfirm={() => confirm && del.mutate(confirm.id)}
      />
    </>
  );
}
