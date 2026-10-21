/**
 * Landing-page motion toolkit. Small, reusable effects built on `motion` + Lenis.
 * All of them degrade to static content for `prefers-reduced-motion`.
 */
import {
  animate,
  motion,
  useInView,
  useMotionValue,
  useReducedMotion,
  useSpring,
  type HTMLMotionProps,
} from "motion/react";
import { Fragment, useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { EASE } from "./motion-utils";


/** Fade + lift + un-blur when scrolled into view. */
export function Reveal({
  children,
  delay = 0,
  y = 24,
  className,
  ...rest
}: { children: ReactNode; delay?: number; y?: number; className?: string } & HTMLMotionProps<"div">) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y, filter: "blur(8px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: 0.8, ease: EASE, delay }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Headline that assembles word by word (each word rises out of a mask). */
export function SplitWords({ text, className, delay = 0, gradientWords = [] }: {
  text: string;
  className?: string;
  delay?: number;
  gradientWords?: string[];
}) {
  const reduce = useReducedMotion();
  const words = text.split(" ");
  return (
    <span className={className} aria-label={text}>
      {words.map((w, i) => (
        <Fragment key={`${w}-${i}`}>
        {i > 0 && " "}
        <span className="inline-block overflow-hidden pb-[0.12em] align-bottom" aria-hidden="true">
          <motion.span
            className={cn("inline-block", gradientWords.includes(w) && "l-gradient-text")}
            initial={reduce ? false : { y: "110%", rotate: 4, opacity: 0 }}
            animate={{ y: "0%", rotate: 0, opacity: 1 }}
            transition={{ duration: 0.9, ease: EASE, delay: delay + i * 0.07 }}
          >
            {w}
          </motion.span>
        </span>
        </Fragment>
      ))}
    </span>
  );
}

/** Card with a cursor-following border glow and an optional 3D tilt. */
export function GlowCard({ children, className, tilt = true }: { children: ReactNode; className?: string; tilt?: boolean }) {
  const reduce = useReducedMotion();
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 160, damping: 18 });
  const sry = useSpring(ry, { stiffness: 160, damping: 18 });

  function onMove(e: PointerEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    e.currentTarget.style.setProperty("--cx", `${x}px`);
    e.currentTarget.style.setProperty("--cy", `${y}px`);
    if (tilt && !reduce) {
      ry.set(((x / r.width) - 0.5) * 8);
      rx.set(-((y / r.height) - 0.5) * 8);
    }
  }
  function onLeave() {
    rx.set(0);
    ry.set(0);
  }
  return (
    <motion.div
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{ rotateX: srx, rotateY: sry, transformPerspective: 900 }}
      className={cn("l-card", className)}
    >
      {children}
    </motion.div>
  );
}

/** Wrapper that pulls its child towards the cursor (for CTA buttons). */
export function Magnetic({ children, strength = 0.35 }: { children: ReactNode; strength?: number }) {
  const reduce = useReducedMotion();
  const x = useSpring(0, { stiffness: 220, damping: 16 });
  const y = useSpring(0, { stiffness: 220, damping: 16 });
  return (
    <motion.div
      style={{ x, y }}
      className="inline-block"
      onPointerMove={(e) => {
        if (reduce) return;
        const r = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * strength);
        y.set((e.clientY - (r.top + r.height / 2)) * strength);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}

/** Number that counts up once it scrolls into view. */
export function CountUp({ to, suffix = "", prefix = "", decimals = 0, className }: {
  to: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px" });
  const reduce = useReducedMotion();
  const [value, setValue] = useState(reduce ? to : 0);
  useEffect(() => {
    if (!inView || reduce) return;
    const controls = animate(0, to, { duration: 1.8, ease: EASE, onUpdate: (v) => setValue(v) });
    return () => controls.stop();
  }, [inView, reduce, to]);
  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      {prefix}
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}
