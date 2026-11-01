# Docify — cost report (P14, 2026-11-02)

**Rule for this project:** pay everything from the **$200 AWS credits**; the card must stay at **$0**
(guards: `docify-card-charge` budget alerts on any net charge > $0.01, credit-burn budget, anomaly alerts ≥ $1,
90 %-of-credits budget action stops the server — `docs/AWS_Mumbai_Setup_Summary.md`).

## Actuals so far

| Source | Gross | Net (card) | Note |
| --- | --- | --- | --- |
| Cost Explorer, Oct 2026 + 1 Nov | $0.00 | $0.00 | CE lags ~24 h: the first real usage (1 Nov) shows up on 2–3 Nov |
| App ledger `llm_usage` (Bedrock, real calls since D61) | ≈ $0.006 | $0 (credits) | Nova Micro/Lite + Titan V2: 3 repos indexed, ~10 chats, re-indexes, EKS-lab seed |
| Older `claude-*` rows in the ledger | $0 real | — | written in **fake mode** before D61 (priced, never called) |

⚠ To do on 2–3 Nov: Billing → Credits and Cost Explorer (group by service, *Net unblended*) must show EC2,
Bedrock, EKS, RDS, ELB covered by credits and **$0.00 net**. Bedrock *Amazon* models are first-party services
(credit-eligible); Claude on Bedrock would be Marketplace — not used (IAM allows only `amazon.*` models).

## Steady-state estimate (on-demand list prices, ap-south-1 — verify against CE)

| Item | Unit | 12 h/day (demo mode) | 24/7 |
| --- | --- | --- | --- |
| EC2 t4g.large (`cpu_credits=standard`, no surcharge) | ≈ $0.054/h | ≈ $19.4 | ≈ $39 |
| EBS gp3 30 + 10 GB (root + data) | ≈ $0.091/GB-mo | $3.6 | $3.6 |
| Public IPv4 (server) | $0.005/h while running | $1.8 | $3.6 |
| Route 53 hosted zone | $0.50/mo | $0.5 | $0.5 |
| ECR (~0.8 GB images), S3 (backups, repo cache, web), EBS snapshots | GB-month | < $0.5 | < $0.5 |
| CloudFront, Lambda, SQS, SNS, SES, EventBridge, CloudWatch basics | free-tier levels at our traffic | ~$0 | ~$0 |
| Bedrock (Nova + Titan) | per 1M tokens: Micro $0.041/$0.164, Lite $0.071/$0.284, Titan $0.024 | < $0.5 | < $0.5 |
| **Total** |  | **≈ $26 / month** | **≈ $48 / month** |

$200 credits ≈ **7–8 months** in demo mode (auto-stop 23:00 IST + Start workflow), ≈ 4 months 24/7.
Credits expire Oct 2027.

## One-off: P12 EKS lab (1 Nov, 23:02 → 00:06 IST, destroyed)

| Item | Approx. |
| --- | --- |
| EKS control plane ($0.10/h × ~1 h) | $0.10 |
| Spot nodes (1–5 × Graviton spot ≈ $0.01/h, ~2.5 node-hours incl. interruptions) | $0.03 |
| RDS db.t4g.micro + 20 GB gp3 (~1 h) | $0.03 |
| ALB (~1 h + LCU) | $0.03 |
| Public IPv4 (nodes + ALB) | $0.03 |
| **Lab total** | **≈ $0.25** (credits) |

`scripts/whats-running.sh` after teardown: only the k3s server + the two expected webhook Lambda URLs.

## Cost decisions that mattered

- **One t4g.large k3s node instead of EKS** (D56): EKS alone would be $73/month before any node.
- **No NAT gateway** (public subnets + SG locked to CloudFront): saves ~$40/month in ap-south-1.
- **Graviton + `standard` CPU credits**: cheapest x86-equivalent capacity, no unlimited-mode surprise.
- **Auto-stop 23:00 IST + Start workflow**: halves EC2 + IPv4 cost.
- **Bedrock Nova instead of Claude/Voyage** (D61): AI is credit-covered and ~$0.003 per indexed small repo.
- **KEDA scale-to-zero workers** and **loadtest messages instead of real AI** for burst tests: $0 load testing.
