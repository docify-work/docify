variable "region" {
  description = "Main AWS region (D29)."
  type        = string
  default     = "ap-south-1"
}

variable "github_owner" {
  description = "GitHub user/org that owns the repo (used in OIDC trust subjects)."
  type        = string
  default     = "docify-work"
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
  default     = "docify"
}

variable "budget_email" {
  description = "Email that receives budget + cost-anomaly alerts. Never commit it: pass via terraform.tfvars (git-ignored) or TF_VAR_budget_email."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_email))
    error_message = "budget_email must be an email address."
  }
}

variable "budget_limits_usd" {
  description = "Monthly cost budgets in USD; each alerts on ACTUAL and FORECASTED spend at 100%."
  type        = list(number)
  default     = [5, 15, 30]
}

variable "anomaly_threshold_usd" {
  description = "Cost Anomaly Detection: alert when an anomaly's total impact is at least this many USD."
  type        = number
  default     = 5
}

variable "server_name_tag" {
  description = "Name tag of the k3s server instance; ops/power permissions are limited to instances with this tag (the instance is created later by envs/main)."
  type        = string
  default     = "docify-server"
}

variable "state_noncurrent_days" {
  description = "Days to keep old (noncurrent) versions of state files."
  type        = number
  default     = 90
}
