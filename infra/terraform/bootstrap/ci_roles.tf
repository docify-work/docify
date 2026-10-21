# -----------------------------------------------------------------------------
# GitHub Actions -> AWS without any stored keys (OIDC). Master Doc §12.7.
#
# How it works: each workflow job asks GitHub for a short-lived signed token
# (needs `permissions: id-token: write`). AWS STS checks the signature against
# the OIDC provider below and the role's trust policy, then hands back ~1 h
# credentials. The trust policy pins:
#   aud = sts.amazonaws.com              (token minted for AWS)
#   sub = repo:<owner>/<repo>:<context>  (EXACT match, no wildcards)
# The `sub` context decides which workflow jobs can use which role:
#   pull_request              -> docify-ci-plan            (read-only plan)
#   environment:infra         -> docify-ci-infra           (apply, approval gate)
#   ref:refs/heads/main       -> docify-ci-release-staging (release.yml)
#   environment:production    -> docify-ci-release-prod    (promote.yml, approval gate D33)
#   ref:refs/heads/main       -> docify-ops-power          (start/stop/eval)
# NOTE: a job that declares `environment:` gets an environment sub, NOT a ref
# sub - so main-branch roles must be used by jobs WITHOUT an environment.
#
# Resources that envs/main creates later (instance, distributions) are matched
# by TAG here, so bootstrap never needs their ids.
# -----------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # thumbprint_list omitted: AWS validates GitHub's certificate via its own
  # trusted CA library; the provider fills in a value if the API wants one.
}

locals {
  repo_sub_prefix = "repo:${var.github_owner}/${var.github_repo}"

  ci_roles = {
    "docify-ci-plan"            = "${local.repo_sub_prefix}:pull_request"
    "docify-ci-infra"           = "${local.repo_sub_prefix}:environment:infra"
    "docify-ci-release-staging" = "${local.repo_sub_prefix}:ref:refs/heads/main"
    "docify-ci-release-prod"    = "${local.repo_sub_prefix}:environment:production"
    "docify-ops-power"          = "${local.repo_sub_prefix}:ref:refs/heads/main"
  }

  partition    = "aws"
  web_bucket   = { for env in ["staging", "prod"] : env => "arn:${local.partition}:s3:::docify-web-${env}-${local.account_id}" }
  artifacts    = "arn:${local.partition}:s3:::docify-artifacts-${local.account_id}"
  backups      = "arn:${local.partition}:s3:::docify-backups-${local.account_id}"
  ecr_backend  = "arn:${local.partition}:ecr:${var.region}:${local.account_id}:repository/docify/backend"
  instance_arn = "arn:${local.partition}:ec2:${var.region}:${local.account_id}:instance/*"
}

data "aws_iam_policy_document" "trust" {
  for_each = local.ci_roles

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [each.value]
    }
  }
}

resource "aws_iam_role" "ci" {
  for_each = local.ci_roles

  name                 = each.key
  description          = "GitHub Actions OIDC role (sub = ${each.value})"
  assume_role_policy   = data.aws_iam_policy_document.trust[each.key].json
  max_session_duration = 3600
}

