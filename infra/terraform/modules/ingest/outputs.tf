output "function_name" {
  description = "Lambda function name."
  value       = aws_lambda_function.this.function_name
}

output "function_url" {
  description = "Public Function URL -> paste into the GitHub App's Webhook URL."
  value       = aws_lambda_function_url.this.function_url
}

output "role_arn" {
  description = "Lambda execution role ARN."
  value       = aws_iam_role.this.arn
}
