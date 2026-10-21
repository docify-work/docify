# -----------------------------------------------------------------------------
# Cost guard rails (Plan §9, Master Doc §12.6). These cover the time the
# server is asleep, when Grafana alerts can't run.
#
#   3 monthly cost budgets ($5 / $15 / $30), each emailing on
#     - ACTUAL spend     > 100% of the limit
#     - FORECASTED spend > 100% of the limit (early warning)
#   Cost Anomaly Detection: ML monitor per AWS service, daily email summary
#   of anomalies whose impact is >= anomaly_threshold_usd.
#
# Budgets + the anomaly monitor were created by hand on day 1 (P0.5) and are
# IMPORTED here in Phase 8 -> see imports.tf.
# -----------------------------------------------------------------------------

resource "aws_budgets_budget" "monthly" {
  for_each = { for limit in var.budget_limits_usd : tostring(limit) => limit }

  name         = "docify-monthly-${each.key}usd"
  budget_type  = "COST"
  limit_amount = format("%.1f", each.value)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}

resource "aws_ce_anomaly_monitor" "services" {
  name              = "docify-services"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "email" {
  name             = "docify-anomaly-email"
  frequency        = "DAILY" # email subscribers support DAILY/WEEKLY (IMMEDIATE needs SNS)
  monitor_arn_list = [aws_ce_anomaly_monitor.services.arn]

  subscriber {
    type    = "EMAIL"
    address = var.budget_email
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = [tostring(var.anomaly_threshold_usd)]
    }
  }
}
