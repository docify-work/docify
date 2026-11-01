# 2026-11-02 — Chaos 1: kill a prod api pod under traffic

**Env:** prod (k3s) · **Script:** `scripts/chaos/kill-api-pod.sh` (run via SSM) · **Result:** ✅ no impact

| Time (IST) | Event |
| --- | --- |
| 00:23:19 | Traffic starts: `GET https://docify.work/api/version` every 0.1 s through CloudFront (400 requests) |
| 00:23:24 | `kubectl delete pod api-…-f4lwb` (one of 2 replicas) |
| 00:23:44 | Replacement pod Running + Ready (< 20 s) |
| 00:24:05 | Traffic ends: **400 ok / 0 failed** |

**Why it held:** 2 api replicas (HPA min 2) + PDB `minAvailable: 1` + readiness probe (Traefik only routes to Ready
pods) + graceful SIGTERM handling in Uvicorn.

**Follow-ups:** none.
