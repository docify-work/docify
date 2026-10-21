# -----------------------------------------------------------------------------
# Module: scheduler
#
# Nightly auto-stop of the server at 23:00 Asia/Kolkata (D25).
# Why EventBridge Scheduler and not a GitHub cron workflow: GitHub disables
# scheduled workflows after 60 days without repo activity, and a forgotten
# running server is the #1 way to blow the budget.
#
# The target is a "universal target": Scheduler calls the EC2 API
# StopInstances directly (no Lambda needed). V17.
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    # Confused-deputy guard: only schedules in this account may use the role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name}-scheduler-stop-server"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "stop" {
  statement {
    sid       = "StopOnlyTheServer"
    actions   = ["ec2:StopInstances"]
    resources = [var.instance_arn]
  }
}

resource "aws_iam_role_policy" "stop" {
  name   = "stop-server"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.stop.json
}

resource "aws_scheduler_schedule" "stop_server" {
  name        = "${var.name}-server-auto-stop"
  description = "Stop the Docify k3s server every night (D25)"

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:stopInstances"
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ InstanceIds = [var.instance_id] })

    retry_policy {
      maximum_retry_attempts       = 3
      maximum_event_age_in_seconds = 3600
    }
  }
}
