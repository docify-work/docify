# -----------------------------------------------------------------------------
# Module: ingest  (one instance per environment)
#
# GitHub webhook receiver = Lambda Function URL -> SQS (D05, Master Doc §5.4).
# Why not send webhooks straight to the cluster: the server sleeps most of the
# time and GitHub does not retry failed deliveries. The Lambda is always on,
# costs ~nothing, verifies the HMAC signature, filters events and drops a
# small message into SQS, where it waits (up to 14 days) for the worker.
#
#   runtime python3.13, arm64 (Graviton = cheaper), 128 MB, 5 s timeout
#   Function URL AuthType NONE: GitHub can't sign AWS requests; the HMAC
#   check inside the handler is the authentication.
#   IAM: send to own queue, read own webhook secret, write own logs. Nothing else.
#
# Code: lambdas/webhook_ingest/ (entry handler.handler), zipped by archive_file.
# boto3 is provided by the Lambda runtime, so no dependencies are bundled.
# -----------------------------------------------------------------------------

locals {
  function_name = "${var.name}-${var.env}-webhook-ingest"
}

data "aws_region" "current" {}

data "archive_file" "code" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${var.build_dir}/${local.function_name}.zip"
  excludes    = ["__pycache__", "tests", ".pytest_cache"]
}

# Create the log group ourselves so retention is 7 d (default = never expire).
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days

  tags = { Env = var.env }
}

# --- IAM ----------------------------------------------------------------------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = local.function_name
  assume_role_policy = data.aws_iam_policy_document.assume.json

  tags = { Env = var.env }
}

data "aws_iam_policy_document" "this" {
  statement {
    sid       = "SendToOwnQueue"
    actions   = ["sqs:SendMessage"]
    resources = [var.queue_arn]
  }

  statement {
    sid       = "ReadOwnWebhookSecret"
    actions   = ["ssm:GetParameter"]
    resources = [var.webhook_secret_param_arn]
  }

  # SecureStrings use the AWS-managed key aws/ssm; allow decrypt only via SSM.
  statement {
    sid       = "DecryptViaSsmOnly"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${data.aws_region.current.region}.amazonaws.com"]
    }
  }

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "webhook-ingest"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

# --- function -------------------------------------------------------------------

resource "aws_lambda_function" "this" {
  function_name = local.function_name
  description   = "GitHub webhook -> HMAC verify -> filter -> SQS (${var.env})"
  role          = aws_iam_role.this.arn

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.13"
  architectures    = ["arm64"]
  memory_size      = 128
  timeout          = 5

  # null = no reservation. The new-account concurrency quota can be as low as
  # 10, and AWS refuses reservations that leave < 10 unreserved (V14, §5.4).
  reserved_concurrent_executions = var.reserved_concurrency

  environment {
    variables = {
      QUEUE_URL            = var.queue_url
      WEBHOOK_SECRET_PARAM = var.webhook_secret_param_name
      ENV                  = var.env
    }
  }

  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy.this]

  tags = { Env = var.env }
}

resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE" # auth = HMAC signature check in the handler
}

# Public Function URLs need BOTH permissions (AWS change, Oct 2025; V13 -
# argument names verified against AWS provider 6.69 schema):
#   1) lambda:InvokeFunctionUrl restricted to auth type NONE
#   2) lambda:InvokeFunction, but only when the call comes through the URL
resource "aws_lambda_permission" "url_invoke_function_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "url_invoke_function" {
  statement_id             = "AllowInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.this.function_name
  principal                = "*"
  invoked_via_function_url = true
}
