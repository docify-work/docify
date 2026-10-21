import { useInView } from "motion/react";
import { lazy, Suspense, useRef } from "react";
import { Reveal } from "./fx";

const DemoVideo = lazy(() => import("./DemoVideo"));

const CHAPTERS = ["Push", "Pipeline", "Rewrite", "Ask"];

export function Product() {
  const ref = useRef<HTMLDivElement>(null);
  const near = useInView(ref, { once: true, margin: "400px 0px" });
  return (
    <section id="demo" className="relative scroll-mt-24 px-5 py-24 sm:py-32">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="l-eyebrow">Watch it work</p>
        <h2 className="mt-3 text-[clamp(2rem,4.5vw,3.4rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
          Sixteen seconds, <span className="l-gradient-text">zero manual docs</span>.
        </h2>
        <p className="mt-4 text-[15px] text-fg-muted">A live render of the real flow — composed in code with Remotion.</p>
      </Reveal>

      <Reveal delay={0.1} className="relative mx-auto mt-14 max-w-5xl">
        <div className="pointer-events-none absolute -inset-10 rounded-[40px] bg-gradient-to-r from-[var(--l-indigo)]/30 via-[var(--l-violet)]/20 to-[var(--l-cyan)]/30 blur-3xl" aria-hidden="true" />
        <div ref={ref} className="l-glow-border relative rounded-[20px] p-[2px]">
          <div className="aspect-video overflow-hidden rounded-[18px] bg-white">
            {near ? (
              <Suspense fallback={<div className="size-full animate-pulse bg-black/[0.02]" />}>
                <DemoVideo />
              </Suspense>
            ) : (
              <div className="size-full bg-black/[0.02]" />
            )}
          </div>
        </div>
        <div className="mt-5 flex justify-center gap-2">
          {CHAPTERS.map((c, i) => (
            <span key={c} className="rounded-full border border-black/[0.07] bg-black/[0.03] px-3 py-1 text-xs text-fg-subtle">
              <span className="mr-1.5 font-mono text-[var(--accent-text)]">0{i + 1}</span>
              {c}
            </span>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
