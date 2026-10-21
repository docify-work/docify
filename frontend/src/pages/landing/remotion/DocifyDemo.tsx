/**
 * The hero stage film (Remotion): push → pipeline → doc rewrite → chat. Every pixel is a pure function
 * of the frame, so it loops perfectly. No CSS filters; motion is transform/opacity only.
 */
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FILM } from "./config";

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

/** The live product stage: 4 scenes, transparent background so it sits directly on the hero. */
export function DocifyDemo() {
  const frame = useCurrentFrame();
  const sceneIndex = Math.min(3, Math.floor(frame / FILM.scene));
  const sceneFrame = frame - sceneIndex * FILM.scene;
  return (
    <AbsoluteFill style={{ fontFamily: font, color: C.fg, textAlign: "left" }}>
      <div style={{ position: "absolute", left: 20, top: 16, width: 800, height: 648 }}>
        <Stage sceneIndex={sceneIndex} sceneFrame={sceneFrame} />
      </div>
    </AbsoluteFill>
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
  const W = 800;
  const PAD = 68; // end nodes sit well inside the stage
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
