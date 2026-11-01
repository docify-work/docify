output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet ids (index 0 hosts the k3s server)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet ids (reserved for the EKS lab / RDS)."
  value       = aws_subnet.private[*].id
}

output "public_subnet_azs" {
  description = "Availability zones of the public subnets (same order as public_subnet_ids)."
  value       = aws_subnet.public[*].availability_zone
}

output "server_security_group_id" {
  description = "Security group for the k3s server (443 from CloudFront only)."
  value       = aws_security_group.server.id
  # The server's first boot downloads packages, k3s and Helm charts. Make every
  # consumer (the instance) wait until the rules exist, otherwise cloud-init
  # starts with no egress and has to rely on retries (seen 2026-11-01).
  depends_on = [
    aws_vpc_security_group_egress_rule.all_ipv4,
    aws_vpc_security_group_ingress_rule.https_from_cloudfront,
  ]
}
