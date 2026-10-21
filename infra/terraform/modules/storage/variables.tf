variable "name" {
  description = "Name prefix for buckets."
  type        = string
  default     = "docify"
}

variable "account_id" {
  description = "AWS account id, used as bucket-name suffix (bucket names are global). Comes from data.aws_caller_identity, never hard-coded."
  type        = string
}

variable "envs" {
  description = "Environments that get their own web bucket."
  type        = list(string)
  default     = ["staging", "prod"]
}

variable "artifacts_expire_days" {
  description = "Days to keep frontend/<sha>.tar.gz build artifacts."
  type        = number
  default     = 30
}

variable "backups_expire_days" {
  description = "Days to keep Postgres dumps."
  type        = number
  default     = 14
}

variable "repo_cache_expire_days" {
  description = "Days to keep cached repo tarballs."
  type        = number
  default     = 7
}
