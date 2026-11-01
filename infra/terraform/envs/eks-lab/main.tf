# -----------------------------------------------------------------------------
# envs/eks-lab - Phase 12: the same Helm chart on EKS + RDS for ONE day, then
# `terraform destroy` (runbook R12, scripts/whats-running.sh must be clean).
#
# Cost (ap-south-1, on-demand prices, paid from AWS credits - D61/§1):
#   EKS control plane $0.10/h · 1-3 x t4g.medium SPOT ~$0.011/h each
#   RDS db.t4g.micro ~$0.021/h + 20 GB gp3 · ALB ~$0.0239/h + LCU
#   public IPv4 $0.005/h each (nodes + ALB) · SQS/CloudWatch ~$0
#   => roughly $0.20/h, ~$1-2 for a lab evening. NAT-free by design.
#
# Images are arm64-only (release.yml) -> Graviton nodes (AL2023 ARM).
# The lab reuses the STAGING identity (SSM /docify/staging/*, staging GitHub
# App) but has its OWN queue (docify-lab-events): sharing the staging queue
# would let lab workers drop staging jobs whose rows live in another DB.
# -----------------------------------------------------------------------------

locals {
  name      = "docify-eks-lab"
  ns        = "docify-lab"
  partition = data.aws_partition.current.partition
  account   = data.aws_caller_identity.current.account_id
  region    = data.aws_region.current.region
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ----------------------------------------------------------------- network (reuse envs/main)

data "aws_vpc" "main" {
  tags = { Name = "docify-vpc" }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  tags = { Name = "docify-public-*" }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  tags = { Name = "docify-private-*" }
}

# ALB subnet discovery tags on the shared public subnets; removed again on destroy.
resource "aws_ec2_tag" "elb" {
  for_each    = toset(data.aws_subnets.public.ids)
  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

# ----------------------------------------------------------------- EKS cluster

data "aws_iam_policy_document" "assume_eks" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${local.name}-cluster"
  assume_role_policy = data.aws_iam_policy_document.assume_eks.json
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_eks_cluster" "lab" {
  name     = local.name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = data.aws_subnets.public.ids
    endpoint_public_access  = true
    endpoint_private_access = true
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  # Standard support only - never pay the extended-support surcharge for a lab.
  upgrade_policy {
    support_type = "STANDARD"
  }

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

# ----------------------------------------------------------------- nodes (spot, public subnets, no NAT)

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${local.name}-node"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryReadOnly",
  ])
  role       = aws_iam_role.node.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/${each.value}"
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.lab.name
  node_group_name = "spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = data.aws_subnets.public.ids
  capacity_type   = "SPOT"
  ami_type        = "AL2023_ARM_64_STANDARD"
  instance_types  = var.node_instance_types
  disk_size       = 20

  scaling_config {
    min_size     = var.node_min
    desired_size = var.node_min
    max_size     = var.node_max
  }

  update_config {
    max_unavailable = 1
  }

  # Cluster Autoscaler owns desired_size after creation.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_iam_role_policy_attachment.node]
}

# ----------------------------------------------------------------- add-ons

resource "aws_eks_addon" "core" {
  for_each = {
    "vpc-cni"                = jsonencode({ enableNetworkPolicy = "true" })
    "kube-proxy"             = null
    "coredns"                = null
    "eks-pod-identity-agent" = null
    "metrics-server"         = null
  }
  cluster_name                = aws_eks_cluster.lab.name
  addon_name                  = each.key
  configuration_values        = each.value
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [aws_eks_node_group.spot]
}

# ----------------------------------------------------------------- Pod Identity roles

data "aws_iam_policy_document" "assume_pods" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "autoscaler" {
  statement {
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:GetInstanceTypesFromInstanceRequirements",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"] # describe APIs have no resource-level permissions
  }
  statement {
    actions   = ["autoscaling:SetDesiredCapacity", "autoscaling:TerminateInstanceInAutoScalingGroup"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/k8s.io/cluster-autoscaler/${local.name}"
      values   = ["owned"]
    }
  }
}

