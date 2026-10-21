import { ArrowRight, ArrowUpRight, Play } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { LogoMark } from "@/components/Logo";
import { Button } from "@/components/ui";
import { CountUp, Magnetic, Reveal } from "./fx";
import { scrollToSection } from "./motion-utils";

const STATS = [
  { to: 185, suffix: "+", label: "automated tests on every push" },
  { to: 0, suffix: "", label: "failed requests while killing pods" },
  { to: 14, suffix: " days", label: "a push can wait safely in the queue" },
  { to: 96, suffix: " MB", label: "hardened container image" },
];

export function Stats() {
  return (
    <section className="border-t border-black/[0.06] bg-white">
      <div className="mx-auto grid max-w-6xl grid-cols-2 px-5 md:grid-cols-4">
        {STATS.map((s, i) => (
          <Reveal key={s.label} delay={i * 0.06} className="px-4 py-12 text-center">
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

const REPO = "https://github.com/docify-work/docify";

function SectionLink({ id, children }: { id: string; children: ReactNode }) {
  return (
    <a
      href={`#${id}`}
      onClick={(e: MouseEvent) => {
        e.preventDefault();
        scrollToSection(id);
      }}
      className="text-fg-muted transition-colors hover:text-fg"
    >
      {children}
    </a>
  );
}

/** Closing CTA band + real product footer (no build/env info: this is the public face). */
export function SiteFooter({ primaryHref, primaryLabel, demoHref }: {
  primaryHref: string;
  primaryLabel: string;
  demoHref: string | null;
}) {
  return (
    <footer className="relative overflow-hidden bg-white">
      <div className="l-mesh pointer-events-none absolute inset-x-0 top-0 h-[420px] opacity-70" aria-hidden="true" />

      {/* CTA band */}
      <div className="relative mx-auto max-w-6xl px-5 pb-16 pt-20 sm:pt-24">
        <Reveal className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="l-eyebrow">Get started</p>
            <h2 className="mt-3 text-[clamp(2rem,4.6vw,3.6rem)] font-semibold leading-[1.02]">
              Docs that never go stale.
              <br />
              <span className="l-gradient-text">Set up in two minutes.</span>
            </h2>
            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-fg-muted">
              Install the GitHub App, pick a repo and get an overview, setup guide and API reference — kept current on
              every push.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
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
                  Live demo
                </Link>
              </Button>
            )}
          </div>
        </Reveal>
      </div>

      {/* Link columns */}
      <div className="relative mx-auto max-w-6xl px-5">
        <div className="grid gap-10 border-t border-black/[0.06] py-12 sm:grid-cols-2 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link to="/" className="inline-flex items-center gap-2 text-[15px] font-semibold" aria-label="Docify home">
              <LogoMark size={24} /> Docify
            </Link>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-fg-muted">
              Living documentation for your code — generated, cited and kept in sync automatically.
            </p>
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Docify on GitHub"
              className="mt-5 inline-grid size-9 place-items-center rounded-lg border border-black/[0.08] text-fg-muted transition-colors hover:border-black/20 hover:text-fg"
            >
              <GitHubIcon className="size-4" />
            </a>
          </div>
          <FooterCol title="Product">
            <SectionLink id="product">Product tour</SectionLink>
            <SectionLink id="features">Features</SectionLink>
            <SectionLink id="architecture">Architecture</SectionLink>
            {demoHref && <Link to={demoHref} className="text-fg-muted hover:text-fg">Live demo</Link>}
          </FooterCol>
          <FooterCol title="Developers">
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-fg-muted hover:text-fg">
              Source code <ArrowUpRight className="size-3.5" />
            </a>
            <a href={`${REPO}/blob/main/docs/Docify_Master_Doc.md`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-fg-muted hover:text-fg">
              Architecture docs <ArrowUpRight className="size-3.5" />
            </a>
            <Link to="/privacy" className="text-fg-muted hover:text-fg">Security &amp; privacy</Link>
          </FooterCol>
          <FooterCol title="Account">
            <Link to="/signup" className="text-fg-muted hover:text-fg">Create account</Link>
            <Link to="/login" className="text-fg-muted hover:text-fg">Sign in</Link>
          </FooterCol>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-black/[0.06] py-6 text-xs text-fg-subtle">
          <span>© {new Date().getFullYear()} Docify. All rights reserved.</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-[var(--l-emerald)]" />
            All systems normal
          </span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-fg">{title}</h3>
      <div className="mt-4 flex flex-col gap-2.5 text-sm">{children}</div>
    </div>
  );
}
