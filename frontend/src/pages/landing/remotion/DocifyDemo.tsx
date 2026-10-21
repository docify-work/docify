/**
 * The hero film (Remotion). Every pixel is a pure function of the frame, so it loops perfectly.
 *
 *  variant "full"  (desktop, 1920×1080): headline + copy on the left, live product stage on the right,
 *                  chapter progress under the copy. Real HTML buttons are overlaid by Hero.tsx.
 *  variant "stage" (mobile, 1280×720):   only the stage, shown under the HTML headline.
 *
 * Performance: no CSS filters (blur/drop-shadow), backgrounds are radial gradients that only translate,
 * motion is transform/opacity only.
 */
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CHAPTERS, FILM, LAYOUT } from "./config";

const C = {
  bg: "#fbfbfd",
  card: "#ffffff",
  border: "rgba(15,15,30,0.09)",
  fg: "#0f0f14",
  muted: "#52525e",
  subtle: "#8a8a96",
  indigo: "#4f46e5",
  violet: "#7c3aed",
  cyan: "#0891b2",
  emerald: "#059669",
  red: "#dc2626",
  amber: "#d97706",
};
const font = '"Geist Variable", "Inter Variable", ui-sans-serif, system-ui, sans-serif';
const mono = 'ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace';
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const GRADIENT = "linear-gradient(100deg, #4f46e5 0%, #7c3aed 45%, #0891b2 100%)";

export type FilmProps = { variant: "full" | "stage" };

export function DocifyDemo({ variant }: FilmProps) {
  const frame = useCurrentFrame();
  // Scenes start after the intro in the full film; the stage-only film has no intro.
  const offset = variant === "full" ? FILM.intro : 0;
  const t = Math.max(0, frame - offset);
  const sceneIndex = Math.min(3, Math.floor(t / FILM.scene));
  const sceneFrame = t - sceneIndex * FILM.scene;

  if (variant === "stage") {
    return (
      <AbsoluteFill style={{ background: C.bg, fontFamily: font, color: C.fg, overflow: "hidden", textAlign: "left" }}>
        <Backdrop fade={false} />
        <div style={{ position: "absolute", left: 30, top: 36, width: 840, height: 660 }}>
          <Stage sceneIndex={sceneIndex} sceneFrame={sceneFrame} />
        </div>
      </AbsoluteFill>
    );
  }

  const stageIn = interpolate(frame, [FILM.intro - 20, FILM.intro + 10], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: font, color: C.fg, overflow: "hidden", textAlign: "left" }}>
      <Backdrop fade />
      <Copy />
      <ChapterBar sceneIndex={sceneIndex} sceneFrame={sceneFrame} started={frame >= FILM.intro} />
      <div
        style={{
          position: "absolute", left: 1060, top: 170, width: 780, height: 760,
          opacity: stageIn, transform: `translateX(${(1 - stageIn) * 60}px)`,
        }}
      >
        <Stage sceneIndex={sceneIndex} sceneFrame={sceneFrame} />
      </div>
    </AbsoluteFill>
  );
}

/* ---------------------------------------------------------------------------------- backdrop */

