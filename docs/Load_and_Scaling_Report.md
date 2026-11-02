# Docify — Load, Scaling & Resilience Test Report

Date: 1–2 Nov 2026 · Environments: prod + staging on k3s (one `t4g.large`, Mumbai) and a one-evening EKS lab.
Everything here was run for real and measured; raw incident notes are in `docs/incidents/`.
Total cost of all tests: **≈ $0.25 of AWS credits, $0 on the card.**

---

## 1. Summary

| Test | What we did | Result |
| --- | --- | --- |
| **API load test (prod)** | 50 virtual users for 10 min through CloudFront | **30,668 requests, 0 errors**, p95 **107 ms** |
| **API auto-scaling (HPA)** | Same load test | API pods **2 → 3** in ~80 s, back to 2 after load stopped |
| **Worker burst (KEDA)** | 500 background jobs dropped into the queue at once | Workers **0 → 3 → 0**, queue drained in ~4 min |
| **EKS lab — node scaling** | 6 API pods forced on real Amazon EKS | Cluster Autoscaler added nodes **3 → 5** in ~40 s, then scaled back **5 → 3** |
| **EKS lab — load test** | 50 users through an AWS load balancer | **16,609 requests, 0 errors**, p95 **40 ms** |
| **Chaos 1** | Killed an API pod under traffic | **400/400 OK**, 0 failed requests |
| **Chaos 2** | Killed a worker in the middle of a job | Job retried and finished **exactly once** |
| **Chaos 3** | Database stopped for 60 s | Errors during the outage, **self-recovered 6 s** after the DB came back |
| **Chaos 4** | Shipped a broken release | **0 errors** — bad image never reached users; rolled back with `git revert` |
| **Chaos 5** | Forced a real 5xx error burst | Alert fired and the **e-mail arrived** |
| **Restore drill** | Restored the nightly backup into a scratch DB | **RTO 20 s** (target 30 min) |

**Verdict:** the system scales up and down by itself, survives pod/worker/database failures, blocks bad releases,
alerts on errors, and can be restored from backup in seconds.

---

## 2. Setup (what was being tested)

- **Prod/staging:** one ARM server (`t4g.large`, 2 vCPU, 8 GB) running k3s. CloudFront in front.
- **API scaling:** Kubernetes HPA on CPU 70 %, prod min 2 / max 3 pods.
- **Worker scaling:** KEDA watching the SQS queue (2 messages per worker), min 0 / max 3, 5-min cooldown.
- **Safety:** PodDisruptionBudget (always ≥ 1 API pod), readiness probes, graceful shutdown, job leases + fencing tokens.
- **Tools:** k6 (`scripts/load/api.js`), burst generator (`scripts/load/burst.sh`), chaos scripts (`scripts/chaos/`).

**Traffic mix (k6):** read-only public demo endpoints, so no AI cost — 35 % open a doc, 25 % list docs,
20 % search docs, 10 % list repos, 10 % other. Pass rules: < 1 % errors, p95 < 1.5 s, > 99 % checks OK.

**Burst jobs:** special `loadtest` messages that only simulate work (3 s sleep), so 500 jobs cost $0
(real AI jobs would cost money). They are only accepted when `LOADTEST_MESSAGES=true` (decision D64).

---

## 3. API load test — prod (1 Nov)

`k6 run -e BASE=https://docify.work -e VUS=50 -e DURATION=10m scripts/load/api.js`

| Metric | Value |
| --- | --- |
| Virtual users | 50 (1 min ramp-up, 10 min steady, 30 s ramp-down) |
| Requests | **30,668** (~44 per second) |
| Errors | **0 %** (0 of 30,668) |
| Checks passed | 100 % |
| Latency avg / median | 50 ms / 32 ms |
| Latency p90 / **p95** | 67 ms / **107 ms** |
| Latency max | 2.08 s (one outlier, during the scale-up) |

**Scaling timeline:** API pods 2 → **3** about 80 s after load started (CPU went over 70 %), stayed at 3 during
the test, went back to **2** about 5 min after the load stopped. All thresholds passed.

## 4. Worker burst — KEDA (1 Nov)

`scripts/load/burst.sh prod 500 3000`

| Step | Time |
| --- | --- |
| 500 messages sent to the prod queue | t = 0 |
| KEDA sees the queue, workers 0 → 1 → **3** (max) | < 1 min |
| Queue empty | ~4 min |
| Workers back to **0** | after the 5-min cooldown |

