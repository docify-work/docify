# Docify backend

FastAPI API + SQS worker + jobs + AI. See `docs/Docify_Master_Doc.md` §5.2.

```bash
uv sync
uv run docify api        # http://localhost:8000/api/docs
uv run docify worker
uv run pytest            # unit tests; integration tests need `docker compose up -d postgres valkey elasticmq`
```