# =============================================================================
# docify-ci-plan: read-only + state lock, but NOT the secrets
# =============================================================================

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.ci["docify-ci-plan"].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "plan" {
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }
  # use_lockfile: plan writes + deletes "<key>.tflock" while it runs.
  statement {
    sid       = "StateLockFile"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/*.tflock"]
  }
  # ReadOnlyAccess includes ssm:GetParameter* - which would let any PR read
  # the SecureStrings. An explicit Deny always wins over an Allow.
  statement {
    sid    = "DenyDocifySecrets"
    effect = "Deny"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
      "ssm:GetParameterHistory",
    ]
    resources = ["arn:${local.partition}:ssm:${var.region}:${local.account_id}:parameter/docify/*"]
  }
}

resource "aws_iam_role_policy" "plan" {
  name   = "state-and-secret-deny"
  role   = aws_iam_role.ci["docify-ci-plan"].id
  policy = data.aws_iam_policy_document.plan.json
}

# =============================================================================
# docify-ci-infra: admin (accepted for learning, §12.7). Protected by the
# GitHub Environment "infra" (required reviewer) because of the sub above.
# =============================================================================

resource "aws_iam_role_policy_attachment" "infra_admin" {
  role       = aws_iam_role.ci["docify-ci-infra"].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AdministratorAccess"
}

# =============================================================================
# Release roles (staging + prod) - built from one template
# =============================================================================

data "aws_iam_policy_document" "release" {
  for_each = toset(["staging", "prod"])

  # ECR push only exists for staging: images are built once and promoted.
  dynamic "statement" {
    for_each = each.key == "staging" ? [1] : []
    content {
      sid       = "EcrAuth"
      actions   = ["ecr:GetAuthorizationToken"]
      resources = ["*"]
    }
  }
  dynamic "statement" {
    for_each = each.key == "staging" ? [1] : []
    content {
      sid = "EcrPushBackend"
      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart",
      ]
      resources = [local.ecr_backend]
    }
  }

  # Frontend artifacts: staging uploads them, prod only downloads them.
  statement {
    sid       = "FrontendArtifacts"
    actions   = each.key == "staging" ? ["s3:GetObject", "s3:PutObject"] : ["s3:GetObject"]
    resources = ["${local.artifacts}/frontend/*"]
  }

  # `aws s3 sync --delete` into this env's web bucket only.
  statement {
    sid       = "WebBucketList"
    actions   = ["s3:ListBucket"]
    resources = [local.web_bucket[each.key]]
  }
  statement {
    sid       = "WebBucketWrite"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.web_bucket[each.key]}/*"]
  }

  # Invalidate only the distribution tagged Env=<env>.
  # ⚠ verify (P8): CloudFront distributions support aws:ResourceTag conditions
  # for CreateInvalidation. If not, replace with the distribution ARN from
  # envs/main outputs.
  statement {
    sid       = "InvalidateOwnDistribution"
    actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
    resources = ["arn:${local.partition}:cloudfront::${local.account_id}:distribution/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Env"
      values   = [each.key]
    }
  }

  # "Is the server awake?" check before smoke tests.
  statement {
    sid       = "DescribeInstances"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"] # Describe* has no resource-level permissions
  }
}

resource "aws_iam_role_policy" "release" {
  for_each = toset(["staging", "prod"])

  name   = "release-${each.key}"
  role   = aws_iam_role.ci["docify-ci-release-${each.key}"].id
  policy = data.aws_iam_policy_document.release[each.key].json
}

# =============================================================================
# docify-ops-power: start/stop the server + run commands on it via SSM
# =============================================================================

data "aws_iam_policy_document" "ops_power" {
  statement {
    sid       = "StartStopServer"
    actions   = ["ec2:StartInstances", "ec2:StopInstances"]
    resources = [local.instance_arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Name"
      values   = [var.server_name_tag]
    }
  }

  statement {
    sid       = "DescribeInstances"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  # SendCommand needs permission on BOTH the target instance and the document.
  statement {
    sid       = "RunShellOnServer"
    actions   = ["ssm:SendCommand"]
    resources = [local.instance_arn]
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/Name"
      values   = [var.server_name_tag]
    }
  }
  statement {
    sid       = "RunShellDocument"
    actions   = ["ssm:SendCommand"]
    resources = ["arn:${local.partition}:ssm:${var.region}::document/AWS-RunShellScript"]
  }

  statement {
    sid       = "ReadCommandResults"
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
    resources = ["*"] # no resource-level permissions for these
  }

  # start.yml warns if the newest Postgres dump is older than the last stop
  # (§16.4 "Backup missing"). List only - cannot read the dumps.
  statement {
    sid       = "ListBackups"
    actions   = ["s3:ListBucket"]
    resources = [local.backups]
  }
}

resource "aws_iam_role_policy" "ops_power" {
  name   = "ops-power"
  role   = aws_iam_role.ci["docify-ops-power"].id
  policy = data.aws_iam_policy_document.ops_power.json
}
