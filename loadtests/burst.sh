#!/usr/bin/env bash
# KEDA burst test (P11): enqueue N cheap jobs and watch workers scale 0 → max → 0.
#
#   loadtests/burst.sh docify-staging 500
#
# Uses only `repo_sync` jobs for repos already in the namespace's database; with AI_MODE=fake
# (staging during the test) nothing costs money. Coalescing (§8.3) means N messages for the same
# repo collapse into ≤ 1 queued + 1 running job, so we send *notification* messages for the
# same job ids repeatedly — the point is the queue depth KEDA sees, not N real jobs.
set -euo pipefail

NS="${1:?namespace, e.g. docify-staging}"
N="${2:-500}"

echo "Sending $N messages via the api pod in $NS ..."
kubectl -n "$NS" exec deploy/api -- python - "$N" <<'PY'
import asyncio, sys
from sqlalchemy import select
from docify.db.models import Repository
from docify.db.session import init_engine, session_scope
from docify.jobs import service
from docify.jobs.queue import get_queue, job_message

async def main(n: int) -> None:
    init_engine(pool_size=2)
    async with session_scope() as db:
        repos = (await db.execute(select(Repository).where(Repository.status == "ready"))).scalars().all()
        if not repos:
            raise SystemExit("no ready repos to sync")
        ids = [(await service.enqueue(db, "repo_sync", workspace_id=r.workspace_id, repo_id=r.id,
                                      payload={"reason": "burst-test"})).job_id for r in repos]
    q = get_queue()
    for i in range(n):
        await q.send(job_message(str(ids[i % len(ids)])))
    print(f"sent {n} messages for {len(ids)} jobs")

asyncio.run(main(int(sys.argv[1])))
PY
echo "Now watch: kubectl -n $NS get pods -l app.kubernetes.io/component=worker -w"
