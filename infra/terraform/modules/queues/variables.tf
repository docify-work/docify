variable "name" {
  description = "Name prefix."
  type        = string
  default     = "docify"
}

variable "env" {
  description = "Environment name (staging | prod)."
  type        = string
}

variable "retention_seconds" {
  description = "Message retention for queue and DLQ (14 days = SQS maximum)."
  type        = number
  default     = 1209600
}

variable "max_receive_count" {
  description = "Receives before a message is moved to the DLQ (§8.3 rule 10)."
  type        = number
  default     = 5
}
