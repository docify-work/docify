# -----------------------------------------------------------------------------
# Module: server
#
# The single EC2 instance running k3s for staging + prod (D01), Master Doc §12.4.
#
#   AMI        Ubuntu 24.04 LTS, looked up from Canonical's public SSM
#              parameter (always the current image). ignore_changes = [ami]
#              so a new AMI release never replaces the running server.
#   IMDSv2     required, hop limit 2 (pods are one network hop further away
#              than the host and use the instance role, D16).
#   root EBS   30 GB gp3 encrypted (OS, k3s, images, swap); disposable.
#   data EBS   10 GB gp3 encrypted, SEPARATE volume mounted at /data
#              (Postgres, Prometheus, Loki). Survives instance replacement,
#              prevent_destroy, snapshotted daily by DLM (keep 7).
#   user_data  infra/server/bootstrap.sh rendered with templatefile(); runs
#              once on first boot. ignore_changes = [user_data] so editing the
#              script doesn't silently replace the server - rebuild on purpose
#              with: terraform apply -replace=module.server.aws_instance.this
#   No SSH key, no port 22: admin access is SSM Session Manager only.
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  partition  = data.aws_partition.current.partition

  # Graviton families have a "g" right after the generation number
  # (t4g, m7g, c7gn, r8g ...). Everything else here is x86_64.
  architecture = can(regex("^[a-z]+[0-9]+g", var.instance_type)) ? "arm64" : "amd64"

  # t2/t3/t3a/t4g are burstable: only they accept credit_specification.
  is_burstable = can(regex("^t[0-9]", var.instance_type))

  origin_fqdns = [for h in var.origin_hostnames : "${h}.${var.domain}"]
  # Names cert-manager writes for DNS-01 challenges (§13.5).
  acme_fqdns = [for f in local.origin_fqdns : "_acme-challenge.${f}"]
}

# Canonical publishes the current Ubuntu AMI id as a public SSM parameter.
data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/${local.architecture}/hvm/ebs-gp3/ami-id"
}

# =============================================================================
# IAM: instance role (Master Doc §12.7, first row)
# =============================================================================

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name}-server"
  description        = "k3s server instance role (shared by allowed pods via IMDS, D16)"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

