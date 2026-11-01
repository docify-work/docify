variable "name" {
  description = "Name prefix."
  type        = string
  default     = "docify"
}

# --- placement -------------------------------------------------------------------

variable "instance_type" {
  description = "EC2 instance type (D30/Q7). Graviton types (t4g, m7g...) automatically switch the AMI + binaries to arm64."
  type        = string
  default     = "t4g.large"
}

variable "subnet_id" {
  description = "Public subnet for the server."
  type        = string
}

variable "availability_zone" {
  description = "AZ of that subnet (the data volume must be in the same AZ)."
  type        = string
}

variable "security_group_ids" {
  description = "Security groups for the server."
  type        = list(string)
}

variable "root_volume_size" {
  description = "Root volume size in GiB."
  type        = number
  default     = 30
}

variable "data_volume_size" {
  description = "Data volume (/data) size in GiB. Can be grown online later (R9)."
  type        = number
  default     = 10
}

variable "cpu_credits" {
  description = "CPU credit mode for burstable (t*) types; ignored for others. standard = throttle to baseline when credits run out (never bills surplus CPU, D56)."
  type        = string
  default     = "standard"
}

# --- things the role is scoped to ---------------------------------------------------------

variable "domain" {
  description = "Apex domain (origin.<domain>, origin-staging.<domain>)."
  type        = string
}

variable "origin_hostnames" {
  description = "Origin host labels the server updates at boot and cert-manager validates."
  type        = list(string)
  default     = ["origin", "origin-staging"]
}

variable "zone_id" {
  description = "Route 53 hosted zone id."
  type        = string
}

variable "zone_arn" {
  description = "Route 53 hosted zone ARN."
  type        = string
}

variable "backups_bucket_arn" {
  description = "ARN of the backups bucket."
  type        = string
}

variable "repo_cache_bucket_arn" {
  description = "ARN of the repo-cache bucket."
  type        = string
}

variable "ses_identity_arn" {
  description = "ARN of the SES domain identity."
  type        = string
}

variable "alerts_topic_arn" {
  description = "ARN of the docify-alerts SNS topic."
  type        = string
}

# --- snapshots ---------------------------------------------------------------------------------

variable "snapshot_time_utc" {
  description = "Daily DLM snapshot time (UTC, HH:MM). 18:00 UTC = 23:30 IST, after the nightly backup and auto-stop."
  type        = string
  default     = "18:00"
}

variable "snapshot_retain_count" {
  description = "Number of daily snapshots to keep."
  type        = number
  default     = 7
}

# --- bootstrap script inputs (pinned versions) ---------------------------------------------------

variable "k3s_version" {
  description = "k3s release (INSTALL_K3S_VERSION). V18: re-check kubelet flags when bumping."
  type        = string
}

variable "ecr_credential_provider_version" {
  description = "kubernetes/cloud-provider-aws release that ships ecr-credential-provider (binary from artifacts.k8s.io)."
  type        = string
}

variable "ecr_credential_provider_sha256" {
  description = "sha256 of the ecr-credential-provider binary per architecture (amd64, arm64)."
  type        = map(string)
}

variable "helm_version" {
  description = "Helm CLI version used once to install Argo CD."
  type        = string
}

variable "helm_sha256" {
  description = "sha256 of the helm tarball per architecture (amd64, arm64)."
  type        = map(string)
}

variable "argocd_chart_version" {
  description = "argo-cd Helm chart version. MUST equal the version the root app pins for the argocd Application, so Argo CD adopts the release instead of upgrading it."
  type        = string
}

variable "git_repo_url" {
  description = "Git repository Argo CD watches."
  type        = string
}

variable "git_revision" {
  description = "Branch/revision the root Application tracks."
  type        = string
  default     = "main"
}

variable "root_app_path" {
  description = "Path of the root (app-of-apps) Helm chart in the repo."
  type        = string
  default     = "deploy/argocd/root"
}

variable "root_values_files" {
  description = "Value files (relative to root_app_path) for the root Application."
  type        = list(string)
  default     = ["values.yaml"]
}

variable "argocd_values_path" {
  description = "Repo path of the Argo CD Helm values (fetched from raw.githubusercontent.com at boot so the bootstrap install is identical to what Argo CD later manages)."
  type        = string
  default     = "deploy/values/platform/argocd.yaml"
}
