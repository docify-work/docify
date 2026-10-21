import { ArrowRight, Check, Play } from "lucide-react";
import { motion } from "motion/react";
import { lazy, Suspense, useCallback, useRef, useState, useSyncExternalStore } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { Button } from "@/components/ui";
import { Magnetic, SplitWords } from "./fx";
import { EASE, useActive } from "./motion-utils";
import { CHAPTERS, FILM, LAYOUT } from "./remotion/config";

// Start fetching the film chunk as soon as the landing chunk loads — it *is* the hero.
const loadFilm = () => import("./DemoVideo");
void loadFilm();
const DemoVideo = lazy(loadFilm);

const WIDE = "(min-width: 1024px)";
function useWide(): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(WIDE);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(WIDE).matches,
    () => true,
  );
}

type Props = { primaryHref: string; primaryLabel: string; demoHref: string | null };

/** Film pixels → container-query width units (the film is always FILM.width wide in its own space). */
const cq = (px: number) => `${(px / FILM.width) * 100}cqw`;

/**
 * The hero IS the film. On desktop the Remotion composition renders the headline, copy and the live
 * product stage; only the buttons and chapter tabs are real HTML laid over it (clickable, accessible).
 * On small screens the headline is HTML and the film shows just the stage.
 */
export function Hero(props: Props) {
  const wide = useWide();
  const ref = useRef<HTMLElement>(null);
  const active = useActive(ref);
  const [scene, setScene] = useState(0);
  const [jump, setJump] = useState({ scene: 0, key: 0 });
  const [ready, setReady] = useState(false);
  const onScene = useCallback((s: number) => setScene(s), []);
  const onReady = useCallback(() => setReady(true), []);
  const go = (i: number) => {
    setScene(i);
    setJump((j) => ({ scene: i, key: j.key + 1 }));
  };

  return (
    <section ref={ref} id="product" className="relative isolate overflow-hidden bg-[#fbfbfd]">
      {wide ? (
        <div className="l-hero-film relative mx-auto w-full max-w-[calc(100svh*16/9)] [container-type:inline-size]">
          {/* SEO / screen readers: the visible headline is drawn inside the film */}
          <h1 className="sr-only">Your code changes. Your docs keep up.</h1>
          <p className="sr-only">
            Connect a GitHub repo. Docify writes the docs with AI, rewrites only what changed on every push, and
            answers questions with links to the exact lines.
          </p>
          <div className="aspect-video w-full">
            <Suspense fallback={<div className="size-full" />}>
              <DemoVideo variant="full" active={active} jump={jump} onScene={onScene} onReady={onReady} />
            </Suspense>
          </div>
          {ready && <FilmControls {...props} scene={scene} onPick={go} />}
        </div>
      ) : (
        <MobileHero {...props} active={active} jump={jump} onScene={onScene} />
      )}
    </section>
  );
}

/** Real buttons + invisible chapter hit-areas placed exactly over the film's drawn layout. */
function FilmControls({ primaryHref, primaryLabel, demoHref, scene, onPick }: Props & {
  scene: number;
  onPick: (i: number) => void;
}) {
  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: EASE, delay: 0.85 }}
        className="absolute flex items-center"
        style={{ left: cq(LAYOUT.left), top: cq(LAYOUT.ctaTop), height: cq(LAYOUT.ctaHeight), gap: cq(16) }}
      >
        <Magnetic>
          <Button
            asChild
            variant="primary"
            className="h-auto rounded-[0.8cqw] shadow-[0_8px_24px_-8px_rgb(79_70_229/0.55)] [&_svg]:size-[1.1cqw]"
            style={{ height: cq(LAYOUT.ctaHeight), paddingInline: cq(30), fontSize: cq(22), gap: cq(10) }}
          >
            <Link to={primaryHref}>
              <GitHubIcon />
              {primaryLabel}
              <ArrowRight />
            </Link>
          </Button>
        </Magnetic>
        {demoHref && (
          <Button
            asChild
            variant="secondary"
            className="h-auto rounded-[0.8cqw] border-black/10 bg-white shadow-sm hover:bg-[#f5f5f8] [&_svg]:size-[1.1cqw]"
            style={{ height: cq(LAYOUT.ctaHeight), paddingInline: cq(28), fontSize: cq(22), gap: cq(10) }}
          >
            <Link to={demoHref}>
              <Play />
              Live demo
            </Link>
          </Button>
        )}
      </motion.div>

      <div
        role="tablist"
        aria-label="Product tour chapters"
        className="absolute flex"
        style={{ left: cq(LAYOUT.left), top: cq(LAYOUT.chaptersTop - 14), gap: cq(LAYOUT.chapterGap) }}
      >
        {CHAPTERS.map((label, i) => (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={scene === i}
            aria-label={`Chapter ${i + 1}: ${label}`}
            title={`Jump to: ${label}`}
            onClick={() => onPick(i)}
            className="cursor-pointer rounded-lg transition-colors hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
            style={{ width: cq(LAYOUT.chapterWidth), height: cq(LAYOUT.chapterHeight + 20) }}
          />
        ))}
      </div>
    </>
  );
}

function MobileHero({ primaryHref, primaryLabel, demoHref, active, jump, onScene }: Props & {
  active: boolean;
  jump: { scene: number; key: number };
  onScene: (s: number) => void;
}) {
  return (
    <div className="relative px-5 pb-14 pt-28 text-center">
      <div className="l-mesh absolute inset-0 -z-10" aria-hidden="true" />
      <span className="inline-flex items-center gap-2 rounded-full border border-black/[0.08] bg-white py-1 pl-1 pr-3 text-xs text-fg-muted shadow-sm">
        <span className="rounded-full bg-[var(--l-indigo)] px-2 py-0.5 text-[11px] font-semibold text-white">New</span>
        Docs that update on every push
      </span>
      <h1 className="mx-auto mt-6 text-[clamp(2.4rem,10vw,4rem)] font-semibold leading-[0.98] tracking-[-0.05em]">
        <SplitWords text="Your code changes." delay={0.1} />
        <br />
        <SplitWords text="Your docs keep up." delay={0.3} gradientWords={["docs"]} />
      </h1>
      <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-fg-muted">
        Connect a GitHub repo. Docify writes the docs with AI, rewrites only what changed on every push, and answers
        questions with links to the exact lines.
      </p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button asChild variant="primary" className="h-11 rounded-xl px-5">
          <Link to={primaryHref}>
            <GitHubIcon />
            {primaryLabel}
            <ArrowRight />
          </Link>
        </Button>
        {demoHref && (
          <Button asChild variant="secondary" className="h-11 rounded-xl bg-white px-5">
            <Link to={demoHref}>
              <Play />
              Live demo
            </Link>
          </Button>
        )}
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-fg-subtle">
        {["Free to try", "Read-only access", "Cited answers"].map((t) => (
          <span key={t} className="inline-flex items-center gap-1">
            <Check className="size-3.5 text-[var(--l-emerald)]" />
            {t}
          </span>
        ))}
      </div>
      <div className="mx-auto mt-10 aspect-[5/4] w-full max-w-xl overflow-hidden rounded-2xl border border-black/[0.06] bg-white shadow-lg">
        <Suspense fallback={<div className="size-full" />}>
          <DemoVideo variant="stage" active={active} jump={jump} onScene={onScene} />
        </Suspense>
      </div>
    </div>
  );
}
