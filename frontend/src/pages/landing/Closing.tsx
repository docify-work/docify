import { ArrowRight, Play } from "lucide-react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { LogoMark } from "@/components/Logo";
import { Button } from "@/components/ui";
import { CountUp, Magnetic, Reveal } from "./fx";

const STATS = [
  { to: 185, suffix: "+", label: "automated tests on every push" },
  { to: 0, suffix: "", label: "failed requests while killing pods" },
  { to: 14, suffix: " days", label: "a push can wait safely in the queue" },
  { to: 96, suffix: " MB", label: "hardened container image" },
];

export function Stats() {
  return (
    <section className="border-y border-black/[0.06] bg-black/[0.015]">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-px px-5 md:grid-cols-4">
        {STATS.map((s, i) => (
          <Reveal key={s.label} delay={i * 0.08} className="px-4 py-12 text-center">
            <div className="text-[clamp(2rem,4vw,3rem)] font-semibold tracking-tight">
              <CountUp to={s.to} suffix={s.suffix} className="l-gradient-text" />
            </div>
            <div className="mt-2 text-sm text-fg-muted">{s.label}</div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

export function FinalCta({ primaryHref, primaryLabel, demoHref }: {
  primaryHref: string;
  primaryLabel: string;
  demoHref: string | null;
}) {
  return (
    <section className="relative px-5 py-28 sm:py-36">
      <Reveal className="mx-auto max-w-4xl">
        <div className="l-glow-border rounded-3xl p-px">
          <div className="relative overflow-hidden rounded-3xl bg-white px-6 py-16 text-center sm:px-16">
            <div className="l-aurora opacity-60" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div className="relative">
              <LogoMark size={44} className="mx-auto shadow-[0_0_50px_-6px_var(--l-indigo)]" />
              <h2 className="mt-6 text-[clamp(2rem,5vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.035em]">
                Point it at a repo.
                <br />
                <span className="l-gradient-text">Watch the docs write themselves.</span>
              </h2>
              <p className="mx-auto mt-5 max-w-lg text-[15px] text-fg-muted">
                Two minutes from install to your first generated docs. Read-only access, cancel anytime.
              </p>
              <div className="mt-9 flex flex-wrap justify-center gap-3">
                <Magnetic>
                  <Button asChild variant="primary" className="h-11 rounded-xl px-5 text-[15px] shadow-[0_0_40px_-8px_var(--l-indigo)]">
                    <Link to={primaryHref}>
                      <GitHubIcon />
                      {primaryLabel}
                      <ArrowRight />
                    </Link>
                  </Button>
                </Magnetic>
                {demoHref && (
                  <Magnetic>
                    <Button asChild variant="secondary" className="h-11 rounded-xl border-black/10 bg-white px-5 text-[15px] shadow-sm hover:bg-[#f5f5f8]">
                      <Link to={demoHref}>
                        <Play />
                        Live demo
                      </Link>
                    </Button>
                  </Magnetic>
                )}
              </div>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

export function Footer({ version }: { version: string }) {
  return (
    <footer className="border-t border-black/[0.06]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-8 text-sm text-fg-subtle">
        <span className="flex items-center gap-2 font-semibold text-fg">
          <LogoMark size={20} /> Docify
        </span>
        <span>Living documentation for your code.</span>
        <nav className="ml-auto flex items-center gap-5" aria-label="Footer">
          <a href="https://github.com/docify-work/docify" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:text-fg">
            <GitHubIcon className="size-3.5" /> Source
          </a>
          <Link to="/privacy" className="hover:text-fg">Privacy</Link>
          <Link to="/login" className="hover:text-fg">Sign in</Link>
          <span className="font-mono text-xs">{version}</span>
        </nav>
      </div>
    </footer>
  );
}
