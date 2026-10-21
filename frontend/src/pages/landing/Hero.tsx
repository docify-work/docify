import { ArrowRight, Check, GitCommitHorizontal, MessagesSquare, Play, RefreshCw, Workflow } from "lucide-react";
import { motion, useScroll, useTransform } from "motion/react";
import { lazy, Suspense, useCallback, useRef, useState } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { Magnetic, SplitWords } from "./fx";
import { EASE, useActive } from "./motion-utils";

const DemoVideo = lazy(() => import("./DemoVideo"));

const CHAPTERS = [
  { label: "You push", icon: GitCommitHorizontal },
  { label: "Docify reacts", icon: Workflow },
  { label: "Docs rewrite", icon: RefreshCw },
  { label: "Ask anything", icon: MessagesSquare },
];

export function Hero({ primaryHref, primaryLabel, demoHref }: {
  primaryHref: string;
  primaryLabel: string;
  demoHref: string | null;
}) {
  return (
    <section id="product" className="relative isolate overflow-hidden pt-32 sm:pt-40">
      <div className="l-mesh absolute inset-0 -z-20" aria-hidden="true" />
      <div className="l-grid absolute inset-0 -z-10" aria-hidden="true" />

      <div className="relative mx-auto max-w-6xl px-5 text-center">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
          className="mx-auto inline-flex items-center gap-2 rounded-full border border-black/[0.08] bg-white py-1 pl-1 pr-3 text-xs text-fg-muted shadow-sm"
        >
          <span className="rounded-full bg-[var(--l-indigo)] px-2 py-0.5 text-[11px] font-semibold text-white">New</span>
          Docs that update themselves on every push
        </motion.span>

        <h1 className="mx-auto mt-7 max-w-4xl text-[clamp(2.7rem,7vw,5.8rem)] font-semibold leading-[0.95] tracking-[-0.05em]">
          <SplitWords text="Your code changes." delay={0.15} />
          <br />
          <SplitWords text="Your docs keep up." delay={0.4} gradientWords={["docs"]} />
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.75 }}
          className="mx-auto mt-6 max-w-2xl text-[clamp(1rem,1.6vw,1.2rem)] leading-relaxed text-fg-muted"
        >
          Connect a GitHub repo. Docify writes the docs with AI, rewrites only what changed on every push, and answers
          questions with links to the exact lines.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.9 }}
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <Magnetic>
            <Button asChild variant="primary" className="h-11 rounded-xl px-5 text-[15px] shadow-[0_8px_24px_-8px_rgb(79_70_229/0.55)]">
              <Link to={primaryHref}>
                <GitHubIcon />
                {primaryLabel}
                <ArrowRight />
              </Link>
            </Button>
          </Magnetic>
          {demoHref && (
            <Button asChild variant="secondary" className="h-11 rounded-xl border-black/10 bg-white px-5 text-[15px] shadow-sm hover:bg-[#f5f5f8]">
              <Link to={demoHref}>
                <Play />
                Explore the live demo
              </Link>
            </Button>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.1, duration: 0.8 }}
          className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-xs text-fg-subtle"
        >
          {["Free to try", "Read-only GitHub access", "Line-level citations"].map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <Check className="size-3.5 text-[var(--l-emerald)]" />
              {t}
            </span>
          ))}
        </motion.div>
      </div>

      <HeroFilm />
    </section>
  );
}

/** The product film right in the hero: framed like an app window, with chapter tabs below. */
function HeroFilm() {
  const frameRef = useRef<HTMLDivElement>(null);
  const active = useActive(frameRef);
  const [scene, setScene] = useState(0);
  const [jump, setJump] = useState({ scene: 0, key: 0 });
  const onScene = useCallback((s: number) => setScene(s), []);
  const { scrollYProgress } = useScroll({ target: frameRef, offset: ["start end", "start 35%"] });
  // Transform-only entrance as it scrolls into place (compositor; no tilt, no animated shadow).
  const scale = useTransform(scrollYProgress, [0, 1], [0.94, 1]);
  const y = useTransform(scrollYProgress, [0, 1], [30, 0]);

  return (
    <div className="relative mx-auto mt-16 max-w-6xl px-5 pb-20 sm:mt-20 sm:pb-28">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease: EASE, delay: 0.5 }}
      >
        <motion.div ref={frameRef} style={{ scale, y }} className="origin-top will-change-transform">
          <div className="l-glow-border rounded-[22px] p-[1.5px] shadow-[0_40px_90px_-45px_rgb(79_70_229/0.45)]">
            <div className="overflow-hidden rounded-[21px] bg-white">
              <div className="flex h-10 items-center gap-2 border-b border-black/[0.06] px-4">
                <span className="size-2.5 rounded-full bg-[#ff5f57]" />
                <span className="size-2.5 rounded-full bg-[#febc2e]" />
                <span className="size-2.5 rounded-full bg-[#28c840]" />
                <span className="mx-auto rounded-md bg-black/[0.04] px-3 py-1 font-mono text-[11px] text-fg-subtle">
                  docify.work — product tour
                </span>
              </div>
              <div className="aspect-video bg-[#f8f8fb]">
                <Suspense fallback={<div className="size-full" />}>
                  <DemoVideo active={active} jump={jump} onScene={onScene} />
                </Suspense>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>

      <div role="tablist" aria-label="Product tour chapters" className="mx-auto mt-6 grid max-w-3xl grid-cols-2 gap-2 sm:grid-cols-4">
        {CHAPTERS.map(({ label, icon: Icon }, i) => {
          const on = scene === i;
          return (
            <button
              key={label}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => {
                setScene(i);
                setJump((j) => ({ scene: i, key: j.key + 1 }));
              }}
              className={cn(
                "relative flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors",
                on ? "text-fg" : "text-fg-subtle hover:text-fg-muted",
              )}
            >
              {on && (
                <motion.span
                  layoutId="chapter-pill"
                  className="absolute inset-0 -z-10 rounded-xl border border-black/[0.08] bg-white shadow-sm"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <span className={cn("font-mono text-[11px]", on ? "text-[var(--accent-text)]" : "text-fg-subtle")}>0{i + 1}</span>
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
