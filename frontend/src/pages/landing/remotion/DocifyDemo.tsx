/**
 * Remotion composition: a 16-second product film rendered live in the browser by @remotion/player.
 * Four scenes: push → pipeline → doc rewrite → chat with citations.
 * Everything is a pure function of the current frame (that's the Remotion model), so it loops perfectly.
 */
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DEMO, DEMO_DURATION } from "./config";


const C = {
  bg: "#f8f8fb",
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

export function DocifyDemo() {
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: font, color: C.fg, overflow: "hidden" }}>
      <Backdrop />
      <Sequence durationInFrames={DEMO.scene}>
        <Scene step="01" title="You push a commit"><PushScene /></Scene>
      </Sequence>
      <Sequence from={DEMO.scene} durationInFrames={DEMO.scene}>
        <Scene step="02" title="Docify reacts — even while servers sleep"><PipelineScene /></Scene>
      </Sequence>
      <Sequence from={DEMO.scene * 2} durationInFrames={DEMO.scene}>
        <Scene step="03" title="Only the affected doc is rewritten"><DocScene /></Scene>
      </Sequence>
      <Sequence from={DEMO.scene * 3} durationInFrames={DEMO.scene}>
        <Scene step="04" title="Ask anything — answers cite the lines"><ChatScene /></Scene>
      </Sequence>
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------------------------ shared */

function Backdrop() {
  const frame = useCurrentFrame();
  const a = (frame / DEMO_DURATION) * Math.PI * 2;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute", width: 900, height: 900, borderRadius: "50%", opacity: 0.5,
          background: `radial-gradient(circle, rgba(79,70,229,0.18), transparent 65%)`,
          left: 100 + Math.cos(a) * 120, top: -300 + Math.sin(a) * 80,
        }}
      />
      <div
        style={{
          position: "absolute", width: 700, height: 700, borderRadius: "50%", opacity: 0.45,
          background: `radial-gradient(circle, rgba(124,58,237,0.16), transparent 65%)`,
          right: -100 + Math.sin(a) * 100, bottom: -300 + Math.cos(a) * 60,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(to right, rgba(15,15,30,0.05) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(15,15,30,0.05) 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(ellipse 70% 70% at 50% 50%, #000 30%, transparent 100%)",
        }}
      />
    </AbsoluteFill>
  );
}

function Scene({ step, title, children }: { step: string; title: string; children: ReactNode }) {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 12, DEMO.scene - 12, DEMO.scene], [0, 1, 1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [0, 18], [20, 0], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ opacity, padding: "56px 72px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, transform: `translateY(${titleY}px)` }}>
        <span style={{
          fontFamily: mono, fontSize: 18, color: C.cyan, border: `1px solid ${C.border}`, borderRadius: 999,
          padding: "4px 12px", background: "#ffffff",
        }}>{step}</span>
        <span style={{ fontSize: 34, fontWeight: 600, letterSpacing: -0.8 }}>{title}</span>
      </div>
      <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", paddingBottom: 40 }}>{children}</div>
    </AbsoluteFill>
  );
}

function card(extra: CSSProperties = {}): CSSProperties {
  return {
    background: "#ffffff",
    border: `1px solid ${C.border}`, borderRadius: 20, boxShadow: "0 1px 2px rgba(15,15,30,0.04), 0 30px 60px -30px rgba(30,27,75,0.30)", ...extra,
  };
}

function usePop(delay: number) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 140 } });
}

/* ------------------------------------------------------------------------------------ 1. push */

const DIFF = [
  { s: " ", t: '@router.post("/auth/login")' },
  { s: " ", t: "async def login(body: LoginIn):" },
  { s: "+", t: '    await limiter.hit(f"login:{ip}", limit=5)' },
  { s: " ", t: "    user = await users.by_email(body.email)" },
  { s: "-", t: "    if not verify(body.password, user.hash):" },
  { s: "+", t: "    if not await averify(body.password, user.hash):" },
];

