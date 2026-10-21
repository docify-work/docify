import { CheckCircle2, FileText, GitCommitHorizontal, Lock, MessagesSquare, Search, ShieldCheck, Wallet } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { GlowCard, Reveal } from "./fx";
import { EASE } from "./motion-utils";

/** Cycles 0..n-1 every `ms` (static for reduced motion). */
function useCycle(n: number, ms: number) {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setI((v) => (v + 1) % n), ms);
    return () => clearInterval(id);
  }, [n, ms, reduce]);
  return i;
}

function Tile({ icon, title, text, children, className }: {
  icon: ReactNode;
  title: string;
  text: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <GlowCard className={cn("flex flex-col overflow-hidden p-6", className)}>
      <div className="flex items-center gap-2.5">
        <span className="grid size-9 place-items-center rounded-xl bg-[var(--l-indigo)]/15 text-[var(--accent-text)] ring-1 ring-inset ring-[var(--l-indigo)]/30">
          {icon}
        </span>
        <h3 className="text-[17px] font-semibold tracking-tight">{title}</h3>
      </div>
      <p className="mt-2.5 text-sm leading-relaxed text-fg-muted">{text}</p>
      {children && <div className="mt-6 flex-1">{children}</div>}
    </GlowCard>
  );
}

export function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl scroll-mt-24 px-5 py-24 sm:py-32">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="l-eyebrow">Features</p>
        <h2 className="mt-3 text-[clamp(2rem,4.5vw,3.4rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
          Everything docs should have been.
        </h2>
      </Reveal>

      <div className="mt-16 grid auto-rows-[minmax(0,1fr)] gap-4 md:grid-cols-6">
        <Reveal className="md:col-span-4"><Tile icon={<FileText className="size-[18px]" />} title="Docs that write themselves" text="Overview, setup guide and API reference — generated from the code, every sentence linked to its source." className="h-full"><DocBuilder /></Tile></Reveal>
        <Reveal delay={0.08} className="md:col-span-2"><Tile icon={<GitCommitHorizontal className="size-[18px]" />} title="Always in sync" text="Each push rewrites only what changed and logs a changelog entry." className="h-full"><CommitGraph /></Tile></Reveal>
        <Reveal delay={0.04} className="md:col-span-2"><Tile icon={<MessagesSquare className="size-[18px]" />} title="Ask anything" text="Chat that cites file and line — or honestly says it doesn't know." className="h-full"><ChatBubble /></Tile></Reveal>
        <Reveal delay={0.1} className="md:col-span-2"><Tile icon={<Search className="size-[18px]" />} title="Hybrid search" text="Meaning-based vectors + exact keywords, fused into one ranking." className="h-full"><SearchDemo /></Tile></Reveal>
        <Reveal delay={0.14} className="md:col-span-2"><Tile icon={<CheckCircle2 className="size-[18px]" />} title="Review before publish" text="Auto-publish by default — or flip one switch to approve every change." className="h-full"><ApproveDemo /></Tile></Reveal>
        <Reveal delay={0.06} className="md:col-span-3"><Tile icon={<ShieldCheck className="size-[18px]" />} title="Secrets never leave" text="Keys and passwords are redacted before anything is stored or sent to a model. Teams can't see each other's data." className="h-full"><Redaction /></Tile></Reveal>
        <Reveal delay={0.12} className="md:col-span-3"><Tile icon={<Wallet className="size-[18px]" />} title="AI on a budget" text="Daily and per-workspace spend caps. Hit the cap and jobs wait instead of burning money." className="h-full"><BudgetGauge /></Tile></Reveal>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------- mini animations */

