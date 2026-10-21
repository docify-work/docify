output "topic_arn" {
  description = "ARN of the docify-alerts SNS topic."
  value       = aws_sns_topic.alerts.arn
}