# SSM agent: Session Manager (shell, port-forward 6443) + Run Command (stop.yml).
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "instance" {
  # --- ECR pull (kubelet ecr-credential-provider) ---
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this API has no resource-level permissions
  }
  statement {
    sid = "EcrPullDocify"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = ["arn:${local.partition}:ecr:${local.region}:${local.account_id}:repository/${var.name}/*"]
  }

  # --- SSM parameters (External Secrets Operator) ---
  statement {
    sid = "ReadDocifyParams"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = ["arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/${var.name}/*"]
  }
  statement {
    sid       = "DecryptViaSsmOnly"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${local.region}.amazonaws.com"]
    }
  }

  # --- SQS (api/worker + KEDA scaler) ---
  statement {
    sid = "DocifyQueues"
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]
    resources = ["arn:${local.partition}:sqs:${local.region}:${local.account_id}:${var.name}-*-events*"]
  }

  # --- S3: backups (pg-backup pods) + repo cache (worker) ---
  statement {
    sid       = "ListDataBuckets"
    actions   = ["s3:ListBucket"]
    resources = [var.backups_bucket_arn, var.repo_cache_bucket_arn]
  }
  statement {
    sid       = "ReadWriteDataBuckets"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.backups_bucket_arn}/*", "${var.repo_cache_bucket_arn}/*"]
  }

  # --- SES (transactional email) ---
  statement {
    sid       = "SendEmailFromDomain"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = [var.ses_identity_arn]
  }

  # --- SNS (Grafana alert contact point, D35) ---
  statement {
    sid       = "PublishAlerts"
    actions   = ["sns:Publish"]
    resources = [var.alerts_topic_arn]
  }

  # --- Route 53: boot-time DNS (D26) + cert-manager DNS-01 (D08) ---
  # Only these 4 names, only UPSERT/DELETE. A compromised pod can't hijack
  # the apex, www or the SES records.
  statement {
    sid       = "ChangeOnlyOriginRecords"
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = [var.zone_arn]
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "route53:ChangeResourceRecordSetsNormalizedRecordNames"
      values   = concat(local.origin_fqdns, local.acme_fqdns) # lowercase, no trailing dot
    }
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "route53:ChangeResourceRecordSetsActions"
      values   = ["UPSERT", "DELETE"]
    }
  }
  statement {
    sid       = "ReadZone"
    actions   = ["route53:ListResourceRecordSets"]
    resources = [var.zone_arn]
  }
  statement {
    sid       = "WatchChanges"
    actions   = ["route53:GetChange"]
    resources = ["arn:${local.partition}:route53:::change/*"]
  }
}

resource "aws_iam_role_policy" "instance" {
  name   = "docify-server"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance.json
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.name}-server"
  role = aws_iam_role.instance.name
}

# =============================================================================
# Data volume (created BEFORE the instance so its id can go into user_data)
# =============================================================================

resource "aws_ebs_volume" "data" {
  availability_zone = var.availability_zone # must match the instance's AZ
  size              = var.data_volume_size
  type              = "gp3"
  encrypted         = true

  tags = {
    Name     = "${var.name}-data"
    Snapshot = "${var.name}-data" # DLM selects volumes by this tag
  }

  # Holds the database. Never let Terraform delete it by accident.
  lifecycle {
    prevent_destroy = true
  }
}

# =============================================================================
# Instance
# =============================================================================

resource "aws_instance" "this" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.insecure_value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = aws_iam_instance_profile.this.name
  associate_public_ip_address = true  # no EIP: IP changes each start, DNS self-updates (D26)
  monitoring                  = false # detailed monitoring costs extra

  user_data = templatefile("${path.module}/../../../server/bootstrap.sh", {
    region                         = local.region
    account_id                     = local.account_id
    domain                         = var.domain
    hosted_zone_id                 = var.zone_id
    origin_fqdns                   = join(" ", local.origin_fqdns)
    data_volume_id                 = aws_ebs_volume.data.id
    architecture                   = local.architecture
    k3s_version                    = var.k3s_version
    ecr_credential_provider_ver    = var.ecr_credential_provider_version
    ecr_credential_provider_sha256 = var.ecr_credential_provider_sha256[local.architecture]
    helm_version                   = var.helm_version
    helm_sha256                    = var.helm_sha256[local.architecture]
    argocd_chart_version           = var.argocd_chart_version
    git_repo_url                   = var.git_repo_url
    git_revision                   = var.git_revision
    root_app_path                  = var.root_app_path
    root_values_files              = join(" ", var.root_values_files)
    argocd_values_path             = var.argocd_values_path
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # pods sit one hop behind the node
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
    tags                  = { Name = "${var.name}-root" }
  }

  # Burstable types only: "unlimited" lets short load tests burst past the
  # baseline (small extra charge only if the average exceeds baseline).
  dynamic "credit_specification" {
    for_each = local.is_burstable ? [1] : []
    content {
      cpu_credits = var.cpu_credits
    }
  }

  tags = { Name = "${var.name}-server" }

  lifecycle {
    ignore_changes = [ami, user_data]
  }

  # The boot script needs the role's permissions (Route 53, ECR) immediately.
  depends_on = [aws_iam_role_policy.instance, aws_iam_role_policy_attachment.ssm_core]
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/sdf" # appears as /dev/nvme1n1 on Nitro; the script uses /dev/disk/by-id
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.this.id

  # On rebuild, stop the old instance first so /data is unmounted cleanly.
  stop_instance_before_detaching = true
}

# =============================================================================
# DLM: daily snapshot of the data volume, keep 7 (§18.1)
# =============================================================================

data "aws_iam_policy_document" "assume_dlm" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm" {
  name               = "${var.name}-dlm"
  assume_role_policy = data.aws_iam_policy_document.assume_dlm.json
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "data" {
  description        = "Docify data volume daily snapshot keep 7"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Snapshot = "${var.name}-data" }

    schedule {
      name      = "daily-keep-7"
      copy_tags = true

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = [var.snapshot_time_utc]
      }

      retain_rule {
        count = var.snapshot_retain_count
      }

      tags_to_add = { SnapshotCreator = "dlm" }
    }
  }
}
