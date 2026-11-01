# 2026-11-02 — Chaos 4: bad release (non-existent image tag) to staging

**Env:** staging · **Script:** `scripts/chaos/bad-release.sh` · **Result:** ✅ zero downtime, rolled back by `git revert`

| Time (IST) | Event |
| --- | --- |
| 00:49:13 | Commit `chaos: deploy a non-existent image tag to staging` pushed (`image.tag: does-not-exist`) |
| 00:49–00:51 | Argo CD syncs. The **migrate hook (wave -1) runs first** with the new image → `ImagePullBackOff` → the sync waits on the hook. **The api/worker Deployments were never changed**, so the old pods kept serving |
| 00:56:54 | `git revert` pushed (an earlier attempt failed because `git revert -q` is not a valid flag) |
| 01:02:24 | Argo picked up the revert on its next Git poll (3 min) and finished the sync: `Synced Healthy` |

Staging traffic during the whole test: **90 × 200, 0 errors**.

## What we learned

- The migrate hook is a free **gate**: an image that can't start never reaches the Deployments. The runbook expected
  "new ReplicaSet stuck, old pods serve"; the real behaviour is even safer.
- Rollback time is dominated by Argo's 3-minute Git polling.
  **Follow-up:** add a GitHub → Argo CD webhook (or `argocd app sync` in the runbook) to cut detection and rollback
  to seconds.
- `deploy/values/**` changes don't trigger `release.yml` (path filter), so a bad bump is not "fixed" by a new release.
