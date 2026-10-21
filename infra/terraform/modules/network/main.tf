# -----------------------------------------------------------------------------
# Module: network
#
# One small VPC for the whole project (Master Doc §4.2):
#   - 2 public subnets  (AZ a, b)  -> the k3s server lives in public subnet 0
#   - 2 private subnets (AZ a, b)  -> reserved for the EKS lab / RDS (P12)
#   - NO NAT gateway (~$33/month each). The server has a public IP and only
#     makes outbound calls; private subnets have no internet route on purpose.
#   - S3 gateway endpoint (free): S3 traffic (backups, repo cache) stays on the
#     AWS network and doesn't count as internet egress.
#   - One security group: inbound 443 ONLY from CloudFront's origin-facing
#     managed prefix list (D07/D08). No SSH (admin access = SSM Session Manager).
# -----------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # 10.20.0.0/16 split into /20s: public 0-1, private 8-9 (leaves room to grow).
  public_cidrs  = [for i in range(2) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_cidrs = [for i in range(2) : cidrsubnet(var.vpc_cidr, 4, i + 8)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name}-vpc" }
}

# Lock down the VPC's default security group (no rules = deny all) so nothing
# accidentally lands in an open group.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-default-deny" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-igw" }
}

# --- public subnets ----------------------------------------------------------

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true # server gets an auto-assigned public IPv4 (no EIP, D26)

  tags = {
    Name = "${var.name}-public-${local.azs[count.index]}"
    Tier = "public"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# --- private subnets (no default route: no NAT on purpose) -------------------

resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = {
    Name = "${var.name}-private-${local.azs[count.index]}"
    Tier = "private"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# --- S3 gateway endpoint (free) ----------------------------------------------

data "aws_region" "current" {}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id, aws_route_table.private.id]

  tags = { Name = "${var.name}-s3-endpoint" }
}

# --- server security group ----------------------------------------------------

# AWS-managed list of CloudFront's origin-facing IP ranges. Using it means only
# CloudFront can reach the origin; every other source is dropped by the SG.
# It counts ~55 "rules" against the default 60 rules per SG quota (V15), so
# do NOT add more inbound rules (and no IPv6 rule).
data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "server" {
  name        = "${var.name}-server"
  description = "k3s server: HTTPS from CloudFront only, all egress"
  vpc_id      = aws_vpc.this.id

  tags = { Name = "${var.name}-server" }
}

resource "aws_vpc_security_group_ingress_rule" "https_from_cloudfront" {
  security_group_id = aws_security_group.server.id
  description       = "HTTPS from CloudFront origin-facing ranges only"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing.id
}

resource "aws_vpc_security_group_egress_rule" "all_ipv4" {
  security_group_id = aws_security_group.server.id
  description       = "All outbound (AWS APIs, GitHub, Anthropic, Voyage, Let's Encrypt)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
