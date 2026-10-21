# -----------------------------------------------------------------------------
# Module: storage
#
# All S3 buckets except the Terraform state bucket (that one lives in
# bootstrap/). Master Doc §12.6.
#
#   docify-web-<env>-<acct>     SPA files per env; private, read only by
#                               CloudFront via OAC (policy is in module edge
#                               because it needs the distribution ARN)
#   docify-artifacts-<acct>     frontend/<sha>.tar.gz build artifacts (30 d)
#   docify-backups-<acct>       Postgres dumps; NO versioning, 14 d expiry,
#                               prevent_destroy (survives "Off mode", R10)
#   docify-repo-cache-<acct>    downloaded repo tarballs (7 d)
#
# Every bucket: Block Public Access (all 4 flags), SSE-S3 encryption, object
# ownership "BucketOwnerEnforced" (ACLs disabled). Names end with the account
# id because S3 bucket names are global across all AWS customers.
# -----------------------------------------------------------------------------

locals {
  web_buckets = { for env in var.envs : env => "${var.name}-web-${env}-${var.account_id}" }
}

# --- buckets -----------------------------------------------------------------

resource "aws_s3_bucket" "web" {
  for_each = local.web_buckets

  bucket = each.value
  # Contents are rebuilt from artifacts on every deploy -> safe to empty on destroy.
  force_destroy = true

  tags = { Env = each.key }
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.name}-artifacts-${var.account_id}"
  force_destroy = true # re-creatable build outputs
}

resource "aws_s3_bucket" "repo_cache" {
  bucket        = "${var.name}-repo-cache-${var.account_id}"
  force_destroy = true # pure cache
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.name}-backups-${var.account_id}"

  # Backups must survive `terraform destroy` (Off mode, R10). To really delete
  # this bucket you must first remove this guard on purpose.
  lifecycle {
    prevent_destroy = true
  }
}

locals {
  # Every bucket id, keyed by a stable logical name, for the shared settings below.
  all_buckets = merge(
    { for env, b in aws_s3_bucket.web : "web-${env}" => b.id },
    {
      artifacts  = aws_s3_bucket.artifacts.id
      repo-cache = aws_s3_bucket.repo_cache.id
      backups    = aws_s3_bucket.backups.id
    },
  )
}

# --- settings shared by every bucket -------------------------------------------

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.all_buckets

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = local.all_buckets

  bucket = each.value
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.all_buckets

  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3: free, no KMS key to manage
    }
  }
}

# --- lifecycle rules -----------------------------------------------------------

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-frontend-artifacts"
    status = "Enabled"
    filter {
      prefix = "frontend/"
    }
    expiration {
      days = var.artifacts_expire_days # rollback window for the frontend (§14.3)
    }
  }

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-backups"
    status = "Enabled"
    filter {}
    expiration {
      days = var.backups_expire_days # purged data leaves backups within 14 d (§17.3)
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "repo_cache" {
  bucket = aws_s3_bucket.repo_cache.id

  rule {
    id     = "expire-repo-cache"
    status = "Enabled"
    filter {}
    expiration {
      days = var.repo_cache_expire_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# --- bucket policies: deny any non-TLS request ---------------------------------
# (web buckets get their policy in module edge, together with the OAC grant)

data "aws_iam_policy_document" "deny_insecure_transport" {
  for_each = {
    artifacts  = aws_s3_bucket.artifacts.arn
    repo-cache = aws_s3_bucket.repo_cache.arn
    backups    = aws_s3_bucket.backups.arn
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [each.value, "${each.value}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.deny_insecure_transport["artifacts"].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}

resource "aws_s3_bucket_policy" "repo_cache" {
  bucket = aws_s3_bucket.repo_cache.id
  policy = data.aws_iam_policy_document.deny_insecure_transport["repo-cache"].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}

resource "aws_s3_bucket_policy" "backups" {
  bucket = aws_s3_bucket.backups.id
  policy = data.aws_iam_policy_document.deny_insecure_transport["backups"].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}
