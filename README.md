# Docify

> Docify reads a GitHub repo, writes documentation for it with AI, keeps that documentation updated when the code changes, and lets people search and chat with it — answers link to the exact file lines.

The app is the excuse — the real goal is to learn **DevOps, Cloud, System Design and Scaling** by building, shipping and running a real product end to end on a small budget.

| | |
|---|---|
| ![Demo dashboard](docs/screenshots/light-04-demo-dashboard.png) | ![Chat with citations](docs/screenshots/light-08-chat.png) |
| ![Generated doc (dark)](docs/screenshots/dark-06-doc.png) | ![Command palette](docs/screenshots/dark-16-palette.png) |

## Stack

| Area | Stack |
|---|---|
| Frontend | Vite + React 19 + TypeScript + Tailwind v4, Radix primitives, TanStack Query (static SPA on S3 + CloudFront) |
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 (async) · Alembic · server-side sessions · GitHub/Google OAuth |
| Worker | SQS consumer with row leases + fencing, coalescing, retries, reconciler |
| Data | Postgres 17 + pgvector (hybrid vector + full-text search) · Valkey 8 |
| AI | Anthropic Claude (Haiku) for summaries, docs, changelog and chat · Voyage `voyage-code-3` embeddings |
| Platform | k3s on one EC2 instance · Argo CD (GitOps, app-of-apps) · Helm · cert-manager · External Secrets · KEDA · Traefik |
| Infra | Terraform (S3 backend) · CloudFront · Lambda webhook ingest → SQS · SSM · SES · Route 53 · ECR · EventBridge Scheduler |
| CI/CD | GitHub Actions (SHA-pinned) with OIDC · Trivy · hadolint · kubeconform · tflint |
| Observability | Prometheus · Grafana (dashboards + alerts as code) · Loki · Alloy |

## Status

Live progress is tracked in [`docs/Docify_Master_Doc.md`](docs/Docify_Master_Doc.md) §1 and §23.

- ✅ Backend, worker, Lambda, frontend, Docker image, CI — built and tested (140+ backend tests incl. integration on real Postgres/Valkey/SQS).
- ✅ Terraform, Helm charts, Argo CD apps, dashboards — written and statically validated.
- ⏳ AWS deployment — waiting on account setup. Until real API keys are added, AI runs in deterministic **fake mode** (`AI_MODE=fake`).

## Quick start (local)

Requirements: Docker Desktop, [uv](https://docs.astral.sh/uv/), Node 22.12+.

```bash
cp .env.example .env
docker compose up -d postgres valkey elasticmq mailpit     # Postgres :55432, Valkey :56379, SQS :9324, Mailpit :8025
cd backend && uv sync && uv run docify migrate
uv run docify seed-demo --from-dir src/docify/demo/eval_data/fixture-repo   # public "demo" workspace
uv run docify api --reload          # http://localhost:8000/api/docs
uv run docify worker                # in another terminal
cd ../frontend && npm ci && npm run dev                      # http://localhost:5173
```

Or run everything in containers (the same image CI ships): `docker compose up -d --build`.

Tests: `cd backend && uv run pytest -q` · `cd frontend && npm test -- --run`. All `make` targets are listed in the [`Makefile`](Makefile) (each is a one-line command you can also run by hand on Windows).

## Repository layout

```text
backend/      FastAPI app, worker, jobs, AI, GitHub integration (Python package `docify`)
frontend/     React SPA (design tokens + shared UI kit in src/components/ui)
lambdas/      webhook-ingest Lambda (GitHub → SQS)
deploy/       Helm charts, Argo CD app-of-apps, per-env values, dashboards
infra/        Terraform (bootstrap, modules, envs) + server bootstrap script
scripts/      smoke tests, ops helpers
docs/         plan, master doc (spec + tracker), screenshots, incident notes
```

## Docs

- [`docs/Docify_Project_Plan.md`](docs/Docify_Project_Plan.md) — the simple plan: why, what, scope and budget.
- [`docs/Docify_Master_Doc.md`](docs/Docify_Master_Doc.md) — the full technical spec, decision log and live tracker.
- [`deploy/README.md`](deploy/README.md) · [`infra/README.md`](infra/README.md) — how the platform and AWS pieces fit together.

## Licence

[MIT](LICENSE)