function Backdrop({ fade }: { fade: boolean }) {
  const frame = useCurrentFrame();
  const a = (frame / 300) * Math.PI * 2; // one slow orbit per 10 s (FILM.scene * 2 frames) → seamless loop
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", width: 1100, height: 1100, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(129,140,248,0.22), transparent 62%)",
        left: -260, top: -420, transform: `translate(${Math.cos(a) * 40}px, ${Math.sin(a) * 30}px)`,
      }} />
      <div style={{
        position: "absolute", width: 1100, height: 1100, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(216,180,254,0.26), transparent 62%)",
        right: -300, top: -300, transform: `translate(${Math.sin(a) * 40}px, ${Math.cos(a) * 30}px)`,
      }} />
      <div style={{
        position: "absolute", width: 1000, height: 1000, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(103,232,249,0.16), transparent 62%)",
        left: 700, bottom: -560,
      }} />
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(to right, rgba(15,15,30,0.045) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(15,15,30,0.045) 1px, transparent 1px)`,
        backgroundSize: "64px 64px",
        maskImage: "radial-gradient(ellipse 80% 75% at 50% 40%, #000 35%, transparent 100%)",
      }} />
      {/* fade into the page below */}
      {fade && <AbsoluteFill style={{ background: `linear-gradient(to bottom, transparent 84%, ${C.bg})` }} />}
    </AbsoluteFill>
  );
}

/* ---------------------------------------------------------------------------------- left copy */

function Copy() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pill = interpolate(frame, [0, 12], [0, 1], clamp);
  const lines = [["Your", "code", "changes."], ["Your", "docs", "keep", "up."]];
  const sub = interpolate(frame, [24, 40], [0, 1], clamp);
  const checks = interpolate(frame, [34, 50], [0, 1], clamp);
  let idx = 0;
  return (
    <>
      <div style={{ position: "absolute", left: LAYOUT.left, top: 210, width: 860 }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 12, padding: "6px 18px 6px 6px", borderRadius: 999,
          background: C.card, border: `1px solid ${C.border}`, fontSize: 20, color: C.muted,
          opacity: pill, transform: `translateY(${(1 - pill) * 12}px)`, boxShadow: "0 1px 2px rgba(15,15,30,0.05)",
        }}>
          <span style={{ background: C.indigo, color: "#fff", fontWeight: 600, fontSize: 17, padding: "4px 12px", borderRadius: 999 }}>New</span>
          Docs that update themselves on every push
        </div>

        <div style={{ marginTop: 34, fontSize: 100, fontWeight: 650, lineHeight: 1, letterSpacing: -4.6 }}>
          {lines.map((line, li) => (
            <div key={li} style={{ display: "flex", gap: 24 }}>
              {line.map((w) => {
                const p = spring({ frame: frame - 4 - idx++ * 3, fps, config: { damping: 16, stiffness: 120 } });
                const grad = w === "docs";
                return (
                  <span key={w + li} style={{ display: "inline-block", clipPath: "inset(-20% -15% 0 -15%)", paddingBottom: 14 }}>
                    <span style={{
                      display: "inline-block", transform: `translateY(${(1 - p) * 110}%)`, opacity: p,
                      ...(grad ? { background: GRADIENT, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" } : {}),
                    }}>{w}</span>
                  </span>
                );
              })}
            </div>
          ))}
        </div>

        <p style={{
          marginTop: 26, fontSize: 28, lineHeight: 1.5, color: C.muted, maxWidth: 800,
          opacity: sub, transform: `translateY(${(1 - sub) * 14}px)`,
        }}>
          Connect a GitHub repo. Docify writes the docs with AI, rewrites only what changed on every push, and answers
          questions with links to the exact lines.
        </p>
      </div>

      {/* the real, clickable buttons are HTML overlaid at LAYOUT.ctaTop (see Hero.tsx) */}

      <div style={{
        position: "absolute", left: LAYOUT.left, top: LAYOUT.ctaTop + LAYOUT.ctaHeight + 28, display: "flex", gap: 30,
        fontSize: 19, color: C.subtle, opacity: checks,
      }}>
        {["Free to try", "Read-only GitHub access", "Line-level citations"].map((c) => (
          <span key={c} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: C.emerald, fontWeight: 700 }}>✓</span>{c}
          </span>
        ))}
      </div>
    </>
  );
}

function ChapterBar({ sceneIndex, sceneFrame, started }: { sceneIndex: number; sceneFrame: number; started: boolean }) {
  const frame = useCurrentFrame();
  const show = interpolate(frame, [36, 54], [0, 1], clamp);
  return (
    <div style={{ position: "absolute", left: LAYOUT.left, top: LAYOUT.chaptersTop, display: "flex", gap: LAYOUT.chapterGap, opacity: show }}>
      {CHAPTERS.map((label, i) => {
        const fill = !started ? 0 : i < sceneIndex ? 1 : i === sceneIndex ? sceneFrame / FILM.scene : 0;
        const on = started && i === sceneIndex;
        return (
          <div key={label} style={{ width: LAYOUT.chapterWidth, height: LAYOUT.chapterHeight }}>
            <div style={{ height: 4, borderRadius: 4, background: "rgba(15,15,30,0.08)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: "100%", background: GRADIENT, transformOrigin: "left", transform: `scaleX(${fill})` }} />
            </div>
            <div style={{ marginTop: 14, fontSize: 19, color: on ? C.fg : C.subtle, fontWeight: on ? 600 : 400 }}>
              <span style={{ fontFamily: mono, fontSize: 15, color: on ? C.indigo : C.subtle, marginRight: 8 }}>0{i + 1}</span>
              {label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------------------------- stage */

const CAPTIONS = [
  "You push a commit",
  "Docify reacts — even while servers sleep",
  "Only the affected doc is rewritten",
  "Ask anything — answers cite the lines",
];

function Stage({ sceneIndex, sceneFrame }: { sceneIndex: number; sceneFrame: number }) {
  const fade = interpolate(sceneFrame, [0, 14, FILM.scene - 14, FILM.scene], [0, 1, 1, 0], clamp);
  const lift = interpolate(sceneFrame, [0, 18], [24, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const Scene = [PushScene, PipelineScene, DocScene, ChatScene][sceneIndex]!;
  return (
    <div style={{ position: "relative", width: "100%", height: "100%", opacity: fade, transform: `translateY(${lift}px)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 21, color: C.muted }}>
        <span style={{ fontFamily: mono, fontSize: 16, color: C.cyan, background: C.card, border: `1px solid ${C.border}`, borderRadius: 999, padding: "3px 11px" }}>
          0{sceneIndex + 1}
        </span>
        {CAPTIONS[sceneIndex]}
      </div>
      <div style={{ position: "absolute", inset: "64px 0 0 0", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <Scene f={sceneFrame} />
      </div>
    </div>
  );
}

