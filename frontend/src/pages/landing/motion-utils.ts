/** Landing-page motion constants and hooks (kept apart from components for fast refresh). */
import Lenis from "lenis";
import { useInView, useReducedMotion } from "motion/react";
import { useEffect, type RefObject } from "react";

export const EASE = [0.22, 1, 0.36, 1] as const;
export const NAV_OFFSET = 88;

let lenis: Lenis | null = null;

/** Smooth scrolling for the landing page only (destroyed on unmount). */
export function useSmoothScroll(): void {
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    lenis = new Lenis({ duration: 1.05, easing: (t) => 1 - Math.pow(1 - t, 3), smoothWheel: true });
    let frame = 0;
    const raf = (time: number) => {
      lenis?.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(frame);
      lenis?.destroy();
      lenis = null;
    };
  }, [reduce]);
}

/** Smoothly scroll to a section (nav links). Falls back to native smooth scroll. */
export function scrollToSection(id: string): void {
  const el = document.getElementById(id);
  if (!el) return;
  if (lenis) {
    lenis.scrollTo(el, { offset: -NAV_OFFSET, duration: 1.2 });
  } else {
    const top = el.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
    window.scrollTo({ top, behavior: "smooth" });
  }
  history.replaceState(null, "", `#${id}`);
}

/**
 * True while the element is (nearly) on screen and motion is allowed.
 * Every JS-driven loop on the page checks this, so off-screen sections cost nothing.
 */
export function useActive(ref: RefObject<Element | null>): boolean {
  const reduce = useReducedMotion();
  const inView = useInView(ref, { margin: "120px 0px" });
  return inView && !reduce;
}
