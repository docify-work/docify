variable "name" {
  description = "Name prefix for all network resources."
  type        = string
  default     = "docify"
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC (Master Doc §4.2)."
  type        = string
  default     = "10.20.0.0/16"
}
