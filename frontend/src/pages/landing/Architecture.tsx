import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Reveal } from "./fx";
import { EASE } from "./motion-utils";

type NodeId = "browser" | "cdn" | "s3" | "api" | "github" | "lambda" | "sqs" | "worker" | "pg" | "ai" | "argo";

const NODES: Record<NodeId, { x: number; y: number; label: string; sub: string; detail: string; color: string }> = {
  browser: { x: 90, y: 190, label: "Browser", sub: "React SPA", detail: "Static app, same-origin API calls, session cookie (no tokens in JS).", color: "#f2f2f7" },
  cdn: { x: 300, y: 190, label: "CloudFront", sub: "the only door", detail: "Serves the SPA from S3 and proxies /api/* to the origin over TLS. The server only accepts CloudFront traffic.", color: "#fbbf24" },
  s3: { x: 300, y: 60, label: "S3", sub: "web assets", detail: "Private bucket, readable only by CloudFront (OAC).", color: "#34d399" },
  api: { x: 640, y: 190, label: "API", sub: "FastAPI · HPA 2→3", detail: "Stateless pods behind Traefik. Scales on CPU; a deleted pod costs zero failed requests.", color: "#a5a8ff" },
  github: { x: 90, y: 410, label: "GitHub", sub: "push webhooks", detail: "The Docify GitHub App: read-only, installed per repo.", color: "#f2f2f7" },
  lambda: { x: 300, y: 410, label: "Lambda", sub: "verify HMAC", detail: "Always on, costs ~$0. Verifies the signature, filters, enqueues. Works while the server sleeps.", color: "#fbbf24" },
  sqs: { x: 470, y: 410, label: "SQS", sub: "14-day buffer", detail: "Durable queue + dead-letter queue. Nothing is lost during deploys or nights.", color: "#c084fc" },
  worker: { x: 640, y: 410, label: "Worker", sub: "KEDA 0→3", detail: "Leases + fencing so a job runs exactly once. Scales from zero on queue depth.", color: "#22d3ee" },
  pg: { x: 870, y: 300, label: "Postgres", sub: "+ pgvector", detail: "Docs, chunks and vectors in one database. Hybrid search = vectors + full-text, fused with RRF.", color: "#60a5fa" },
  ai: { x: 870, y: 500, label: "Claude", sub: "+ Voyage", detail: "Summaries, docs, changelog and chat. Hard daily and per-workspace budgets.", color: "#a5a8ff" },
  argo: { x: 870, y: 105, label: "Argo CD", sub: "GitOps", detail: "The cluster mirrors Git. Change a values file → it deploys; change the cluster by hand → it heals back.", color: "#fb923c" },
};

const EDGES: { from: NodeId; to: NodeId; d: string; flow: "web" | "push" | "ops" }[] = [
  { from: "browser", to: "cdn", d: "M150 190 H240", flow: "web" },
  { from: "cdn", to: "s3", d: "M300 160 V90", flow: "web" },
  { from: "cdn", to: "api", d: "M360 190 H580", flow: "web" },
  { from: "api", to: "pg", d: "M700 190 C 780 190, 800 300, 810 300", flow: "web" },
  { from: "github", to: "lambda", d: "M150 410 H240", flow: "push" },
  { from: "lambda", to: "sqs", d: "M360 410 H415", flow: "push" },
  { from: "sqs", to: "worker", d: "M525 410 H580", flow: "push" },
  { from: "worker", to: "pg", d: "M700 410 C 780 410, 790 300, 810 300", flow: "push" },
  { from: "worker", to: "ai", d: "M700 410 C 780 410, 790 500, 810 500", flow: "push" },
  { from: "argo", to: "api", d: "M820 125 C 760 150, 720 160, 690 168", flow: "ops" },
];

const FLOW_COLOR = { web: "#6366f1", push: "#22d3ee", ops: "#fb923c" };

