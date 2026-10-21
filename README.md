# Docify

> Docify reads a GitHub repo, writes documentation for it with AI, keeps that documentation updated when the code changes, and lets people search and chat with it (answers link to exact file lines).

The app is the excuse — the real goal is to learn **DevOps, Cloud, System Design and Scaling** by building, shipping and running a real product end to end on a small budget.

| Area | Stack |
|---|---|
| Frontend | Vite + React 19 + TypeScript + Tailwind v4 (static SPA on S3 + CloudFront) |
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 (async) · Alembic |
| Worker | SQS consumer with leases, fencing, coalescing and retries |
| Data | Postgres 17 + pgvector · Valkey 8 |
| AI | Anthropic Claude (docs, summaries, chat) · Voyage `voyage-code-3` embeddings · hybrid RAG |
| Platform | k3s on one EC2 instance · Argo CD (GitOps) · Helm · cert-manager · External Secrets · KEDA · Traefik |
| Infra | Terraform (S3 backend) · CloudFront · Lambda webhook ingest → SQS · SSM · SES · Route 53 · ECR |
| CI/CD | GitHub Actions with OIDC · Trivy · staging auto-deploy, prod behind approval |
| Observability | Prometheus · Grafana · Loki · Alloy |

## Docs

- [`docs/Docify_Project_Plan.md`](docs/Docify_Project_Plan.md) — the simple plan: why, what, scope and budget.
- [`docs/Docify_Master_Doc.md`](docs/Docify_Master_Doc.md) — the full technical spec **and** live progress tracker (status in §1, roadmap in §23).

## Quick start (local)

Requirements: Docker Desktop, [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
cp .env.example .env          # local defaults: fake AI, local storage, Mailpit
docker compose up -d --build  # postgres, valkey, elasticmq, mailpit, api, worker
cd frontend && npm install && npm run dev
```

- App: http://localhost:5173 · API docs: http://localhost:8000/api/docs · Mail: http://localhost:8025

Without `make` (Windows): every Makefile target is a short command — see the [`Makefile`](Makefile).

## Repository layout

```text
backend/      FastAPI app, worker, jobs, AI, GitHub integration (Python package `docify`)
frontend/     React SPA
lambdas/      webhook-ingest Lambda (GitHub → SQS)
deploy/       Helm charts, Argo CD app-of-apps, per-env values
infra/        Terraform (bootstrap, modules, envs) + server bootstrap script
scripts/      smoke tests, ops helpers, chaos scripts
loadtests/    k6 scripts
evals/        AI retrieval evaluation
docs/         plan, master doc, incident notes
```

## Licence

[MIT](LICENSE)
