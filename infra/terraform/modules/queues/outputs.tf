output "queue_url" {
  description = "Events queue URL (SQS_QUEUE_URL)."
  value       = aws_sqs_queue.events.url
}

output "queue_arn" {
  description = "Events queue ARN."
  value       = aws_sqs_queue.events.arn
}

output "queue_name" {
  description = "Events queue name."
  value       = aws_sqs_queue.events.name
}

output "dlq_url" {
  description = "Dead-letter queue URL (SQS_DLQ_URL)."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "Dead-letter queue ARN."
  value       = aws_sqs_queue.dlq.arn
}