function card(extra: CSSProperties = {}): CSSProperties {
  return {
    background: C.card, border: `1px solid ${C.border}`, borderRadius: 22,
    boxShadow: "0 1px 2px rgba(15,15,30,0.04), 0 30px 60px -30px rgba(30,27,75,0.30)", ...extra,
  };
}

function usePop(f: number, delay: number) {
  const { fps } = useVideoConfig();
  return spring({ frame: f - delay, fps, config: { damping: 15, stiffness: 140 } });
}

function Chip({ children, s = 1 }: { children: ReactNode; s?: number }) {
  return (
    <span style={{
      fontFamily: mono, fontSize: 16, padding: "4px 11px", borderRadius: 8, border: "1px solid rgba(79,70,229,0.3)",
      background: "rgba(79,70,229,0.06)", color: "#4338ca", opacity: s, transform: `translateY(${(1 - s) * 8}px)`, display: "inline-block",
    }}>{children}</span>
  );
}

/* 1 · push ---------------------------------------------------------------------------- */

const DIFF = [
  { s: " ", t: '@router.post("/auth/login")' },
  { s: " ", t: "async def login(body: LoginIn):" },
  { s: "+", t: '    await limiter.hit(f"login:{ip}", limit=5)' },
  { s: " ", t: "    user = await users.by_email(body.email)" },
  { s: "-", t: "    if not verify(body.password, user.hash):" },
  { s: "+", t: "    if not await averify(body.password, user.hash):" },
];

