variable "region" {
  description = "AWS region."
  type        = string
  default     = "ap-south-1"
}

variable "cluster_version" {
  description = "EKS Kubernetes version (pick a standard-support version at P12 to avoid extended-support fees)."
  type        = string
  default     = "1.36"
}

variable "node_instance_types" {
  description = "Spot instance types for the managed node group (arm64: images are built for linux/arm64)."
  type        = list(string)
  default     = ["t4g.medium"]
}

variable "node_min" {
  description = "Minimum nodes."
  type        = number
  default     = 1
}

variable "node_max" {
  description = "Maximum nodes (Cluster Autoscaler ceiling)."
  type        = number
  default     = 3
}

variable "rds_instance_class" {
  description = "RDS PostgreSQL 17 instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "repo_cache_bucket" {
  description = "Name of the envs/main repo-cache bucket (terraform -chdir=../main output bucket_names). Set in the git-ignored terraform.tfvars."
  type        = string
}