No failed jobs, nothing in the dead-letter queue.

## 5. EKS lab — real Kubernetes autoscaling (1 Nov, 23:00–00:06)

Same app on Amazon EKS + RDS Postgres, arm64 spot nodes, Cluster Autoscaler, AWS Load Balancer Controller.
Built with Terraform and **destroyed the same night** (35 resources, verified nothing left running).

| Test | Result |
| --- | --- |
| Force 6 API replicas | 4 pods Pending ("Too many pods") → node limit raised → Cluster Autoscaler **3 → 5 nodes** in ~40 s, all 6 Running |
| k6 50 users via the ALB | **16,609 requests, 0 errors**, avg 32 ms, p95 **40 ms**, max 392 ms |
| KEDA burst on the lab queue | workers **0 → 3 → 0** |
| Scale-in after the test | nodes **5 → 4 → 3** (timeline in the lab log: 23:22 = 5, 23:24 = 4, 23:28 = 3) |

**Real-world problem hit (good learning):** the cheap "spot" server was taken back by AWS twice, then AWS had none
left (`UnfulfillableCapacity`) → lab API down ~10 min. Fixed by allowing 7 server types. Full write-up:
`docs/incidents/2026-11-01-eks-lab-spot-capacity.md`.

## 6. Chaos (break-it) tests (2 Nov)

| # | Break | What happened | Notes |
| --- | --- | --- | --- |
| 1 | Delete 1 of 2 prod API pods during 400 requests | New pod Ready in < 20 s, **400 OK / 0 failed** | 2 replicas + PDB + readiness probe |
| 2 | Force-kill the worker mid-job | Lease expired after 5 min → job re-claimed (fence 2) → **finished once** | Fencing stops a "zombie" double-write |
| 3 | Stop Postgres 60 s | 12 s of 500s, then 503s; **back 6 s after DB Ready**, no pod restarts | First try: Argo CD put the DB back in 4 s by itself |
| 4 | Deploy a non-existent image to staging | Migrate hook blocked it, old pods kept serving, **90 × 200, 0 errors** | Rollback via `git revert` took ~5.5 min (Argo polls every 3 min) |
| 5 | Make staging return 500s (DB permission revoked) | "API 5xx > 5 %" alert fired after 10 min, **e-mail delivered** | k6: 6,623 requests, 79 % failed on purpose |
| — | Restore drill | Backup restored + verified in **20 s** | 2 script bugs found and fixed |

Each one has an incident note in `docs/incidents/`.

---

## 7. Honest limits — what this is NOT

- **It is not "huge" traffic.** 50 users ≈ 44 requests/second ≈ **3.8 million requests/day** if sustained.
  That is plenty for a portfolio project, but it is not a stress test to the breaking point.
- **We never found the breaking point.** Prod max is 3 API pods on one server (by design, to stay in budget);
  CPU and p95 were still comfortable. A real "max capacity" test would need a bigger cluster.
- **Read-only traffic only.** Chat (AI) was not load-tested on purpose — every chat costs real Bedrock money.
- **Single server for prod.** If the `t4g.large` itself dies, the app is down until it restarts (~2 min).
  The EKS lab showed the multi-node design works, but it is not running permanently (cost).

## 8. Follow-ups (optional)

1. **Stress test to the limit** (e.g. ramp 50 → 300 users on staging) to find max requests/second on one node — ~$0.
2. Small **chat load test** (e.g. 5 users × 5 min) to measure AI latency and cost per answer — a few cents of credits.
3. GitHub → Argo CD **webhook** so rollbacks take seconds instead of ~5 min.
4. Alert on **pods stuck Pending** for 5 min (from the EKS lab incident).
5. Real multi-node setup: on-demand base node + spot for bursts, VPC CNI prefix delegation.

## 9. How to re-run

```bash
# API load (read-only, $0)
k6 run -e BASE=https://staging.docify.work -e VUS=50 -e DURATION=10m scripts/load/api.js
# Worker burst ($0, simulated work)
scripts/load/burst.sh staging 200 3000
# Chaos
scripts/chaos/kill-api-pod.sh · kill-worker-mid-job.sh · stop-postgres.sh · bad-release.sh · force-5xx.sh · restore-drill.sh
```