function DocBuilder() {
  const step = useCycle(7, 700);
  const lines = [88, 72, 95, 60, 80];
  return (
    <div className="rounded-xl border border-black/[0.06] bg-[#f7f7fa] p-4">
      <div className="mb-3 flex gap-2">
        {["Overview", "Setup", "API"].map((t, i) => (
          <span key={t} className={cn("rounded-md px-2 py-0.5 text-[11px] transition-colors duration-500", step % 3 === i ? "bg-[var(--l-indigo)]/25 text-[var(--accent-text)]" : "text-fg-subtle")}>
            {t}
          </span>
        ))}
      </div>
      <div className="h-4 w-1/3 rounded bg-black/15" />
      <div className="mt-3 space-y-2">
        {lines.map((w, i) => (
          <div key={i} className="flex items-center gap-2">
            <motion.div
              className="h-2.5 rounded bg-black/[0.09]"
              initial={false}
              animate={{ width: step > i ? `${w}%` : "0%" }}
              transition={{ duration: 0.6, ease: EASE }}
            />
            <motion.span
              initial={false}
              animate={{ opacity: step > i + 1 ? 1 : 0, scale: step > i + 1 ? 1 : 0.6 }}
              className="shrink-0 rounded border border-[var(--l-indigo)]/40 px-1 font-mono text-[9px] text-[var(--accent-text)]"
            >
              L{12 + i * 7}
            </motion.span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommitGraph() {
  const head = useCycle(5, 1100);
  return (
    <svg viewBox="0 0 220 110" className="h-28 w-full" aria-hidden="true">
      <path d="M10 70 H210" stroke="rgb(15 15 30 / 0.12)" strokeWidth="2" />
      <path d="M60 70 C 80 70, 80 30, 110 30 H150 C 170 30, 170 70, 190 70" stroke="var(--l-violet)" strokeOpacity="0.5" strokeWidth="2" fill="none" className="l-flow" />
      {[20, 60, 110, 150, 190].map((x, i) => {
        const y = i === 2 || i === 3 ? 30 : 70;
        const on = i <= head;
        return (
          <g key={x}>
            <motion.circle cx={x} cy={y} r={7} initial={false} animate={{ fill: on ? "#6366f1" : "#e4e4ec", scale: i === head ? 1.25 : 1 }} stroke="#4338ca" strokeWidth={i === head ? 2 : 0} style={{ transformBox: "fill-box", transformOrigin: "center" }} />
            {i === head && <circle cx={x} cy={y} r={12} fill="none" stroke="#6366f1" className="l-pulse-dot" />}
          </g>
        );
      })}
      <text x="10" y="102" fill="#8a8a96" fontSize="10" fontFamily="monospace">main · docs v{head + 1}</text>
    </svg>
  );
}

function ChatBubble() {
  const phase = useCycle(4, 1300);
  return (
    <div className="space-y-2 text-[12px]">
      <div className="ml-auto w-fit rounded-xl rounded-br-sm bg-[var(--l-indigo)]/25 px-3 py-1.5">Where is auth handled?</div>
      <AnimatePresence mode="wait">
        {phase === 0 ? (
          <motion.div key="t" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex w-fit gap-1 rounded-xl bg-black/[0.05] px-3 py-2.5">
            {[0, 1, 2].map((i) => (
              <motion.span key={i} className="size-1.5 rounded-full bg-fg-muted" animate={{ y: [0, -3, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.12 }} />
            ))}
          </motion.div>
        ) : (
          <motion.div key="a" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="w-fit max-w-[95%] rounded-xl rounded-bl-sm bg-black/[0.05] px-3 py-2 leading-relaxed text-fg-muted">
            In <span className="font-mono text-[var(--accent-text)]">auth/service.py</span>, sessions are created after Argon2 checks.
            <span className="ml-1 rounded border border-[var(--l-indigo)]/40 px-1 font-mono text-[10px] text-[var(--accent-text)]">[1]</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const QUERIES = [
  { q: "rate limit", hits: ["cache.py", "routers/auth.py"] },
  { q: "session cookie", hits: ["auth/sessions.py", "middleware.py"] },
  { q: "retry backoff", hits: ["jobs/service.py", "worker/runner.py"] },
];

function SearchDemo() {
  const i = useCycle(QUERIES.length, 1800);
  const q = QUERIES[i]!;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 rounded-lg border border-black/[0.08] bg-[#f7f7fa] px-3 py-2 text-[12px]">
        <Search className="size-3.5 text-fg-subtle" />
        <AnimatePresence mode="wait">
          <motion.span key={q.q} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="l-caret">
            {q.q}
          </motion.span>
        </AnimatePresence>
      </div>
      <AnimatePresence mode="popLayout">
        {q.hits.map((h, k) => (
          <motion.div key={q.q + h} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ delay: 0.15 + k * 0.08 }}
            className="flex items-center justify-between rounded-md bg-black/[0.03] px-3 py-1.5 font-mono text-[11px] text-fg-muted">
            {h}
            <span className="text-[var(--l-emerald)]">{(0.92 - k * 0.11).toFixed(2)}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function ApproveDemo() {
  const on = useCycle(2, 1600) === 1;
  return (
    <div className="flex items-center justify-between rounded-xl border border-black/[0.06] bg-[#f7f7fa] px-4 py-3">
      <div>
        <div className="text-[12px] font-medium">Require approval</div>
        <div className="text-[11px] text-fg-subtle">{on ? "Admins review each change" : "Changes publish instantly"}</div>
      </div>
      <motion.div className="flex h-6 w-11 items-center rounded-full p-0.5" animate={{ backgroundColor: on ? "#6366f1" : "#2e2e3c" }}>
        <motion.span layout transition={{ type: "spring", stiffness: 500, damping: 30 }} className={cn("size-5 rounded-full bg-white shadow", on && "ml-auto")} />
      </motion.div>
    </div>
  );
}

function Redaction() {
  const masked = useCycle(2, 1800) === 1;
  return (
    <div className="rounded-xl border border-black/[0.06] bg-[#f7f7fa] p-4 font-mono text-[12px] leading-6">
      <div className="text-fg-subtle"># settings.py</div>
      <div>
        <span className="text-[#7c3aed]">AWS_KEY</span> = <span className="text-[var(--l-amber)]">"</span>
        <AnimatePresence mode="wait">
          <motion.span key={String(masked)} initial={{ opacity: 0, filter: "blur(4px)" }} animate={{ opacity: 1, filter: "blur(0px)" }} exit={{ opacity: 0, filter: "blur(4px)" }}
            className={masked ? "rounded bg-[var(--l-emerald)]/15 px-1 text-[var(--l-emerald)]" : "text-[var(--l-amber)]"}>
            {masked ? "[REDACTED]" : "AKIAIOSFODNN7EXAMPLE"}
          </motion.span>
        </AnimatePresence>
        <span className="text-[var(--l-amber)]">"</span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-fg-subtle">
        <Lock className="size-3" /> redacted before storage &amp; before any model sees it
      </div>
    </div>
  );
}

function BudgetGauge() {
  const v = [0.18, 0.42, 0.67, 0.86, 1][useCycle(5, 1200)]!;
  const blocked = v >= 1;
  const R = 46;
  const L = Math.PI * R;
  return (
    <div className="flex items-center gap-6">
      <svg viewBox="0 0 120 70" className="h-24 w-40" aria-hidden="true">
        <path d={`M14 62 A ${R} ${R} 0 0 1 106 62`} stroke="rgb(15 15 30 / 0.08)" strokeWidth="10" fill="none" strokeLinecap="round" />
        <motion.path d={`M14 62 A ${R} ${R} 0 0 1 106 62`} stroke={blocked ? "#fbbf24" : "url(#bg)"} strokeWidth="10" fill="none" strokeLinecap="round"
          strokeDasharray={L} initial={false} animate={{ strokeDashoffset: L * (1 - v) }} transition={{ duration: 0.9, ease: EASE }} />
        <defs>
          <linearGradient id="bg"><stop offset="0" stopColor="#34d399" /><stop offset="1" stopColor="#6366f1" /></linearGradient>
        </defs>
      </svg>
      <div className="text-sm">
        <div className="font-mono text-2xl font-semibold tabular-nums">${(v * 2).toFixed(2)}<span className="text-sm text-fg-subtle"> / $2.00 today</span></div>
        <div className={cn("mt-1 text-xs", blocked ? "text-[var(--l-amber)]" : "text-fg-subtle")}>
          {blocked ? "Cap reached — jobs parked until tomorrow" : "Within budget"}
        </div>
      </div>
    </div>
  );
}