function PushScene({ f }: { f: number }) {
  const p = usePop(f, 4);
  return (
    <div style={card({ padding: 30, transform: `translateY(${(1 - p) * 40}px) scale(${0.96 + p * 0.04})`, opacity: p })}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 19, color: C.muted }}>
        <div style={{ width: 34, height: 34, borderRadius: 999, background: GRADIENT }} />
        <span style={{ color: C.fg, fontWeight: 600 }}>ganesh</span> pushed to <span style={{ fontFamily: mono, color: C.cyan }}>main</span>
        <span style={{ marginLeft: "auto", fontFamily: mono, fontSize: 16, color: C.subtle }}>4f2c9e1</span>
      </div>
      <div style={{ marginTop: 14, fontSize: 25, fontWeight: 600, letterSpacing: -0.4 }}>feat(auth): rate-limit login + async password check</div>
      <div style={{ marginTop: 20, borderRadius: 14, border: `1px solid ${C.border}`, background: "#f7f7fa", padding: "12px 0" }}>
        {DIFF.map((d, i) => {
          const show = interpolate(f, [18 + i * 7, 28 + i * 7], [0, 1], clamp);
          const bg = d.s === "+" ? "rgba(5,150,105,0.08)" : d.s === "-" ? "rgba(220,38,38,0.07)" : "transparent";
          const col = d.s === "+" ? C.emerald : d.s === "-" ? C.red : C.muted;
          return (
            <div key={i} style={{ display: "flex", gap: 14, padding: "3px 18px", fontFamily: mono, fontSize: 18, background: bg, opacity: show, transform: `translateX(${(1 - show) * -16}px)` }}>
              <span style={{ width: 12, color: col }}>{d.s}</span>
              <span style={{ color: col, whiteSpace: "pre" }}>{d.t}</span>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 10, fontSize: 17, color: C.muted, opacity: interpolate(f, [70, 84], [0, 1], clamp) }}>
        <span style={{ width: 10, height: 10, borderRadius: 999, background: C.emerald }} />
        webhook delivered to Docify · 38 ms
      </div>
    </div>
  );
}

/* 2 · pipeline ------------------------------------------------------------------------ */

const NODES = [
  { label: "GitHub", sub: "webhook", color: C.fg },
  { label: "Lambda", sub: "verify", color: C.amber },
  { label: "SQS", sub: "queue", color: C.violet },
  { label: "Worker", sub: "diff + index", color: C.cyan },
  { label: "Claude", sub: "rewrite", color: C.indigo },
];

