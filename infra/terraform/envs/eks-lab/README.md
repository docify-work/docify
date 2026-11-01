# envs/eks-lab — Phase 12 (one evening, then destroyed)

Runs the **same Helm chart** on **EKS + RDS** to show that moving off k3s is a
values change, not a rewrite. Destroy the same day (runbook R12).

| Piece | What |
| --- | --- |
| Network | reuses the `envs/main` VPC; nodes in the **public** subnets (no NAT); ALB discovery tag added with `aws_ec2_tag` (removed on destroy) |
| EKS | `docify-eks-lab`, standard support only, API auth mode, managed node group 1–3 × `t4g.medium` **spot** (arm64: our images are arm64-only) |
| Add-ons | vpc-cni (network policies on), kube-proxy, coredns, eks-pod-identity-agent, metrics-server (EKS add-ons); Cluster Autoscaler, AWS Load Balancer Controller, External Secrets, KEDA (Helm, see R12 below) |
| Identity | EKS **Pod Identity** roles: autoscaler, lbc, external-secrets, keda-operator, `docify-lab/docify` (SQS lab queue, S3 repo cache, Bedrock Amazon models) |
| Queue | own `docify-lab-events` (+ DLQ): sharing the staging queue would let lab workers drop staging jobs |
| Database | RDS PostgreSQL 17 `db.t4g.micro`, private subnets, user/db/password = staging's (`/docify/staging/db/password`), no backups, no final snapshot |
| App | `deploy/values/eks-lab.yaml` + `--set` for account-specific values |

Cost ≈ **$0.20/h** (EKS $0.10 + spot nodes + RDS + ALB + public IPv4), paid
from AWS credits. Result of the lab: Master Doc §27 (2026-11-01).

## Run

```bash
eval "$(aws configure export-credentials --profile docify --format env)"; export AWS_REGION=ap-south-1
terraform init -backend-config=../main/backend.hcl
echo 'repo_cache_bucket = "<terraform -chdir=../main output bucket_names .repo_cache>"' > terraform.tfvars  # git-ignored
terraform apply
aws eks update-kubeconfig --name docify-eks-lab
```

Then install the add-ons + chart (commands in Master Doc §27 P12 row / R12).

## Teardown (R12)

`helm uninstall` the app (deletes the Ingress → ALB) → wait until
`aws elbv2 describe-load-balancers` shows no `k8s-docifyla*` ALB → delete the
`eks-lab` Route 53 record → `terraform destroy` → `scripts/whats-running.sh`
must be clean.
