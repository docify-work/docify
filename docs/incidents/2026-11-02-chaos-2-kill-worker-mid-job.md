# 2026-11-02 — Chaos 2: kill the worker in the middle of a job

**Env:** prod (k3s) · **Script:** `scripts/chaos/kill-worker-mid-job.sh` (automated: an SSM watcher kills the worker
the moment the job row turns `running`) · **Result:** ✅ job finished exactly once

| Time (IST) | Event |
| --- | --- |
| 00:30 | First attempt: the tip-splitter full re-index finished in ~6 s, 2 s **before** the kill, so nothing was tested (small repo = short job). Re-armed the kill to fire on `running`. |
| 00:33:15 | Full re-index queued (`POST /api/repos/{id}/reindex`); KEDA wakes the worker (0 → 1) |
| 00:33:21 | Job `running attempts=1 fence=1` → worker pod **force-deleted** (`--grace-period=0 --force`, no SIGTERM handling) |
| 00:38:24 | Lease expired (5 min, SQS visibility 300 s) → message redelivered → job re-claimed `attempts=2 fence=2` |
| 00:38:26 | Job `succeeded`; docs and changelog written once |

**What this proves (F50):** the fencing token stops a "zombie" first attempt from writing after the re-claim, and the
lease + SQS redelivery recover a job whose worker vanished.

**Trade-off:** up to 5 min delay after a hard crash (the lease length). A shorter lease means more heartbeat traffic.

**Follow-ups:** none.
