import { ArrowRight, Check, Play } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { Magnetic, SplitWords } from "./fx";
import { EASE, useActive } from "./motion-utils";
import { CHAPTERS, FILM } from "./remotion/config";

// Start fetching the film chunk as soon as the landing chunk loads — it is the hero visual.
const loadFilm = () => import("./DemoVideo");
void loadFilm();
const DemoVideo = lazy(loadFilm);

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.7, ease: EASE, delay },
});

/** What Docify just did — rotates on the left to make the copy feel alive (cheap: one text swap). */
const ACTIVITY = [
  { file: "routers/auth.py", what: "API reference updated" },
  { file: "cache.py", what: "Overview refreshed" },
  { file: "worker/jobs.py", what: "Setup guide updated" },
  { file: "README.md", what: "Changelog entry added" },
];

export function Hero({ primaryHref, primaryLabel, demoHref }: {
  primaryHref: string;
  primaryLabel: string;
  demoHref: string | null;
}) {
  const ref = useRef<HTMLElement>(null);
  const active = useActive(ref);
  const [scene, setScene] = useState(0);
  const [jump, setJump] = useState({ scene: 0, key: 0 });
  const onScene = useCallback((s: number) => setScene(s), []);

  return (
    <section ref={ref} id="product" className="relative isolate overflow-hidden">
      <div className="l-mesh absolute inset-0 -z-20" aria-hidden="true" />
      <div className="l-grid absolute inset-0 -z-10" aria-hidden="true" />

      <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-32 sm:pt-36 lg:min-h-[min(100svh,900px)] lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:gap-10 lg:pb-16 lg:pt-28">
        {/* left: copy */}
        <div className="text-center lg:text-left">
          <motion.span
            {...fadeUp(0.05)}
            className="inline-flex items-center gap-2 rounded-full border border-black/[0.08] bg-white py-1 pl-1 pr-3 text-xs text-fg-muted shadow-sm"
          >
            <span className="rounded-full bg-[var(--l-indigo)] px-2 py-0.5 text-[11px] font-semibold text-white">New</span>
            Docs that update themselves on every push
          </motion.span>

          <h1 className="mt-6 text-[clamp(2.2rem,3.6vw,3.25rem)] font-semibold leading-[1.04] tracking-[-0.045em]">
            <SplitWords text="Your code changes." delay={0.1} />
            <br />
            <SplitWords text="Your docs keep up." delay={0.3} gradientWords={["docs"]} />
          </h1>

          <motion.p {...fadeUp(0.55)} className="mx-auto mt-5 max-w-md text-[15.5px] leading-relaxed text-fg-muted lg:mx-0">
            Connect a GitHub repo. Docify writes the docs with AI, rewrites only what changed on every push, and
            answers questions with links to the exact lines.
          </motion.p>

          <motion.div {...fadeUp(0.7)} className="mt-7 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
            <Magnetic>
              <Button asChild variant="primary" className="h-10 rounded-xl px-4.5 shadow-[0_8px_24px_-8px_rgb(79_70_229/0.55)]">
                <Link to={primaryHref}>
                  <GitHubIcon />
                  {primaryLabel}
                  <ArrowRight />
                </Link>
              </Button>
            </Magnetic>
            {demoHref && (
              <Button asChild variant="secondary" className="h-10 rounded-xl border-black/10 bg-white px-4.5 shadow-sm hover:bg-[#f5f5f8]">
                <Link to={demoHref}>
                  <Play />
                  Live demo
                </Link>
              </Button>
            )}
          </motion.div>

          <motion.div
            {...fadeUp(0.85)}
            className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-fg-subtle lg:justify-start"
          >
            {["Free to try", "Read-only GitHub access", "Cited answers"].map((t) => (
              <span key={t} className="inline-flex items-center gap-1.5 whitespace-nowrap">
                <Check className="size-3.5 text-[var(--l-emerald)]" />
                {t}
              </span>
            ))}
          </motion.div>

          <motion.div {...fadeUp(1.0)} className="mt-9 flex justify-center lg:justify-start">
            <ActivityTicker active={active} />
          </motion.div>
        </div>

        {/* right: live product stage + chapter progress */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.9, ease: EASE, delay: 0.35 }}
          className="relative"
        >
          <div className="aspect-[84/68] w-full">
            <Suspense fallback={<div className="size-full" />}>
              <DemoVideo active={active} jump={jump} onScene={onScene} />
            </Suspense>
          </div>
          <Chapters
            scene={scene}
            runKey={jump.key}
            active={active}
            onPick={(i) => {
              setScene(i);
              setJump((j) => ({ scene: i, key: j.key + 1 }));
            }}
          />
        </motion.div>
      </div>
    </section>
  );
}

/** 4-step progress under the stage. The fill is a CSS animation (no per-frame React work). */
function Chapters({ scene, runKey, active, onPick }: {
  scene: number;
  runKey: number;
  active: boolean;
  onPick: (i: number) => void;
}) {
  return (
    <div role="tablist" aria-label="Product tour chapters" className="mx-auto mt-2 grid max-w-xl grid-cols-4 gap-3 px-3">
      {CHAPTERS.map((label, i) => {
        const on = scene === i;
        return (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={on}
            title={`Jump to: ${label}`}
            onClick={() => onPick(i)}
            className="group cursor-pointer text-left"
          >
            <span className="block h-[3px] overflow-hidden rounded-full bg-black/[0.08]">
              <span
                key={on ? `${scene}-${runKey}` : "idle"}
                className={cn("block h-full origin-left bg-[linear-gradient(100deg,#4f46e5,#7c3aed_45%,#0891b2)]", on && "l-fill")}
                style={{
                  transform: on ? undefined : `scaleX(${i < scene ? 1 : 0})`,
                  animationDuration: `${FILM.scene / FILM.fps}s`,
                  animationPlayState: active ? "running" : "paused",
                }}
              />
            </span>
            <span className={cn("mt-2 block truncate text-xs transition-colors", on ? "font-medium text-fg" : "text-fg-subtle group-hover:text-fg-muted")}>
              <span className={cn("mr-1 font-mono text-[10px]", on ? "text-[var(--accent-text)]" : "")}>0{i + 1}</span>
              {label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ActivityTicker({ active }: { active: boolean }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setI((v) => (v + 1) % ACTIVITY.length), 2600);
    return () => clearInterval(id);
  }, [active]);
  const a = ACTIVITY[i]!;
  return (
    <div className="inline-flex items-center gap-3 rounded-xl border border-black/[0.07] bg-white/80 py-2 pl-3 pr-4 text-xs shadow-sm">
      <span className="relative grid size-2 place-items-center">
        <span className="l-pulse-dot absolute size-2 rounded-full bg-[var(--l-emerald)]" />
      </span>
      <span className="text-fg-subtle">Live</span>
      <span className="h-3 w-px bg-black/10" />
      <span className="relative h-4 w-[17rem] overflow-hidden text-left">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={i}
            initial={{ y: 14, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -14, opacity: 0 }}
            transition={{ duration: 0.35, ease: EASE }}
            className="absolute inset-0 truncate"
          >
            <span className="font-medium text-fg">{a.what}</span>
            <span className="text-fg-subtle"> · </span>
            <span className="font-mono text-[11px] text-[var(--accent-text)]">{a.file}</span>
          </motion.span>
        </AnimatePresence>
      </span>
    </div>
  );
}