function PipelineScene({ f }: { f: number }) {
  const W = 780;
  const PAD = 66; // end nodes sit well inside the stage
  const gap = (W - 2 * PAD) / (NODES.length - 1);
  const travel = interpolate(f, [16, 110], [0, NODES.length - 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const note = interpolate(f, [92, 112], [0, 1], clamp);
  return (
    <div style={{ position: "relative", height: 400 }}>
      <svg width={W} height={260} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <defs>
          <linearGradient id="pipe" x1="0" x2="1">
            <stop offset="0" stopColor={C.indigo} />
            <stop offset="1" stopColor={C.cyan} />
          </linearGradient>
        </defs>
        <line x1={PAD} y1={126} x2={W - PAD} y2={126} stroke="rgba(15,15,30,0.12)" strokeWidth={3} strokeDasharray="8 12" strokeDashoffset={-f * 2} />
        <line x1={PAD} y1={126} x2={PAD + travel * gap} y2={126} stroke="url(#pipe)" strokeWidth={4} />
        <circle cx={PAD + travel * gap} cy={126} r={18} fill={C.cyan} opacity={0.16} />
        <circle cx={PAD + travel * gap} cy={126} r={9} fill={C.cyan} />
      </svg>
      {NODES.map((n, i) => {
        const lit = interpolate(travel, [i - 0.3, i], [0, 1], clamp);
        return (
          <div key={n.label} style={{ position: "absolute", left: PAD + i * gap - 64, top: 64, width: 128, textAlign: "center" }}>
            <div style={card({
              width: 120, height: 120, margin: "0 auto", display: "grid", placeItems: "center", borderRadius: 30,
              borderColor: lit > 0.5 ? n.color : C.border, transform: `scale(${0.9 + lit * 0.1})`,
              boxShadow: lit > 0.5 ? `0 0 0 6px ${n.color}14, 0 24px 40px -24px ${n.color}` : undefined,
            })}>
              <span style={{ fontSize: 22, fontWeight: 700, color: lit > 0.5 ? n.color : C.muted }}>{n.label}</span>
            </div>
            <div style={{ marginTop: 14, fontSize: 17, color: C.subtle, opacity: 0.45 + lit * 0.55 }}>{n.sub}</div>
          </div>
        );
      })}
      <div style={{ position: "absolute", top: 290, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 12, opacity: note, transform: `translateY(${(1 - note) * 10}px)` }}>
        {["queued up to 14 days", "coalesced", "retried", "never lost"].map((t) => (
          <span key={t} style={{ fontSize: 17, padding: "6px 14px", borderRadius: 999, border: `1px solid ${C.border}`, background: C.card, color: C.muted }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

/* 3 · doc rewrite --------------------------------------------------------------------- */

function DocScene({ f }: { f: number }) {
  const p = usePop(f, 4);
  const oldOut = interpolate(f, [30, 46], [1, 0], clamp);
  const newText = "Login is rate-limited to 5 attempts per minute, and passwords are checked off the event loop.";
  const typed = Math.floor(interpolate(f, [46, 104], [0, newText.length], clamp));
  const badge = usePop(f, 108);
  return (
    <div style={card({ padding: 34, opacity: p, transform: `translateY(${(1 - p) * 30}px)` })}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.8 }}>API reference</span>
        <span style={{ marginLeft: "auto", fontSize: 16, padding: "6px 14px", borderRadius: 999, background: "rgba(79,70,229,0.10)", color: "#4338ca", transform: `scale(${badge})`, opacity: badge }}>
          v2 published · just now
        </span>
      </div>
      <div style={{ marginTop: 20, fontSize: 22, fontWeight: 600, fontFamily: mono }}>POST /auth/login</div>
      <p style={{ marginTop: 10, fontSize: 21, lineHeight: 1.55, color: C.muted }}>Signs the user in and sets a session cookie.</p>
      <div style={{ position: "relative", marginTop: 4, minHeight: 104 }}>
        <p style={{ position: "absolute", fontSize: 21, lineHeight: 1.55, color: C.red, opacity: oldOut, textDecoration: "line-through" }}>
          Passwords are verified synchronously.
        </p>
        <p style={{ fontSize: 21, lineHeight: 1.55, color: C.fg, background: typed > 0 ? "rgba(5,150,105,0.08)" : "transparent", borderRadius: 8, padding: "2px 8px" }}>
          {newText.slice(0, typed)}
          {typed > 0 && typed < newText.length && <span style={{ color: C.cyan }}>▍</span>}
          {typed >= newText.length && <span style={{ marginLeft: 10 }}><Chip>auth.py:14-19</Chip></span>}
        </p>
      </div>
      <div style={{ marginTop: 20, display: "flex", gap: 10, fontSize: 16, color: C.subtle }}>
        {["Overview — unchanged", "Setup guide — unchanged", "Changelog +1"].map((t, i) => (
          <span key={t} style={{ padding: "6px 12px", borderRadius: 999, border: `1px solid ${C.border}`, opacity: interpolate(f, [80 + i * 8, 92 + i * 8], [0, 1], clamp) }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

/* 4 · chat ---------------------------------------------------------------------------- */

function ChatScene({ f }: { f: number }) {
  const q = "How does login rate limiting work?";
  const qTyped = Math.floor(interpolate(f, [6, 34], [0, q.length], clamp));
  const a = "Each attempt hits a sliding-window limiter keyed by IP + email: 5 per minute, 20 per hour per IP [1]. Over the limit the API answers 429 with Retry-After [2].";
  const aTyped = Math.floor(interpolate(f, [44, 112], [0, a.length], clamp));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ alignSelf: "flex-end", ...card({ padding: "15px 22px", borderRadius: 18, background: "#f1f0ff", borderColor: "rgba(79,70,229,0.25)" }), fontSize: 23 }}>
        {q.slice(0, qTyped)}
        {qTyped < q.length && <span style={{ color: C.cyan }}>▍</span>}
      </div>
      <div style={{ display: "flex", gap: 16, opacity: interpolate(f, [36, 44], [0, 1], clamp) }}>
        <div style={{ width: 46, height: 46, flexShrink: 0, borderRadius: 13, display: "grid", placeItems: "center", background: GRADIENT, color: "#fff", fontWeight: 800, fontSize: 22 }}>D</div>
        <div style={card({ padding: "18px 24px", fontSize: 22, lineHeight: 1.55, color: C.fg })}>
          {a.slice(0, aTyped)}
          {aTyped < a.length && <span style={{ color: C.cyan }}>▍</span>}
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            {["routers/auth.py:41-47", "cache.py:31-55"].map((c, i) => (
              <Chip key={c} s={interpolate(f, [114 + i * 6, 122 + i * 6], [0, 1], clamp)}>[{i + 1}] {c}</Chip>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
