variable "repository_name" {
  description = "ECR repository name."
  type        = string
  default     = "docify/backend"
}

variable "keep_images" {
  description = "How many images to keep (older ones are expired by the lifecycle policy)."
  type        = number
  default     = 15
}
