import { ArrowRight, Check, FileText, GitCommitHorizontal, Play, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { GitHubIcon } from "@/components/BrandIcons";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { Magnetic, SplitWords } from "./fx";
import { EASE, useSpotlight } from "./motion-utils";

export function Hero({ primaryHref, primaryLabel, demoHref }: {
  primaryHref: string;
  primaryLabel: string;
  demoHref: string | null;
}) {
  const spot = useSpotlight<HTMLElement>();
  const windowRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: windowRef, offset: ["start end", "center center"] });
  const rotateX = useTransform(scrollYProgress, [0, 1], [24, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [0.9, 1]);
  const y = useTransform(scrollYProgress, [0, 1], [60, 0]);

  return (
    <section ref={spot} className="l-spotlight relative isolate overflow-hidden pt-32 sm:pt-40">
      <div className="l-aurora" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="l-grid absolute inset-0 -z-10" aria-hidden="true" />
      <div className="l-noise" aria-hidden="true" />

      <div className="relative mx-auto max-w-6xl px-5 text-center">
        <motion.a
          href="#demo"
          initial={{ opacity: 0, y: 12, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.1 }}
          className="group relative mx-auto inline-flex items-center gap-2 overflow-hidden rounded-full border border-black/10 bg-black/[0.04] py-1 pl-1 pr-3 text-xs text-fg-muted backdrop-blur"
        >
          <span className="rounded-full bg-[var(--l-indigo)] px-2 py-0.5 text-[11px] font-semibold text-white">New</span>
          Docs that update themselves on every push
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          <span className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/80 to-transparent [animation:l-sweep_3.5s_ease-in-out_infinite]" />
        </motion.a>

        <h1 className="mx-auto mt-7 max-w-4xl text-[clamp(2.6rem,7vw,5.6rem)] font-semibold leading-[0.98] tracking-[-0.04em]">
          <SplitWords text="Your code changes." delay={0.2} />
          <br />
          <SplitWords text="Your docs keep up." delay={0.45} gradientWords={["docs"]} />
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 0.85 }}
          className="mx-auto mt-6 max-w-2xl text-[clamp(1rem,1.6vw,1.2rem)] leading-relaxed text-fg-muted"
        >
          Connect a GitHub repo. Docify reads the code, writes the docs with AI, rewrites only what changed on every
          push — and answers questions with links to the exact lines.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 1 }}
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <Magnetic>
            <Button asChild variant="primary" className="h-11 rounded-xl px-5 text-[15px] shadow-[0_0_40px_-8px_var(--l-indigo)]">
              <Link to={primaryHref}>
                <GitHubIcon />
                {primaryLabel}
              </Link>
            </Button>
          </Magnetic>
          {demoHref && (
            <Magnetic>
              <Button asChild variant="secondary" className="h-11 rounded-xl border-black/10 bg-white/80 px-5 text-[15px] shadow-sm backdrop-blur hover:bg-white">
                <Link to={demoHref}>
                  <Play />
                  Explore the live demo
                </Link>
              </Button>
            </Magnetic>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.3, duration: 1 }}
          className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-xs text-fg-subtle"
        >
          {["Free to try", "Read-only GitHub access", "Line-level citations"].map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <Check className="size-3.5 text-[var(--l-emerald)]" />
              {t}
            </span>
          ))}
        </motion.div>
      </div>

      <div className="relative mx-auto mt-16 max-w-6xl px-5 pb-24 [perspective:1600px] sm:mt-20">
        <motion.div ref={windowRef} style={{ rotateX, scale, y }} className="origin-top">
          <HeroWindow />
        </motion.div>
        <div
          className="pointer-events-none absolute inset-x-10 -bottom-4 h-40 rounded-full bg-[var(--l-indigo)] opacity-30 blur-[90px]"
          aria-hidden="true"
        />
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------------- live product window */

const CODE = [
  { t: '@router.post("/auth/login")', k: "dec" },
  { t: "async def login(body: LoginIn, db: DB):", k: "def" },
  { t: "    user = await users.by_email(db, body.email)", k: "" },
  { t: "    if not await verify(body.password, user.hash):", k: "" },
  { t: '        raise Problem(401, "Wrong email or password")', k: "" },
  { t: "    token = await create_session(db, user)", k: "" },
  { t: "    return set_cookie(token)", k: "" },
];

const DOC = [
  { kind: "h1", text: "Authentication" },
  { kind: "p", text: "Users sign in with email and password; a server-side session cookie is issued.", cite: "auth.py:12-18" },
  { kind: "p", text: "Passwords are verified with Argon2 before any session exists.", cite: "auth.py:15" },
  { kind: "h2", text: "Endpoints" },
  { kind: "code", text: "POST /auth/login → 200 · Set-Cookie: docify_session" },
] as const;

const CYCLE = 12;

