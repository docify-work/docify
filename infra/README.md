# infra/ — AWS infrastructure (Terraform) + server bootstrap

Spec: [`docs/Docify_Master_Doc.md`](../docs/Docify_Master_Doc.md) §12 (AWS), §14 (CI/CD), §19 (cost), §22 (runbooks).

> **Status:** written and statically validated only (`terraform validate`, tflint,
> actionlint, shellcheck). **Nothing has been applied** — the AWS account is blocked
> by an org SCP (Q11).

## Layout

```text
infra/
├── server/bootstrap.sh            cloud-init for the k3s server (Terraform templatefile)
└── terraform/
    ├── .tflint.hcl                shared TFLint config (terraform + aws rulesets)
    ├── bootstrap/                 LOCAL state, run once by the admin:
    │                                state bucket, GitHub OIDC provider, 5 CI roles,
    │                                budgets $5/$15/$30 + Cost Anomaly Detection
    ├── modules/
    │   ├── network     VPC 10.20.0.0/16, 2 public + 2 private subnets, no NAT,
    │   │               S3 gateway endpoint, SG: 443 from CloudFront only
    │   ├── server      EC2 (Ubuntu 24.04, IMDSv2), data EBS /data, instance role, DLM
    │   ├── storage     web (per env), artifacts, backups, repo-cache buckets
    │   ├── registry    ECR docify/backend
    │   ├── queues      docify-<env>-events + DLQ
    │   ├── ingest      webhook Lambda + Function URL (per env)
    │   ├── params      SSM SecureStrings (write-only placeholders)
    │   ├── ses         domain identity, DKIM, MAIL FROM, DMARC
    │   ├── dns         Route 53 zone + records, ACM cert (us-east-1)
    │   ├── edge        CloudFront distribution per env (+ functions/spa-rewrite.js)
    │   ├── scheduler   nightly auto-stop 23:00 IST
    │   └── alerts      SNS docify-alerts
    └── envs/
        ├── main/                  staging + prod on one server (remote state)
        └── eks-lab/               Phase 12 skeleton (creates nothing yet)
```

## Order of operations (Phase 8)

Prerequisites: Q11 resolved, `aws login` works as the admin user, Terraform ≥ 1.11,
P0 manual items done (budgets, hosted zone, SES identity).

1. **bootstrap (local state, admin laptop)**
   ```bash
   cd infra/terraform/bootstrap
   cp terraform.tfvars.example terraform.tfvars      # budget_email
   # uncomment + fill imports.tf for the P0 budgets / anomaly monitor
   terraform init && terraform plan && terraform apply
   ```
   Keep `terraform.tfstate` safe (it is git-ignored) — e.g. copy it to
   `s3://docify-tfstate-<acct>/bootstrap/terraform.tfstate`.
2. **GitHub settings** (repo → Settings): see the table below.
3. **Secrets into SSM:** after the first `envs/main` apply created the parameters,
   run `scripts/init-params.sh` (prompts, never echoes; `--generate` for random ones).
4. **envs/main** — normally via CI (`terraform.yml` on push to `main`, approval in the
   `infra` environment). First time / by hand:
   ```bash
   cd infra/terraform/envs/main
   cp backend.hcl.example backend.hcl                # bucket name (keep it out of Git)
   cp terraform.tfvars.example terraform.tfvars
   # uncomment + fill imports.tf (hosted zone + SES from P0)
   terraform init -backend-config=backend.hcl
   terraform plan
   terraform apply
   terraform output                                   # ids for the repo variables below
   ```
5. Point the registrar at `terraform output name_servers` (if the zone is new), put
   `webhook_urls` into the staging/prod GitHub Apps, set the repo variables, then
   `AWS_ENABLED=true`.

Check after apply (§23 P8 AC): `terraform state pull | grep -c CHANGE_ME` → `0`
(write-only values never reach state).

## GitHub settings the workflows need

