import { ArrowRight } from "lucide-react";
import { motion, useMotionValueEvent, useScroll, useSpring } from "motion/react";
import { useState } from "react";
import { Link } from "react-router";
import { LogoMark } from "@/components/Logo";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { EASE } from "./motion-utils";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#demo", label: "Product" },
  { href: "#features", label: "Features" },
  { href: "#architecture", label: "Architecture" },
];

export function Nav({ signedIn, demoHref }: { signedIn: boolean; demoHref: string | null }) {
  const { scrollY, scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 24, mass: 0.3 });
  const [scrolled, setScrolled] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 24));

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: EASE }}
      className="fixed inset-x-0 top-0 z-50 flex justify-center px-3 pt-3"
    >
      <nav
        className={cn(
          "flex h-12 w-full max-w-6xl items-center gap-2 rounded-2xl px-3 transition-all duration-500",
          scrolled
            ? "border border-black/[0.08] bg-white/75 shadow-[0_8px_30px_-14px_rgb(30_27_75/0.25)] backdrop-blur-xl"
            : "border border-transparent",
        )}
        aria-label="Main"
      >
        <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight" aria-label="Docify home">
          <LogoMark size={24} />
          <span className="text-[15px]">Docify</span>
        </Link>
        <div className="ml-6 hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-lg px-2.5 py-1.5 text-sm text-fg-muted transition-colors hover:bg-black/[0.04] hover:text-fg"
            >
              {l.label}
            </a>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          {demoHref && (
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link to={demoHref}>Live demo</Link>
            </Button>
          )}
          <Button asChild variant="primary" size="sm">
            <Link to={signedIn ? "/app" : "/signup"}>
              {signedIn ? "Open app" : "Get started"}
              <ArrowRight />
            </Link>
          </Button>
        </div>
      </nav>
      <motion.div
        aria-hidden="true"
        style={{ scaleX: progress }}
        className="fixed inset-x-0 top-0 h-[2px] origin-left bg-gradient-to-r from-[var(--l-indigo)] via-[var(--l-violet)] to-[var(--l-cyan)]"
      />
    </motion.header>
  );
}