export function Architecture() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState<NodeId>("lambda");
  const node = NODES[active];

  return (
    <section id="architecture" className="relative scroll-mt-24 overflow-hidden px-5 py-24 sm:py-32">
      <div className="l-grid absolute inset-0 -z-10 opacity-60" aria-hidden="true" />
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="l-eyebrow">Under the hood</p>
        <h2 className="mt-3 text-[clamp(2rem,4.5vw,3.4rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
          Real cloud architecture. <span className="l-gradient-text">Not a toy.</span>
        </h2>
        <p className="mt-4 text-[15px] text-fg-muted">Hover any box. Every piece is defined in code: Terraform, Helm and Argo CD.</p>
      </Reveal>

      <Reveal delay={0.1} className="mx-auto mt-14 max-w-5xl">
        <div className="l-card p-3 sm:p-6">
          <svg viewBox="0 0 960 560" className="h-auto w-full" role="img" aria-label="Docify architecture diagram">
            {/* k3s cluster boundary */}
            <rect x="560" y="40" width="390" height="425" rx="22" fill="rgb(99 102 241 / 0.04)" stroke="rgb(99 102 241 / 0.35)" strokeDasharray="5 7" />
            <text x="578" y="64" fill="#a5a8ff" fontSize="12" fontFamily="ui-monospace, monospace">EC2 · k3s cluster</text>
            <text x="20" y="545" fill="#6c6c7c" fontSize="12" fontFamily="ui-monospace, monospace">everything above = terraform apply</text>

            {EDGES.map((e, i) => {
              const hot = e.from === active || e.to === active;
              return (
                <g key={i}>
                  <motion.path
                    d={e.d}
                    fill="none"
                    stroke={FLOW_COLOR[e.flow]}
                    strokeOpacity={hot ? 0.95 : 0.35}
                    strokeWidth={hot ? 2.5 : 1.75}
                    initial={reduce ? false : { pathLength: 0 }}
                    whileInView={{ pathLength: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.2, ease: EASE, delay: 0.2 + i * 0.08 }}
                  />
                  <path d={e.d} fill="none" stroke="#fff" strokeOpacity={hot ? 0.5 : 0.12} strokeWidth="1" className="l-flow" />
                  {!reduce && (
                    <circle r={hot ? 4 : 3} fill={FLOW_COLOR[e.flow]} style={{ filter: `drop-shadow(0 0 6px ${FLOW_COLOR[e.flow]})` }}>
                      <animateMotion dur={`${1.6 + (i % 3) * 0.4}s`} repeatCount="indefinite" path={e.d} />
                    </circle>
                  )}
                </g>
              );
            })}

            {(Object.keys(NODES) as NodeId[]).map((id) => {
              const n = NODES[id];
              const on = id === active;
              return (
                <g
                  key={id}
                  transform={`translate(${n.x} ${n.y})`}
                  className="cursor-pointer outline-none"
                  tabIndex={0}
                  role="button"
                  aria-label={`${n.label}: ${n.detail}`}
                  onPointerEnter={() => setActive(id)}
                  onFocus={() => setActive(id)}
                >
                  <motion.g animate={{ scale: on ? 1.08 : 1 }} transition={{ type: "spring", stiffness: 300, damping: 20 }}>
                    <rect x="-60" y="-30" width="120" height="60" rx="14" fill="#0f0f18" stroke={on ? n.color : "rgb(255 255 255 / 0.12)"} strokeWidth={on ? 2 : 1}
                      style={{ filter: on ? `drop-shadow(0 0 18px ${n.color})` : undefined }} />
                    <text y="-3" textAnchor="middle" fill={on ? n.color : "#f2f2f7"} fontSize="15" fontWeight="600">{n.label}</text>
                    <text y="15" textAnchor="middle" fill="#6c6c7c" fontSize="11">{n.sub}</text>
                  </motion.g>
                </g>
              );
            })}
          </svg>

          <div className="mt-2 grid gap-4 border-t border-white/[0.06] pt-5 sm:grid-cols-[1fr_auto] sm:items-center">
            <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
              <div className="text-sm font-semibold" style={{ color: node.color }}>{node.label}</div>
              <p className="mt-1 text-sm text-fg-muted">{node.detail}</p>
            </motion.div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              {(["web", "push", "ops"] as const).map((f) => (
                <span key={f} className={cn("inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] px-2.5 py-1 text-fg-subtle")}>
                  <span className="size-2 rounded-full" style={{ background: FLOW_COLOR[f] }} />
                  {f === "web" ? "user request" : f === "push" ? "git push" : "GitOps deploy"}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
