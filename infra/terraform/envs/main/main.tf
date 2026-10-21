# -----------------------------------------------------------------------------
# envs/main - staging + prod on ONE k3s server (D01). Master Doc §12.
#
# Shared:   network, server (+ data volume, DLM), storage buckets, ECR,
#           SSM params, SES, Route 53 + ACM, alerts topic, auto-stop schedule
# Per env:  SQS queue + DLQ, webhook Lambda, CloudFront distribution
#
# Apply order is worked out by Terraform from the references below:
#   dns (zone, cert) -> edge (CloudFront) -> dns alias records
#   storage/ses/alerts/dns -> server (role is scoped to them) -> scheduler
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  git_repo_url = "https://github.com/${var.github_repository}.git"

  # Per-env hostnames (§4.3)
  hosts = {
    prod = {
      aliases = [var.domain, "www.${var.domain}"]
      origin  = "origin.${var.domain}"
    }
    staging = {
      aliases = ["staging.${var.domain}"]
      origin  = "origin-staging.${var.domain}"
    }
  }
}

# =============================================================================
# Shared foundation
# =============================================================================

module "network" {
  source = "../../modules/network"
}

module "storage" {
  source     = "../../modules/storage"
  account_id = local.account_id
  envs       = var.envs
}

module "registry" {
  source = "../../modules/registry"
}

module "params" {
  source = "../../modules/params"
  envs   = var.envs
}

module "alerts" {
  source      = "../../modules/alerts"
  alert_email = var.alert_email
}

module "dns" {
  source = "../../modules/dns"
  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  domain = var.domain
  distributions = {
    for env, e in module.edge : env => {
      domain_name    = e.domain_name
      hosted_zone_id = e.hosted_zone_id
    }
  }
}

module "ses" {
  source          = "../../modules/ses"
  domain          = var.domain
  zone_id         = module.dns.zone_id
  dmarc_rua_email = var.dmarc_rua_email
}

# =============================================================================
# Per environment
# =============================================================================

module "queues" {
  source   = "../../modules/queues"
  for_each = toset(var.envs)

  env = each.key
}

module "ingest" {
  source   = "../../modules/ingest"
  for_each = toset(var.envs)

  env                       = each.key
  source_dir                = "${path.root}/../../../../lambdas/webhook_ingest"
  build_dir                 = "${path.root}/.terraform/build" # inside the git-ignored .terraform/
  queue_url                 = module.queues[each.key].queue_url
  queue_arn                 = module.queues[each.key].queue_arn
  webhook_secret_param_name = module.params.webhook_secret_params[each.key].name
  webhook_secret_param_arn  = module.params.webhook_secret_params[each.key].arn
  reserved_concurrency      = var.lambda_reserved_concurrency
}

module "edge" {
  source   = "../../modules/edge"
  for_each = toset(var.envs)

  env                 = each.key
  aliases             = local.hosts[each.key].aliases
  origin_domain       = local.hosts[each.key].origin
  web_bucket          = module.storage.web_buckets[each.key]
  certificate_arn     = module.dns.certificate_arn
  origin_verify_value = module.params.origin_verify_values[each.key]
}

# =============================================================================
# Server + its nightly stop
# =============================================================================

module "server" {
  source = "../../modules/server"

  instance_type      = var.instance_type
  subnet_id          = module.network.public_subnet_ids[0]
  availability_zone  = module.network.public_subnet_azs[0]
  security_group_ids = [module.network.server_security_group_id]

  domain                = var.domain
  zone_id               = module.dns.zone_id
  zone_arn              = module.dns.zone_arn
  backups_bucket_arn    = module.storage.backups_bucket.arn
  repo_cache_bucket_arn = module.storage.repo_cache_bucket.arn
  ses_identity_arn      = module.ses.identity_arn
  alerts_topic_arn      = module.alerts.topic_arn

  k3s_version                     = var.k3s_version
  ecr_credential_provider_version = var.ecr_credential_provider_version
  ecr_credential_provider_sha256  = var.ecr_credential_provider_sha256
  helm_version                    = var.helm_version
  helm_sha256                     = var.helm_sha256
  argocd_chart_version            = var.argocd_chart_version
  git_repo_url                    = local.git_repo_url
  git_revision                    = var.git_revision
  root_values_files               = var.root_values_files
}

module "scheduler" {
  source = "../../modules/scheduler"

  instance_id  = module.server.instance_id
  instance_arn = module.server.instance_arn
}
