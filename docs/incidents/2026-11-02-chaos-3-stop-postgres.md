# 2026-11-02 — Chaos 3: Postgres down for 60 s

**Env:** prod + staging (shared Postgres in `data`) · **Script:** `scripts/chaos/stop-postgres.sh` · **Result:** ✅ self-healed after 72 s of errors

## First attempt — Argo CD put Postgres back in 4 s

At 00:38:55, `kubectl scale statefulset/postgres --replicas=0`. The `data` app (automated sync + **selfHeal**) saw
the drift and scaled it back; `postgres-0` was re-created at 00:38:59. Only 6 requests failed.

This is the **P7 acceptance check "a manual edit is reverted by selfHeal"**, proven live. It also means the chaos
script must pause auto-sync first.

Side finding: a `FailedPreStopHook` event on `postgres-0`, which is harmless. The preStop runs `pg_ctl stop -m fast`;
Postgres exits, and the container dies while the hook's exec is still attached, so the kubelet reports the hook as
failed. The log shows a **clean** shutdown ("database system was shut down at …", no crash recovery on start).

## Second attempt — auto-sync paused (root + data apps)

| Time (IST) | Event |
| --- | --- |
| 00:44:24 | Auto-sync paused on `root` and `data`; Postgres scaled to 0 (pod gone 00:44:26) |
| 00:44:26–00:44:38 | `GET /api/workspaces/demo/docs` → **500** (pods still Ready, DB calls fail) |
| 00:44:38–00:45:38 | → **503** (readiness `/api/ready` fails → Traefik has no endpoints) |
| 00:45:26 | Postgres scaled back to 1, Ready at 00:45:32 |
| 00:45:38 | 200 again, **6 s after Postgres was Ready**; no restarts needed |
| 00:46 | Auto-sync restored on `root` (which re-applies the child apps' sync policy) |

Traffic: 78 × 200, 5 × 500, 27 × 503. The reconcile CronJob that ran during the outage failed, so Argo showed
`docify-prod/staging` **Degraded** until the next run 15 min later (expected, harmless).

## Follow-ups

- [x] Runbook note: pause auto-sync (root + data) before a planned Postgres stop (Master Doc §22 R7).
- [ ] Optional: a shorter readiness period would turn the first ~12 s of 500s into 503s sooner. Fine as is.
