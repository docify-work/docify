/** Landing-page motion constants and hooks (kept apart from components for fast refresh). */
import Lenis from "lenis";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

export const EASE = [0.22, 1, 0.36, 1] as const;

/** Buttery smooth scrolling for the landing page only (destroyed on unmount). */
export function useSmoothScroll(): void {
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    const lenis = new Lenis({ duration: 1.1, easing: (t) => 1 - Math.pow(1 - t, 3), smoothWheel: true });
    let frame = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
    };
  }, [reduce]);
}

/** Sets --mx/--my (px) on the element as the pointer moves: drives `.l-spotlight`. */
export function useSpotlight<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onMove = (e: globalThis.PointerEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    el.addEventListener("pointermove", onMove);
    return () => el.removeEventListener("pointermove", onMove);
  }, []);
  return ref;
}
