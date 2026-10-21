import { FileText, GitBranch, MessagesSquare, RefreshCw } from "lucide-react";
import { motion, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { useRef, type ReactNode } from "react";
import { GitHubIcon } from "@/components/BrandIcons";
import { Reveal } from "./fx";

const STEPS = [
  {
    icon: <GitHubIcon className="size-5" />,
    title: "Connect a repo",
    text: "Install the Docify GitHub App and pick repositories. Read-only, scoped to exactly what you choose.",
    chip: "GitHub App · read-only",
  },
  {
    icon: <FileText className="size-5" />,
    title: "Docs write themselves",
    text: "The worker reads every file, builds a searchable index and writes an Overview, a Setup guide and an API reference — every claim cited.",
    chip: "Claude · pgvector · citations",
  },
  {
    icon: <RefreshCw className="size-5" />,
    title: "Every push keeps them fresh",
    text: "A push lands in a queue — even while servers sleep. Only the docs that the change touches are rewritten, plus a changelog entry.",
    chip: "Webhook → Lambda → SQS → worker",
  },
  {
    icon: <MessagesSquare className="size-5" />,
    title: "Ask anything",
    text: "Search and chat across your code. Answers stream in with links to the exact file and line numbers.",
    chip: "Hybrid search · RAG",
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 70%", "end 60%"] });
  const progress = useSpring(scrollYProgress, { stiffness: 90, damping: 24 });

  return (
    <section id="how" className="relative mx-auto max-w-6xl scroll-mt-24 px-5 py-28 sm:py-36">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="l-eyebrow">How it works</p>
        <h2 className="mt-3 text-[clamp(2rem,4.5vw,3.4rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
          From <span className="l-gradient-text">git push</span> to up-to-date docs.
          <br className="hidden sm:block" /> Automatically.
        </h2>
      </Reveal>

      <div ref={ref} className="relative mx-auto mt-20 max-w-3xl">
        {/* the line that draws itself as you scroll */}
        <svg className="absolute left-[27px] top-0 h-full w-[2px] overflow-visible" preserveAspectRatio="none" aria-hidden="true">
          <line x1="1" y1="0" x2="1" y2="100%" stroke="rgb(15 15 30 / 0.08)" strokeWidth="2" />
          <motion.line
            x1="1"
            y1="0"
            x2="1"
            y2="100%"
            stroke="url(#how-grad)"
            strokeWidth="2"
            style={{ pathLength: progress }}
          />
          <defs>
            <linearGradient id="how-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--l-indigo)" />
              <stop offset="0.5" stopColor="var(--l-violet)" />
              <stop offset="1" stopColor="var(--l-cyan)" />
            </linearGradient>
          </defs>
        </svg>

        <ol className="space-y-14">
          {STEPS.map((s, i) => (
            <Step key={s.title} index={i} total={STEPS.length} progress={progress} {...s} />
          ))}
        </ol>
      </div>
    </section>
  );
}

function Step({ index, total, progress, icon, title, text, chip }: {
  index: number;
  total: number;
  progress: MotionValue<number>;
  icon: ReactNode;
  title: string;
  text: string;
  chip: string;
}) {
  const at = index / (total - 1 || 1);
  const glow = useTransform(progress, [Math.max(0, at - 0.12), at], [0, 1]);
  const scale = useTransform(glow, [0, 1], [0.85, 1]);
  return (
    <li className="relative flex gap-6">
      <motion.div
        style={{ scale }}
        className="relative z-10 grid size-14 shrink-0 place-items-center rounded-2xl border border-black/10 bg-white text-fg"
      >
        <motion.span
          style={{ opacity: glow }}
          className="absolute inset-0 rounded-2xl bg-gradient-to-br from-[var(--l-indigo)] to-[var(--l-violet)] shadow-[0_0_40px_-6px_var(--l-indigo)]"
        />
        <span className="relative">{icon}</span>
      </motion.div>
      <Reveal delay={0.05} className="pt-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-fg-subtle">0{index + 1}</span>
          <h3 className="text-xl font-semibold tracking-tight">{title}</h3>
        </div>
        <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-fg-muted">{text}</p>
        <span className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-black/[0.08] bg-black/[0.03] px-2.5 py-1 font-mono text-[11px] text-fg-subtle">
          <GitBranch className="size-3" />
          {chip}
        </span>
      </Reveal>
    </li>
  );
}
