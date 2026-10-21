variable "name" {
  description = "Name prefix."
  type        = string
  default     = "docify"
}

variable "instance_id" {
  description = "Id of the EC2 instance to stop."
  type        = string
}

variable "instance_arn" {
  description = "ARN of the EC2 instance to stop (the role may stop only this instance)."
  type        = string
}

variable "schedule_expression" {
  description = "When to stop the server."
  type        = string
  default     = "cron(0 23 * * ? *)"
}

variable "timezone" {
  description = "Timezone for the schedule expression."
  type        = string
  default     = "Asia/Kolkata"
}