function HeroWindow() {
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(reduce ? CYCLE - 1 : 0);
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setTick((t) => (t + 1) % CYCLE), 750);
    return () => clearInterval(id);
  }, [reduce]);

  const reading = tick >= 1 && tick <= 7 ? tick - 1 : -1;
  const docShown = Math.max(0, tick - 5);
  const pushed = tick >= 1;
  const updated = tick >= 10;

  return (
    <div className="l-glow-border rounded-2xl p-px shadow-[0_40px_100px_-40px_rgb(79_70_229/0.35)]">
      <div className="overflow-hidden rounded-2xl bg-white">
        {/* window chrome */}
        <div className="flex h-10 items-center gap-2 border-b border-black/[0.06] px-4">
          <span className="size-2.5 rounded-full bg-[#ff5f57]" />
          <span className="size-2.5 rounded-full bg-[#febc2e]" />
          <span className="size-2.5 rounded-full bg-[#28c840]" />
          <div className="mx-auto flex items-center gap-2 rounded-md bg-black/[0.04] px-3 py-1 font-mono text-[11px] text-fg-subtle">
            <span className="size-1.5 rounded-full bg-[var(--l-emerald)]" />
            docify.work/w/acme/docs/authentication
          </div>
        </div>

        <div className="grid gap-px bg-black/[0.04] text-left md:grid-cols-[1fr_auto_1.1fr]">
          {/* code */}
          <div className="bg-white p-5">
            <div className="mb-3 flex items-center gap-2 text-xs text-fg-subtle">
              <GitHubIcon className="size-3.5" /> acme/api · <span className="font-mono">src/auth.py</span>
              <AnimatePresence>
                {pushed && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.8, x: -6 }}
                    animate={{ opacity: 1, scale: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    className="ml-auto inline-flex items-center gap-1 rounded-full bg-[var(--l-emerald)]/10 px-2 py-0.5 font-mono text-[10px] text-[var(--l-emerald)]"
                  >
                    <GitCommitHorizontal className="size-3" /> pushed 4f2c9e1
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
            <pre className="overflow-x-auto font-mono text-[12.5px] leading-6">
              {CODE.map((line, i) => (
                <div key={i} className="relative flex">
                  <span className="w-8 shrink-0 select-none pr-3 text-right text-fg-subtle/60">{12 + i}</span>
                  <motion.span
                    className="absolute inset-y-0 left-6 right-0 rounded bg-[var(--l-indigo)]/15"
                    initial={false}
                    animate={{ opacity: reading === i ? 1 : 0 }}
                    transition={{ duration: 0.25 }}
                  />
                  <span
                    className={cn(
                      "relative whitespace-pre",
                      line.k === "dec" && "text-[var(--l-amber)]",
                      line.k === "def" && "text-[#7c3aed]",
                      !line.k && "text-fg-muted",
                    )}
                  >
                    {line.t}
                  </span>
                </div>
              ))}
            </pre>
          </div>

          {/* beam */}
          <div className="relative hidden w-20 items-center justify-center bg-white md:flex">
            <svg viewBox="0 0 80 200" className="h-48 w-20" aria-hidden="true">
              <defs>
                <linearGradient id="beam" x1="0" x2="1">
                  <stop offset="0" stopColor="var(--l-indigo)" stopOpacity="0" />
                  <stop offset="0.5" stopColor="var(--l-cyan)" />
                  <stop offset="1" stopColor="var(--l-violet)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0 100 C 30 100, 50 100, 80 100" stroke="url(#beam)" strokeWidth="2" fill="none" className="l-flow" />
              {[0, 1, 2].map((i) => (
                <motion.circle
                  key={i}
                  r="3"
                  cy="100"
                  fill="var(--l-cyan)"
                  initial={{ cx: 0, opacity: 0 }}
                  animate={reading >= 0 ? { cx: [0, 80], opacity: [0, 1, 0] } : { opacity: 0 }}
                  transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.35, ease: "easeInOut" }}
                />
              ))}
            </svg>
            <motion.div
              animate={{ rotate: reading >= 0 ? 360 : 0 }}
              transition={{ duration: 3, repeat: reading >= 0 ? Infinity : 0, ease: "linear" }}
              className="absolute grid size-9 place-items-center rounded-xl border border-black/10 bg-white shadow-[0_0_30px_-4px_var(--l-indigo)]"
            >
              <Sparkles className="size-4 text-[var(--accent-text)]" />
            </motion.div>
          </div>

          {/* generated doc */}
          <div className="relative bg-white p-5">
            <div className="mb-3 flex items-center gap-2 text-xs text-fg-subtle">
              <FileText className="size-3.5" /> Generated docs
              <AnimatePresence>
                {updated && (
                  <motion.span
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="ml-auto inline-flex items-center gap-1 rounded-full bg-[var(--l-indigo)]/15 px-2 py-0.5 text-[10px] font-medium text-[var(--accent-text)]"
                  >
                    <Check className="size-3" /> Updated just now
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
            <div className="min-h-[196px] space-y-2.5">
              {DOC.map((d, i) => (
                <motion.div
                  key={d.text}
                  initial={false}
                  animate={docShown > i ? { opacity: 1, y: 0, filter: "blur(0px)" } : { opacity: 0, y: 8, filter: "blur(6px)" }}
                  transition={{ duration: 0.5, ease: EASE }}
                >
                  {d.kind === "h1" && <div className="text-lg font-semibold tracking-tight">{d.text}</div>}
                  {d.kind === "h2" && <div className="pt-1 text-sm font-semibold">{d.text}</div>}
                  {d.kind === "p" && (
                    <p className="text-[13px] leading-relaxed text-fg-muted">
                      {d.text}{" "}
                      <span className="inline-flex items-center rounded-md border border-[var(--l-indigo)]/30 bg-[var(--l-indigo)]/10 px-1.5 font-mono text-[10.5px] text-[var(--accent-text)]">
                        {d.cite}
                      </span>
                    </p>
                  )}
                  {d.kind === "code" && (
                    <div className="rounded-lg border border-black/[0.06] bg-[#f7f7fa] px-3 py-2 font-mono text-[11.5px] text-[var(--l-emerald)]">
                      {d.text}
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
