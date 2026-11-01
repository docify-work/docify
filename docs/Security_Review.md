# Docify — security & IAM review (P13.2, 2026-11-02)

Scope: the Docify AWS account (ap-south-1), the k3s server, CI. Method: `aws iam list-roles` + every inline/attached
policy, Terraform (`infra/terraform/modules/*`, `bootstrap/ci_roles.tf`), Helm NetworkPolicies, Grafana alerts.
No account ids or secrets in this file (public repo).

## IAM roles (12 Docify roles + 3 AWS-managed)

| Role | Used by | Permissions | Verdict |
| --- | --- | --- | --- |
| `docify-server` | EC2 instance (k3s pods via IMDS, D16) | ECR pull (`docify/*`), SSM read `/docify/*`, KMS decrypt **only via SSM**, SQS `docify-*-events*`, S3 backups + repo-cache, SES send (one identity), SNS publish (alerts topic), Route 53 (one zone, for DNS-01), Bedrock **Amazon models only** (Nova + Titan) | ✅ least-privilege per service; ⚠ shared by prod + staging pods (D16 accepted risk, below) |
| `docify-ci-plan` | GitHub OIDC, PRs/main | ReadOnlyAccess **+ deny** on Terraform state + SSM SecureStrings | ✅ |
| `docify-ci-infra` | GitHub OIDC, `infra` environment (required reviewer) | AdministratorAccess | ⚠ broad by design (Terraform creates IAM); gated by environment approval + immutable OIDC subject (D57). Follow-up: permission boundary |
| `docify-ci-release-staging` / `-prod` | GitHub OIDC (prod only from the `production` environment) | staging: ECR push + S3 web sync + CloudFront invalidation; prod: S3 web sync + CloudFront invalidation only (no ECR push: prod re-uses the staging-tested image) | ✅ |
| `docify-ops-power` | Start/Stop workflows, ops | EC2 start/stop/describe, SSM send-command, S3 list | ✅ (SSM send-command = shell on the server: keep it behind the workflow's environment) |
| `docify-{prod,staging}-webhook-ingest` | Lambda | SQS send to its env queue, SSM read of the webhook secret (+ KMS decrypt), its own log stream | ✅ |
| `docify-scheduler-stop-server` | EventBridge Scheduler 23:00 IST | `ec2:StopInstances` on the server | ✅ |
| `docify-budgets-action-role` | AWS Budgets 90 % action | SSM automation to stop the server | ✅ |
| `docify-dlm` | EBS snapshots | AWS managed DLM policy | ✅ |
| `AccountFullAccessRole` | org admin access (Identity Center) | AdministratorAccess | ⚠ human admin; MFA on root + Identity Center |
| EKS lab roles (7) | P12 only | — | ✅ **deleted** with the lab (`terraform destroy`, verified with `whats-running.sh`) |

## Network

- Server SG: inbound **443 from the CloudFront origin-facing prefix list only**; no SSH (SSM only); egress limited.
- App: `X-Origin-Verify` secret on `/api/*` (direct-origin requests → 403, re-verified on the EKS lab ALB).
- k3s NetworkPolicies: default-deny per namespace; IMDS only for pods that need AWS (D16); Postgres reachable only
  from `net-app` pods + labelled clients (now also the new postgres-exporter, which can reach nothing else).

## Accepted risks / follow-ups

1. **D16 — pods share the instance role.** A compromised staging pod could use prod-capable credentials.
   *Fix path proven in P12:* **EKS Pod Identity** gave every workload its own role (autoscaler, LBC, ESO, KEDA, app).
   On k3s the equivalent is an IRSA-style setup (public OIDC discovery doc in S3 + `AssumeRoleWithWebIdentity`
   per service account + the pod-identity webhook). Not done: it touches every workload on the single prod server
   for a risk that only matters after a pod compromise; it is the first item for a "real production" move (§24).
2. **`docify-ci-infra` = AdministratorAccess.** Mitigated by the required-reviewer environment + immutable OIDC
   subject. Follow-up: a permissions boundary that forbids touching `AccountFullAccessRole`, Budgets and the org.
3. **Image signing (cosign) — optional, not done.** Images are built only by `release.yml` from `main` and pulled by
   digest-pinned SHA tags from a private ECR repo; Trivy gates HIGH/CRITICAL. Signing adds value once more than one
   pipeline can push.
4. **postgres-exporter connects as the superuser** (same trust boundary as `pg-backup`). Follow-up: a `pg_monitor`
   role with its own password in SSM.
5. **Dependabot:** one moderate dev-only alert (`minimatch` via `@redocly`), not shipped to users.