function PushScene() {
  const frame = useCurrentFrame();
  const p = usePop(6);
  return (
    <div style={{ display: "flex", justifyContent: "center" }}>
      <div style={card({ width: 900, padding: 28, transform: `translateY(${(1 - p) * 60}px) scale(${0.94 + p * 0.06})`, opacity: p })}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 18, color: C.muted }}>
          <div style={{ width: 34, height: 34, borderRadius: 999, background: `linear-gradient(135deg, ${C.indigo}, ${C.violet})` }} />
          <span style={{ color: C.fg, fontWeight: 600 }}>ganesh</span> pushed to <span style={{ fontFamily: mono, color: C.cyan }}>main</span>
          <span style={{ marginLeft: "auto", fontFamily: mono, fontSize: 15, color: C.subtle }}>4f2c9e1</span>
        </div>
        <div style={{ marginTop: 14, fontSize: 24, fontWeight: 600 }}>feat(auth): rate-limit login + async password check</div>
        <div style={{ marginTop: 20, borderRadius: 14, border: `1px solid ${C.border}`, background: "#f7f7fa", padding: "14px 0" }}>
          {DIFF.map((d, i) => {
            const show = interpolate(frame, [20 + i * 8, 30 + i * 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const bg = d.s === "+" ? "rgba(5,150,105,0.08)" : d.s === "-" ? "rgba(220,38,38,0.07)" : "transparent";
            const col = d.s === "+" ? C.emerald : d.s === "-" ? C.red : C.muted;
            return (
              <div key={i} style={{ display: "flex", gap: 16, padding: "3px 20px", fontFamily: mono, fontSize: 19, background: bg, opacity: show, transform: `translateX(${(1 - show) * -20}px)` }}>
                <span style={{ width: 14, color: col }}>{d.s}</span>
                <span style={{ color: col, whiteSpace: "pre" }}>{d.t}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------------------ 2. pipeline */

const NODES = [
  { label: "GitHub", sub: "push webhook", color: C.fg },
  { label: "Lambda", sub: "verify signature", color: C.amber },
  { label: "SQS", sub: "durable queue", color: C.violet },
  { label: "Worker", sub: "diff + index", color: C.cyan },
  { label: "Claude", sub: "rewrite docs", color: C.indigo },
];

function PipelineScene() {
  const frame = useCurrentFrame();
  const W = 1136; // inner width (1280 - 2 × 72 scene padding)
  const PAD = 110; // keep the end nodes well inside the frame
  const gap = (W - 2 * PAD) / (NODES.length - 1);
  const travel = interpolate(frame, [18, 100], [0, NODES.length - 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic),
  });
  return (
    <div style={{ position: "relative", height: 420 }}>
      <svg width={W} height={420} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <line x1={PAD} y1={160} x2={W - PAD} y2={160} stroke="rgba(15,15,30,0.12)" strokeWidth={3} strokeDasharray="8 12" strokeDashoffset={-frame * 2} />
        <line x1={PAD} y1={160} x2={PAD + travel * gap} y2={160} stroke="url(#pipe)" strokeWidth={4} />
        <defs>
          <linearGradient id="pipe" x1="0" x2="1">
            <stop offset="0" stopColor={C.indigo} />
            <stop offset="1" stopColor={C.cyan} />
          </linearGradient>
        </defs>
        <circle cx={PAD + travel * gap} cy={160} r={10} fill={C.cyan}  />
      </svg>
      {NODES.map((n, i) => {
        const lit = interpolate(travel, [i - 0.3, i], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={n.label} style={{ position: "absolute", left: PAD + i * gap - 80, top: 90, width: 160, textAlign: "center" }}>
            <div style={card({
              width: 140, height: 140, margin: "0 auto", display: "grid", placeItems: "center", borderRadius: 32,
              borderColor: lit > 0.5 ? n.color : C.border, boxShadow: lit > 0.5 ? `0 0 60px -10px ${n.color}` : undefined,
              transform: `scale(${0.9 + lit * 0.1})`,
            })}>
              <span style={{ fontSize: 26, fontWeight: 700, color: lit > 0.5 ? n.color : C.muted }}>{n.label}</span>
            </div>
            <div style={{ marginTop: 18, fontSize: 18, color: C.subtle, opacity: 0.4 + lit * 0.6 }}>{n.sub}</div>
          </div>
        );
      })}
      <div style={{ position: "absolute", bottom: 10, left: 0, right: 0, textAlign: "center", fontSize: 20, color: C.muted, opacity: interpolate(frame, [70, 90], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        Queued for up to 14 days · coalesced · retried · fenced — no push is ever lost
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------------------ 3. doc rewrite */

function DocScene() {
  const frame = useCurrentFrame();
  const p = usePop(4);
  const oldOut = interpolate(frame, [30, 45], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const newText = "Login is rate-limited to 5 attempts per minute, and passwords are checked off the event loop.";
  const typed = Math.floor(interpolate(frame, [45, 95], [0, newText.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const badge = usePop(98);
  return (
    <div style={{ display: "flex", justifyContent: "center" }}>
      <div style={card({ width: 960, padding: 36, opacity: p, transform: `translateY(${(1 - p) * 40}px)` })}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 34, fontWeight: 700, letterSpacing: -0.6 }}>API reference</span>
          <span style={{
            marginLeft: "auto", fontSize: 16, padding: "6px 14px", borderRadius: 999, background: "rgba(79,70,229,0.10)",
            color: "#4338ca", transform: `scale(${badge})`, opacity: badge,
          }}>v2 published · just now</span>
        </div>
        <div style={{ marginTop: 22, fontSize: 22, fontWeight: 600 }}>POST /auth/login</div>
        <p style={{ marginTop: 10, fontSize: 21, lineHeight: 1.6, color: C.muted }}>Signs the user in and sets a session cookie.</p>
        <div style={{ position: "relative", marginTop: 6, minHeight: 74 }}>
          <p style={{ position: "absolute", fontSize: 21, lineHeight: 1.6, color: C.red, opacity: oldOut, textDecoration: "line-through" }}>
            Passwords are verified synchronously.
          </p>
          <p style={{ fontSize: 21, lineHeight: 1.6, color: C.fg, background: typed > 0 ? "rgba(5,150,105,0.08)" : "transparent", borderRadius: 8, padding: "0 6px" }}>
            {newText.slice(0, typed)}
            {typed > 0 && typed < newText.length && <span style={{ color: C.cyan }}>▍</span>}
            {typed >= newText.length && (
              <span style={{ marginLeft: 10, fontFamily: mono, fontSize: 15, padding: "2px 8px", borderRadius: 6, border: "1px solid rgba(79,70,229,0.3)", color: "#4338ca" }}>
                auth.py:14-19
              </span>
            )}
          </p>
        </div>
        <div style={{ marginTop: 26, display: "flex", gap: 12, fontSize: 16, color: C.subtle }}>
          {["Overview — unchanged", "Setup guide — unchanged", "Changelog +1 entry"].map((t, i) => (
            <span key={t} style={{ padding: "6px 12px", borderRadius: 999, border: `1px solid ${C.border}`, opacity: interpolate(frame, [70 + i * 8, 82 + i * 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------------------ 4. chat */

function ChatScene() {
  const frame = useCurrentFrame();
  const q = "How does login rate limiting work?";
  const qTyped = Math.floor(interpolate(frame, [6, 32], [0, q.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const a = "Each login attempt hits a sliding-window limiter keyed by IP + email: 5 per minute, 20 per hour per IP [1]. Over the limit, the API answers 429 with Retry-After [2].";
  const aTyped = Math.floor(interpolate(frame, [40, 100], [0, a.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const chips = ["routers/auth.py:41-47", "cache.py:31-55"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22, maxWidth: 1000, margin: "0 auto" }}>
      <div style={{ alignSelf: "flex-end", ...card({ padding: "16px 22px", borderRadius: 18, background: "rgba(79,70,229,0.08)", borderColor: "rgba(79,70,229,0.25)" }), fontSize: 24 }}>
        {q.slice(0, qTyped)}
        {qTyped < q.length && <span style={{ color: C.cyan }}>▍</span>}
      </div>
      <div style={{ display: "flex", gap: 16, opacity: interpolate(frame, [34, 42], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <div style={{ width: 44, height: 44, flexShrink: 0, borderRadius: 12, display: "grid", placeItems: "center", background: `linear-gradient(135deg, ${C.indigo}, ${C.violet})`, fontWeight: 800, fontSize: 22, color: "#fff" }}>D</div>
        <div style={card({ padding: "18px 24px", fontSize: 23, lineHeight: 1.55, color: C.fg })}>
          {a.slice(0, aTyped)}
          {aTyped < a.length && <span style={{ color: C.cyan }}>▍</span>}
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            {chips.map((c, i) => {
              const s = interpolate(frame, [100 + i * 6, 108 + i * 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <span key={c} style={{ fontFamily: mono, fontSize: 16, padding: "5px 12px", borderRadius: 8, border: "1px solid rgba(79,70,229,0.3)", background: "rgba(79,70,229,0.06)", color: "#4338ca", opacity: s, transform: `translateY(${(1 - s) * 8}px)` }}>
                  [{i + 1}] {c}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
