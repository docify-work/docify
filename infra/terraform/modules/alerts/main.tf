# -----------------------------------------------------------------------------
# Module: alerts
#
# SNS topic `docify-alerts` + an email subscription (§12.6, D35).
# Grafana publishes to it using the EC2 instance role (no static keys, unlike
# SES SMTP). AWS sends a confirmation email: the subscription stays
# "PendingConfirmation" until the link in that mail is clicked.
# Encrypted with the AWS-managed SNS key (free; publishers in this account can
# use it through SNS without extra key policy).
# -----------------------------------------------------------------------------

resource "aws_sns_topic" "alerts" {
  name              = var.topic_name
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
