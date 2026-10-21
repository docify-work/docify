variable "topic_name" {
  description = "SNS topic name."
  type        = string
  default     = "docify-alerts"
}

variable "alert_email" {
  description = "Email address that receives alerts (Q8). Empty = no subscription. Never commit a real address; pass it via tfvars / TF_VAR_alert_email."
  type        = string
  default     = ""
}
