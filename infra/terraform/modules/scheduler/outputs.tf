output "schedule_arn" {
  description = "ARN of the auto-stop schedule."
  value       = aws_scheduler_schedule.stop_server.arn
}

output "role_arn" {
  description = "ARN of the role EventBridge Scheduler assumes."
  value       = aws_iam_role.scheduler.arn
}
