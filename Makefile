# Docify developer commands. Windows without make: run the command after each target by hand.
.PHONY: up down logs infra api worker web test test-unit lint fmt migrate seed eval gen-api sync-lambda check-lambda image

up:            ## full local stack (postgres, valkey, elasticmq, mailpit, api, worker)
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f api worker
infra:         ## only the backing services; run api/worker with uv for fast reloads
	docker compose up -d postgres valkey elasticmq mailpit
api:
	cd backend && uv run docify api --reload
worker:
	cd backend && uv run docify worker
web:
	cd frontend && npm run dev
migrate:
	cd backend && uv run docify migrate
seed:          ## index the bundled fixture repo into the public "demo" workspace (fake AI)
	cd backend && uv run docify seed-demo --from-dir src/docify/demo/eval_data/fixture-repo
eval:
	cd backend && uv run docify eval
test:          ## needs `make infra`
	cd backend && uv run pytest -q
test-unit:
	cd backend && uv run pytest -q tests/unit
lint:
	cd backend && uv run ruff check src tests && uv run mypy src
	cd frontend && npm run lint && npm run typecheck
fmt:
	cd backend && uv run ruff check --fix src tests
gen-api:       ## export OpenAPI and regenerate frontend types
	cd backend && uv run python -c "import json; from docify.api.app import create_app; open('../frontend/openapi.json','w').write(json.dumps(create_app(start_background=False).openapi(), indent=1))"
	cd frontend && npm run gen-api
sync-lambda:   ## the Lambda ships its own copy of the shared ingest code
	cp backend/src/docify/ingest/verify.py backend/src/docify/ingest/normalise.py lambdas/webhook_ingest/
check-lambda:
	diff -q backend/src/docify/ingest/verify.py lambdas/webhook_ingest/verify.py
	diff -q backend/src/docify/ingest/normalise.py lambdas/webhook_ingest/normalise.py
image:
	docker build -t docify-backend:dev --build-arg GIT_SHA=$$(git rev-parse HEAD) backend
