import { ArrowRight, Check, Play } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { Button } from "@/components/ui";
import { Magnetic, SplitWords } from "./fx";
import { EASE, useActive } from "./motion-utils";

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

  return (
    <section ref={ref} id="product" className="relative isolate overflow-hidden">
      <div className="l-mesh absolute inset-0 -z-20" aria-hidden="true" />
      <div className="l-grid absolute inset-0 -z-10" aria-hidden="true" />

      <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-5 pb-20 pt-32 sm:pt-36 lg:min-h-[min(100svh,900px)] lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:gap-10 lg:pb-16 lg:pt-28">
        {/* left: copy */}
        <div className="min-w-0 text-center lg:text-left">
          <h1 className="text-[clamp(1.6rem,7.4vw,2.9rem)] font-semibold leading-[1.06] lg:text-[clamp(2.1rem,3.1vw,2.85rem)] tracking-[-0.045em]">
            <SplitWords text="Your code, documented." delay={0.1} gradientWords={["documented."]} className="whitespace-nowrap" />
            <br />
            <SplitWords text="On every push." delay={0.3} className="whitespace-nowrap" />
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

        {/* right: live product stage */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.9, ease: EASE, delay: 0.35 }}
          className="relative min-w-0"
        >
          <div className="mx-auto aspect-[84/68] w-full max-w-xl lg:max-w-none">
            <Suspense fallback={<div className="size-full" />}>
              <DemoVideo active={active} />
            </Suspense>
          </div>
        </motion.div>
      </div>
    </section>
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
    <div className="inline-flex max-w-full items-center gap-3 rounded-xl border border-black/[0.07] bg-white/80 py-2 pl-3 pr-4 text-xs shadow-sm">
      <span className="relative grid size-2 place-items-center">
        <span className="l-pulse-dot absolute size-2 rounded-full bg-[var(--l-emerald)]" />
      </span>
      <span className="text-fg-subtle">Live</span>
      <span className="h-3 w-px bg-black/10" />
      <span className="relative h-4 w-[17rem] min-w-0 max-w-[calc(100vw-9rem)] overflow-hidden text-left">
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
