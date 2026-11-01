# 2026-11-01 — EKS lab: spot node lost twice, then "UnfulfillableCapacity"; pods stuck on max-pods

**Env:** EKS lab (P12), not production · **Impact:** lab API down ~10 min (504 from the ALB) · **Severity:** low (lab)

## Timeline (IST)

| Time | Event |
| --- | --- |
| 23:01 | Node group created: 1 × `t4g.medium` **spot** (single instance type) |
| 23:05 | Spot **rebalance recommendation** → ASG launches a replacement, old node drained |
| 23:08 | Replacement node gets an **interruption notice** too, drained |
| 23:09–23:11 | ASG retries every minute: `Could not launch Spot Instances. UnfulfillableCapacity` → 0 nodes, all pods Pending, ALB targets time out → **504** |
| 23:12 | Fix applied: node group allows 7 Graviton types (t4g.medium/large, m6g/m7g.medium, c6g/c7g.large, r6g.medium) — node group replaced in 1 m 47 s |
| 23:15 | m6g.medium spot node Ready, API answering through the ALB again |
| 23:38 | Forced 6 api replicas (P12 AC): 4 Pending with **"Too many pods"** although a t4g.large had free CPU |
| 23:41 | Cause: node group max = 3 reached and per-node pod limit is low; `node_max` 3 → 5, Cluster Autoscaler added 2 nodes in ~40 s, all 6 pods Running |

## Root causes

1. **One spot instance type = one capacity pool.** `t4g.medium` spot in ap-south-1 had little spare capacity that evening; AWS reclaimed it twice and then could not supply it at all.
2. **Mixed instance types → smallest max-pods.** A managed node group with several instance types computes `maxPods` for the *smallest* type (VPC CNI ENI/IP limits: `*.medium` = 8 pods). DaemonSets (aws-node, kube-proxy, pod-identity agent, ...) use part of that, so a 2-vCPU `t4g.large` still fits only a few app pods.

## Fixes / follow-ups

- [x] Diversify spot instance types (≥ 5 types, same architecture) — `envs/eks-lab/variables.tf`.
- [x] Node group max 5 for the lab so the autoscaler has headroom.
- [ ] Real cluster: keep a small **on-demand** base node group for system pods + spot for burst; enable VPC CNI **prefix delegation** (raises max pods to ~110) or use same-size instance types per node group.
- [ ] Add an alert on `kube_pod_status_phase{phase="Pending"} > 0 for 5m` (it would have pointed straight at scheduling).

## Lessons

Spot is cheap because it can disappear: design for it (multiple pools, PDBs, more than one node, fast rescheduling) instead of hoping it stays. And "free CPU on a node" is not "room for a pod": check pod-count limits too.
