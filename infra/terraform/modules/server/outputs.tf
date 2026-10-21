output "instance_id" {
  description = "EC2 instance id."
  value       = aws_instance.this.id
}

output "instance_arn" {
  description = "EC2 instance ARN."
  value       = aws_instance.this.arn
}

output "instance_role_arn" {
  description = "Instance role ARN (used by pods through IMDS, D16)."
  value       = aws_iam_role.instance.arn
}

output "data_volume_id" {
  description = "Data EBS volume id (/data)."
  value       = aws_ebs_volume.data.id
}

output "architecture" {
  description = "CPU architecture derived from the instance type (amd64 | arm64)."
  value       = local.architecture
}