data "aws_iam_policy_document" "eso" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["arn:${local.partition}:ssm:${local.region}:${local.account}:parameter/docify/staging/*"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${local.region}.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "keda" {
  statement {
    actions   = ["sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [aws_sqs_queue.lab.arn]
  }
}

data "aws_iam_policy_document" "app" {
  statement {
    actions = [
      "sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes", "sqs:GetQueueUrl",
    ]
    resources = [aws_sqs_queue.lab.arn, aws_sqs_queue.lab_dlq.arn]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${var.repo_cache_bucket}"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:${local.partition}:s3:::${var.repo_cache_bucket}/lab/*", "arn:${local.partition}:s3:::${var.repo_cache_bucket}/repos/*"]
  }
  statement {
    sid     = "BedrockAmazonModelsOnly"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:${local.partition}:bedrock:${local.region}:${local.account}:inference-profile/apac.amazon.nova-*",
      "arn:${local.partition}:bedrock:*::foundation-model/amazon.nova-*",
      "arn:${local.partition}:bedrock:${local.region}::foundation-model/amazon.titan-embed-text-v2:0",
    ]
  }
}

locals {
  pod_roles = {
    autoscaler = { ns = "kube-system", sa = "cluster-autoscaler", policy = data.aws_iam_policy_document.autoscaler.json }
    lbc        = { ns = "kube-system", sa = "aws-load-balancer-controller", policy = file("${path.module}/lbc_iam_policy.json") }
    eso        = { ns = "external-secrets", sa = "external-secrets", policy = data.aws_iam_policy_document.eso.json }
    keda       = { ns = "keda", sa = "keda-operator", policy = data.aws_iam_policy_document.keda.json }
    app        = { ns = local.ns, sa = "docify", policy = data.aws_iam_policy_document.app.json }
  }
}

resource "aws_iam_role" "pod" {
  for_each           = local.pod_roles
  name               = "${local.name}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.assume_pods.json
}

resource "aws_iam_role_policy" "pod" {
  for_each = local.pod_roles
  name     = each.key
  role     = aws_iam_role.pod[each.key].id
  policy   = each.value.policy
}

resource "aws_eks_pod_identity_association" "pod" {
  for_each        = local.pod_roles
  cluster_name    = aws_eks_cluster.lab.name
  namespace       = each.value.ns
  service_account = each.value.sa
  role_arn        = aws_iam_role.pod[each.key].arn
}

# ----------------------------------------------------------------- queue (lab-only)

resource "aws_sqs_queue" "lab_dlq" {
  name                      = "docify-lab-events-dlq"
  message_retention_seconds = 86400
}

resource "aws_sqs_queue" "lab" {
  name                       = "docify-lab-events"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.lab_dlq.arn
    maxReceiveCount     = 5
  })
}

# ----------------------------------------------------------------- RDS PostgreSQL 17 + pgvector

# Same user/db/password as staging (docify_staging) so the chart's ExternalSecret works unchanged.
data "aws_ssm_parameter" "db_password" {
  name = "/docify/staging/db/password"
}

data "aws_rds_engine_version" "pg" {
  engine       = "postgres"
  version      = "17"
  latest       = true
  default_only = false
}

resource "aws_db_subnet_group" "lab" {
  name       = local.name
  subnet_ids = data.aws_subnets.private.ids
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Postgres from the VPC (EKS pods use VPC IPs)"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description = "Postgres from the VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }
}

resource "aws_db_instance" "lab" {
  identifier                 = local.name
  engine                     = "postgres"
  engine_version             = data.aws_rds_engine_version.pg.version
  instance_class             = var.rds_instance_class
  allocated_storage          = 20
  storage_type               = "gp3"
  db_name                    = "docify_staging"
  username                   = "docify_staging"
  password                   = data.aws_ssm_parameter.db_password.value
  db_subnet_group_name       = aws_db_subnet_group.lab.name
  vpc_security_group_ids     = [aws_security_group.rds.id]
  publicly_accessible        = false
  multi_az                   = false
  backup_retention_period    = 0
  skip_final_snapshot        = true
  deletion_protection        = false
  apply_immediately          = true
  auto_minor_version_upgrade = false
  storage_encrypted          = true
}

# ----------------------------------------------------------------- outputs

output "cluster_name" {
  description = "EKS cluster (aws eks update-kubeconfig --name ...)."
  value       = aws_eks_cluster.lab.name
}

output "rds_endpoint" {
  description = "RDS host for deploy/values/eks-lab.yaml (passed with --set, not committed)."
  value       = aws_db_instance.lab.address
}

output "queue_url" {
  description = "Lab queue (passed with --set config.SQS_QUEUE_URL)."
  value       = aws_sqs_queue.lab.url
}

output "dlq_url" {
  description = "Lab DLQ."
  value       = aws_sqs_queue.lab_dlq.url
}
