# Docify — instructions for Claude

- **Source of truth:** `docs/Docify_Master_Doc.md` (technical spec + status tracker). Read §0 (rules), §1 (status), §25 (open questions) and the current phase in §23 before doing any work.
- **Scope/budget/goals:** `docs/Docify_Project_Plan.md` (user-approved plan). Don't change scope or add paid resources without asking Ganesh.
- **After each session:** update Master Doc §1, tick §23 tasks, add a row to §27 Session Log, record any design change in §3 Decision Log.
- This is a learning project built live (Ganesh builds, Supriya watches): keep steps explainable and end each phase with a demo.
- Never commit or write real secrets, account IDs, or IPs into the repo or docs.
- **Git:** push straight to `main` (D38) as GitHub user `docify-work`; CI (`ci.yml`, job `all-green`) must stay green.
- **UI:** compact, professional, tooltip-first, global component kit (`frontend/src/components/ui/`), smooth animations.

## Working locally (Windows)

- Services: `docker compose up -d postgres valkey elasticmq mailpit` — host ports **55432** (Postgres), **56379** (Valkey), 9324 (ElasticMQ), 8025 (Mailpit UI). Non-standard ports avoid clashing with a locally installed Postgres/Redis.
- Backend: `cd backend && uv sync && uv run docify api --reload` · worker `uv run docify worker` · tests `uv run pytest -q` (integration tests need the services) · lint `uv run ruff check src tests ../lambdas && uv run mypy src`.
- Demo data: `uv run docify seed-demo --from-dir src/docify/demo/eval_data/fixture-repo` then `uv run docify eval`.
- After changing models: regenerate/extend Alembic migrations and keep `uv run alembic check` clean (CI enforces it).
- Lambda shares `backend/src/docify/ingest/{verify,normalise}.py` — copy with `make sync-lambda` (a test fails on drift).
- Portable tools (git-ignored) live in `.tools/`: helm, kind, terraform, tflint, kubeconform, actionlint, hadolint. `deploy/validate.sh` and `terraform validate` run in CI too.
- AWS: account currently blocked by an org SCP (Q11) — never run `terraform apply` or AWS-mutating commands without Ganesh.
