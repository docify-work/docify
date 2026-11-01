# 2026-11-02 — Restore drill (R7)

**Script:** `scripts/chaos/restore-drill.sh` (on the server via SSM) · **Result:** ✅ **RTO 20 s** (target < 30 min)

Steps: the latest backup `postgres/2026-11-01/20261101T223002.sql.gz` (276 KB) is restored into a throwaway Postgres
(same pgvector image) in namespace `restore-drill`. Then `docify migrate` and `docify verify-db` run for `docify_prod`
and `docify_staging`, and the namespace is deleted. Live data is never touched.

| DB | verify-db | Restored rows | Live rows now |
| --- | --- | --- | --- |
| docify_prod | alembic 0003 = head, extensions OK | 2 repos, 27 chunks, 24 doc versions | 2 repos, 27 chunks, 30 doc versions |
| docify_staging | alembic 0003 = head, extensions OK | 1 repo, 16 chunks, 6 doc versions | 1 repo, 16 chunks, 6 doc versions |

## Findings fixed during the drill

1. The dump contains `ALTER ROLE postgres … PASSWORD`, which overwrote the scratch password, so verify failed. The
   script now re-sets the scratch password after the restore.
2. The backup (22:30) was older than migration 0003 (deployed 22:37), so verify-db reported `MISMATCH`. A real
   restore runs migrations, so the drill now runs `docify migrate` before verifying.

**RPO** = time since the nightly backup (22:30 IST): the 6 prod doc versions created after it are missing, as
expected. Repeat every 3 months (Master Doc §18).
