output "state_bucket" {
  description = "Remote-state bucket -> put it in envs/main/backend.hcl."
  value       = aws_s3_bucket.state.id
}

output "github_oidc_provider_arn" {
  description = "GitHub Actions OIDC provider ARN."
  value       = aws_iam_openid_connect_provider.github.arn
}

output "ci_role_arns" {
  description = "Role ARNs for the workflows (they rebuild these from vars.AWS_ACCOUNT_ID + the role name)."
  value       = { for name, role in aws_iam_role.ci : name => role.arn }
}
