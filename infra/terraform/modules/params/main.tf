# -----------------------------------------------------------------------------
# Module: params
#
# SSM Parameter Store SecureStrings from Master Doc §15.2 (D15).
#
# How secrets stay OUT of Terraform state:
#   Terraform only creates each parameter with a dummy value through the
#   WRITE-ONLY argument `value_wo` (Terraform >= 1.11, AWS provider >= 6).
#   Write-only values are sent to AWS but never stored in state or plan.
#   The real values are then written by `scripts/init-params.sh` (R6) with
#   `aws ssm put-parameter --overwrite`. Terraform never reads them back.
#   Bump `placeholder_version` only if you WANT Terraform to reset every value
#   to the placeholder again (you almost never do).
#
# Exception - origin verify header: CloudFront must know this value at apply
# time (it sends it as the X-Origin-Verify header), so it is generated here by
# random_password and therefore IS in state. Accepted (§15.2 note): it is only
# defence-in-depth behind the CloudFront-only security group.
# -----------------------------------------------------------------------------

locals {
  # Per-environment secrets: /docify/<env>/<path>
  env_param_paths = [
    "db/password",
    "app/session_pepper",
    "github/app_private_key",
    "github/client_secret",
    "github/webhook_secret", # read by the webhook-ingest Lambda at runtime
    "google/client_secret",
    "ai/anthropic_api_key",
    "ai/voyage_api_key",
  ]

  # Shared between environments: /docify/shared/<path>
  shared_param_paths = [
    "postgres/superuser_password",
    "grafana/admin_password",
  ]

  placeholder_params = merge(
    { for pair in setproduct(var.envs, local.env_param_paths) :
      "/${var.name}/${pair[0]}/${pair[1]}" => pair[0]
    },
    { for p in local.shared_param_paths : "/${var.name}/shared/${p}" => "shared" },
  )
}

resource "aws_ssm_parameter" "placeholder" {
  for_each = local.placeholder_params

  name        = each.key
  description = "Docify secret. Real value set by scripts/init-params.sh, never by Terraform."
  type        = "SecureString" # encrypted with the AWS-managed key alias/aws/ssm (free)

  value_wo         = var.placeholder_value
  value_wo_version = var.placeholder_version

  tags = { Env = each.value }
}

# --- origin verify header (value known to Terraform on purpose) ---------------

resource "random_password" "origin_verify" {
  for_each = toset(var.envs)

  length  = 48
  special = false # header-safe characters only
}

resource "aws_ssm_parameter" "origin_verify" {
  for_each = toset(var.envs)

  name        = "/${var.name}/${each.key}/app/origin_verify_header"
  description = "Secret header CloudFront adds to /api/* origin requests (X-Origin-Verify). Managed by Terraform."
  type        = "SecureString"

  # Still written via value_wo so the value appears in state only once (in
  # random_password), not twice. Rotate: `terraform apply -replace=...random_password...`
  # and bump the version below.
  value_wo         = random_password.origin_verify[each.key].result
  value_wo_version = var.origin_verify_version

  tags = { Env = each.key }
}