| Kind | Name | Value / purpose |
| --- | --- | --- |
| variable | `AWS_ENABLED` | `true` to switch on every AWS workflow (until then they are skipped, not failed) |
| variable | `AWS_ACCOUNT_ID` | 12-digit account id → role ARNs `arn:aws:iam::<id>:role/docify-*` |
| variable | `DOMAIN` | optional, default `docify.work` |
| variable | `INSTANCE_TYPE` | optional, default `m7i-flex.large` (terraform.yml) |
| variable | `CF_DISTRIBUTION_ID_STAGING` / `CF_DISTRIBUTION_ID_PROD` | from `terraform output distribution_ids` (cache invalidation) |
| secret | `ALERT_EMAIL` | SNS alert email (TF_VAR_alert_email) |
| secret | `CI_BOT_APP_ID` | docify-ci-bot GitHub App **Client ID** (App ID also works) |
| secret | `CI_BOT_PRIVATE_KEY` | docify-ci-bot private key (PEM) |
| environment | `infra` | required reviewer → gates `terraform.yml` (role `docify-ci-infra`) |
| environment | `production` | required reviewer → gates `promote.yml` (role `docify-ci-release-prod`) |

OIDC trust subjects (exact match, `aud = sts.amazonaws.com`):

| Role | `sub` | Used by |
| --- | --- | --- |
| `docify-ci-plan` | `repo:docify-work/docify:pull_request` | PR plan in `ci.yml` (read-only, SSM secrets denied) |
| `docify-ci-infra` | `repo:docify-work/docify:environment:infra` | `terraform.yml` |
| `docify-ci-release-staging` | `repo:docify-work/docify:ref:refs/heads/main` | `release.yml` (jobs have **no** `environment:`) |
| `docify-ci-release-prod` | `repo:docify-work/docify:environment:production` | `promote.yml` |
| `docify-ops-power` | `repo:docify-work/docify:ref:refs/heads/main` | `start.yml`, `stop.yml`, `eval.yml` |

## Day-to-day

| Task | How |
| --- | --- |
| Start / stop | Actions → **start** / **stop** (stop takes a pre-stop Postgres backup first); auto-stop 23:00 IST |
| Shell on the server | `aws ssm start-session --target <instance-id>` (no SSH, no port 22) |
| Bootstrap log | `/var/log/docify-bootstrap.log`, marker `/etc/docify/bootstrap.done` |
| Rebuild server (R11) | `terraform apply -replace=module.server.aws_instance.this` — `/data` re-attaches |
| What costs money? | `scripts/whats-running.sh` (all regions) |
| Rotate a secret (R6) | `scripts/init-params.sh --env <env> --only <path>` → force-sync ExternalSecret |

## Cost notes (§19)

- **Asleep ≈ $5/month:** 40 GB EBS (30 root + 10 data) + 7 daily data snapshots +
  Route 53 zone ($0.50) + S3/ECR. CloudFront, Lambda, SQS, SNS, Scheduler ≈ free at our traffic.
- **Awake** adds ≈ $0.10/h (`m7i-flex.large` + public IPv4).
- Deliberately absent: NAT gateway (~$33/mo), ALB, RDS, EKS, Elastic IP, CloudFront logs,
  detailed monitoring, KMS customer keys.
- Budgets $5/$15/$30 (actual + forecast) and Cost Anomaly Detection email the owner.

## Destroy / "Off mode" (R10)

Protected on purpose (`prevent_destroy`): the **state bucket** (bootstrap), the
**backups bucket**, the **ECR repository** and the **data EBS volume**.
A plain `terraform destroy` therefore stops with an error — that is the safety net.

1. Run **stop** (takes the pre-stop backup to S3).
2. Destroy everything except the protected resources, e.g.
   ```bash
   cd infra/terraform/envs/main
   terraform destroy -target=module.scheduler -target=module.edge -target=module.ingest \
     -target=module.queues -target=module.server.aws_instance.this \
     -target=module.server.aws_volume_attachment.data
   ```
   (Only if you really want the database volume gone too: remove its
   `prevent_destroy`, destroy, restore later from the S3 dump with R7.)
   Keep the Route 53 zone unless the domain goes away too — a new zone gets new
   name servers that must be re-entered at the registrar.
3. `scripts/whats-running.sh` → must be clean.
4. Coming back: `terraform apply` + R7 (restore the latest dump).

## Validate locally (what CI's infra job runs)

```bash
cd infra/terraform
terraform fmt -recursive -check
for d in bootstrap envs/main envs/eks-lab; do (cd $d && terraform init -backend=false && terraform validate); done
tflint --init --config "$PWD/.tflint.hcl" && tflint --recursive --config "$PWD/.tflint.hcl"
```

The server script is a Terraform template: shell variables that need braces are
written with a doubled dollar sign. Check it with `bash -n infra/server/bootstrap.sh`
(and ideally on the rendered output).
