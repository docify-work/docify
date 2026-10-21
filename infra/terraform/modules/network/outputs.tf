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
}
