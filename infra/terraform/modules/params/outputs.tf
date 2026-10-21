output "parameter_arns" {
  description = "Map of parameter name => ARN for every secret parameter."
  value = merge(
    { for k, p in aws_ssm_parameter.placeholder : k => p.arn },
    { for env, p in aws_ssm_parameter.origin_verify : p.name => p.arn },
  )
}

output "webhook_secret_params" {
  description = "Per env: name and ARN of the GitHub webhook secret parameter (read by the Lambda)."
  value = {
    for env in var.envs : env => {
      name = aws_ssm_parameter.placeholder["/${var.name}/${env}/github/webhook_secret"].name
      arn  = aws_ssm_parameter.placeholder["/${var.name}/${env}/github/webhook_secret"].arn
    }
  }
}

output "origin_verify_values" {
  description = "Per env: X-Origin-Verify header value for CloudFront."
  value       = { for env, p in random_password.origin_verify : env => p.result }
  sensitive   = true
}
