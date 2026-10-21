# -----------------------------------------------------------------------------
# Module: queues  (one instance per environment)
#
# `docify-<env>-events` + its dead-letter queue (Master Doc §8.5).
# GitHub webhooks land here via the Lambda (D05), and the worker also uses it
# for its own job messages. SQS keeps messages for 14 days, which is what lets
# the server sleep while pushes keep arriving.
#
#   visibility 300 s   the worker heartbeat extends it while a job runs
#   receive wait 20 s  long polling = fewer empty (billed) receives
#   redrive 5          a message received 5x without being deleted is a crash
#                      -> moved to the DLQ (an alert fires when DLQ > 0)
#   SSE-SQS            free server-side encryption with SQS-owned keys
# -----------------------------------------------------------------------------

locals {
  queue_name = "${var.name}-${var.env}-events"
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.queue_name}-dlq"
  message_retention_seconds = var.retention_seconds
  sqs_managed_sse_enabled   = true

  tags = { Env = var.env }
}

resource "aws_sqs_queue" "events" {
  name                       = local.queue_name
  visibility_timeout_seconds = 300
  message_retention_seconds  = var.retention_seconds
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = { Env = var.env }
}

# Only our own events queue may use this DLQ.
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.events.arn]
  })
}
