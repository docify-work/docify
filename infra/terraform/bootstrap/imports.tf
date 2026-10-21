# -----------------------------------------------------------------------------
# Phase 8 (P8.1): adopt the cost guard rails created by hand in P0.5.
#
# Terraform >= 1.5 `import` blocks: on the next plan/apply Terraform reads the
# existing object into state instead of creating a duplicate. Steps:
#   1. Make the names below match what you created in the console (or rename
#      the console objects to match the resource names in budgets.tf).
#   2. Uncomment, replace the <placeholders> LOCALLY (never commit the ids),
#      run `terraform plan` -> it should say "N to import, 0 to add".
#   3. `terraform apply`, then comment the blocks out again (they are no-ops
#      once imported, but keep the account id out of Git).
#
# Ids:
#   budget            "<aws-account-id>:<budget-name>"
#   anomaly monitor   its ARN    (aws ce get-anomaly-monitors)
#   anomaly subscr.   its ARN    (aws ce get-anomaly-subscriptions)
# -----------------------------------------------------------------------------

# import {
#   to = aws_budgets_budget.monthly["5"]
#   id = "<aws-account-id>:docify-monthly-5usd"
# }
#
# import {
#   to = aws_budgets_budget.monthly["15"]
#   id = "<aws-account-id>:docify-monthly-15usd"
# }
#
# import {
#   to = aws_budgets_budget.monthly["30"]
#   id = "<aws-account-id>:docify-monthly-30usd"
# }
#
# import {
#   to = aws_ce_anomaly_monitor.services
#   id = "arn:aws:ce::<aws-account-id>:anomalymonitor/<monitor-uuid>"
# }
#
# import {
#   to = aws_ce_anomaly_subscription.email
#   id = "arn:aws:ce::<aws-account-id>:anomalysubscription/<subscription-uuid>"
# }
