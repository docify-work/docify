variable "name" {
  description = "Name prefix."
  type        = string
  default     = "docify"
}

variable "env" {
  description = "Environment name (staging | prod)."
  type        = string
}

variable "source_dir" {
  description = "Path to the Lambda source directory (lambdas/webhook_ingest)."
  type        = string
}

variable "build_dir" {
  description = "Directory where the zip is written (must be git-ignored)."
  type        = string
}

variable "queue_url" {
  description = "URL of this env's events queue (QUEUE_URL)."
  type        = string
}

variable "queue_arn" {
  description = "ARN of this env's events queue."
  type        = string
}

variable "webhook_secret_param_name" {
  description = "SSM parameter name holding the GitHub webhook secret (WEBHOOK_SECRET_PARAM)."
  type        = string
}

variable "webhook_secret_param_arn" {
  description = "ARN of that SSM parameter."
  type        = string
}

variable "reserved_concurrency" {
  description = "Reserved concurrency (null = none). Set 5 only if the account concurrency quota is > 10 (V14)."
  type        = number
  default     = null
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention."
  type        = number
  default     = 7
}
