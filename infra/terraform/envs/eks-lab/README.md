# envs/eks-lab — Phase 12 skeleton (NOT ready, do not apply)

One-day lab: run the same Helm chart on **EKS + RDS**, watch nodes scale, then
**destroy the same day** (Master Doc §23 Phase 12, runbook R12).

> EKS control plane ≈ $0.10/h, NAT-free design, spot nodes. A forgotten lab is
> the biggest budget risk in the project — always finish with R12 +
> `scripts/whats-running.sh`.

## Planned contents (fill in during P12.1)

| Piece | Plan |
| --- | --- |
| Network | reuse `envs/main` VPC (read via `terraform_remote_state` or data sources); nodes in **public** subnets (no NAT) |
| EKS | 1 cluster, managed node group 1–3 × `t3.medium` **spot**, EKS Pod Identity |
| Add-ons | Cluster Autoscaler, AWS Load Balancer Controller (Helm) |
| Database | RDS PostgreSQL 17 `db.t4g.micro` + pgvector, private subnets, no Multi-AZ |
| App | `deploy/values/eks-lab.yaml` |

## Before starting

1. Q10 / V6: is EKS allowed on the Free Plan? If not, upgrade to the Paid plan first.
2. Use a separate state key: `envs/eks-lab/terraform.tfstate` (see `versions.tf`).

## Teardown (R12)

Delete Ingress + `LoadBalancer` Services → wait for the ALB to disappear →
`terraform destroy` → `scripts/whats-running.sh` must be clean.
