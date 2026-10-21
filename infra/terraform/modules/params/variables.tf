variable "name" {
  description = "Top-level path segment for all parameters (/<name>/...)."
  type        = string
  default     = "docify"
}

variable "envs" {
  description = "Environments that get their own /docify/<env>/* parameters."
  type        = list(string)
  default     = ["staging", "prod"]
}

variable "placeholder_value" {
  description = "Dummy value written once on create. Real values come from scripts/init-params.sh."
  type        = string
  default     = "CHANGE_ME"
  ephemeral   = true # never persisted in plan or state
}

variable "placeholder_version" {
  description = "Bump to force Terraform to rewrite the placeholder into EVERY parameter (destroys real values!)."
  type        = number
  default     = 1
}

variable "origin_verify_version" {
  description = "Bump after replacing random_password.origin_verify so the new value is written to SSM."
  type        = number
  default     = 1
}
