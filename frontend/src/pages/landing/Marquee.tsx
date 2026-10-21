import { Bot, Boxes, Cloud, Container, Database, Gauge, Layers, Radar, Server, Ship, Webhook, Workflow, Zap } from "lucide-react";
import { GitHubIcon } from "@/components/BrandIcons";
import { Reveal } from "./fx";

const ITEMS = [
  { icon: <GitHubIcon className="size-4" />, label: "GitHub App" },
  { icon: <Bot className="size-4" />, label: "Claude" },
  { icon: <Radar className="size-4" />, label: "Voyage embeddings" },
  { icon: <Database className="size-4" />, label: "Postgres + pgvector" },
  { icon: <Zap className="size-4" />, label: "FastAPI" },
  { icon: <Ship className="size-4" />, label: "Kubernetes (k3s)" },
  { icon: <Workflow className="size-4" />, label: "Argo CD GitOps" },
  { icon: <Layers className="size-4" />, label: "Terraform" },
  { icon: <Webhook className="size-4" />, label: "AWS Lambda" },
  { icon: <Boxes className="size-4" />, label: "Amazon SQS" },
  { icon: <Cloud className="size-4" />, label: "CloudFront" },
  { icon: <Container className="size-4" />, label: "Docker" },
  { icon: <Gauge className="size-4" />, label: "Prometheus + Grafana" },
  { icon: <Server className="size-4" />, label: "KEDA autoscaling" },
];

export function Marquee() {
  const row = [...ITEMS, ...ITEMS];
  return (
    <section aria-label="Built with" className="relative border-y border-black/[0.06] bg-black/[0.015] py-8">
      <Reveal>
        <p className="mb-6 text-center text-xs font-medium uppercase tracking-[0.18em] text-fg-subtle">
          Production-grade from day one — built on
        </p>
      </Reveal>
      <div className="l-marquee overflow-hidden">
        <div className="l-marquee-track gap-3">
          {row.map((it, i) => (
            <span
              key={i}
              aria-hidden={i >= ITEMS.length}
              className="mx-1.5 inline-flex shrink-0 items-center gap-2 rounded-full border border-black/[0.07] bg-black/[0.03] px-4 py-2 text-sm text-fg-muted transition-colors hover:border-black/20 hover:text-fg"
            >
              <span className="text-[var(--accent-text)]">{it.icon}</span>
              {it.label}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
