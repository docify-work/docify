variable "region" {
  description = "Main AWS region (D29)."
  type        = string
  default     = "ap-south-1"
}

variable "domain" {
  description = "Apex domain (Q1)."
  type        = string
  default     = "docify.work"
}

variable "github_repository" {
  description = "<owner>/<repo> on GitHub (tags + Argo CD repo URL)."
  type        = string
  default     = "docify-work/docify"
}

variable "envs" {
  description = "Application environments sharing the one server."
  type        = list(string)
  default     = ["staging", "prod"]
}

variable "instance_type" {
  description = "Server instance type (D30/Q7). m7i-flex.large = 2 vCPU / 8 GiB, Free-Plan eligible."
  type        = string
  default     = "m7i-flex.large"
}

variable "alert_email" {
  description = "Email for the docify-alerts SNS topic (Q8). Pass via terraform.tfvars or TF_VAR_alert_email; never commit."
  type        = string
  default     = ""
}

variable "dmarc_rua_email" {
  description = "Optional mailbox for DMARC aggregate reports."
  type        = string
  default     = ""
}

variable "lambda_reserved_concurrency" {
  description = "Reserved concurrency per webhook Lambda (null = none; see V14 before setting 5)."
  type        = number
  default     = null
}

# --- pinned versions for the server bootstrap script (§26.1) ---------------------------------

variable "k3s_version" {
  description = "k3s version installed on the server."
  type        = string
  default     = "v1.36.5+k3s1" # stable channel, 2026-10-21
}

variable "ecr_credential_provider_version" {
  description = "cloud-provider-aws release for ecr-credential-provider (published at artifacts.k8s.io)."
  type        = string
  default     = "v1.37.0"
}

variable "ecr_credential_provider_sha256" {
  description = "sha256 of ecr-credential-provider-linux-<arch> for the version above (from the .sha256 files next to the binaries)."
  type        = map(string)
  default = {
    amd64 = "842e0fd8159f5ed8df2f38e6521e1e4f0a1ee80cf1e1ac119bbf20bf9c20681c"
    arm64 = "dd4748d167b0167cd4a66779dbbe4964e17a29a076aaa3d2b63cfc36ae84b52c"
  }
}

variable "helm_version" {
  description = "Helm CLI used once at boot to install Argo CD."
  type        = string
  default     = "v3.22.1"
}

variable "helm_sha256" {
  description = "sha256 of helm-<version>-linux-<arch>.tar.gz (from get.helm.sh .sha256sum files)."
  type        = map(string)
  default = {
    amd64 = "896cf63684a42a723d61c980369d6e588330927deb13676ca0d85006dd6da0ea"
    arm64 = "4c29e286b279d170fa048ddfc3e4e83dcd069ca9c52102766ba672d7149e694d"
  }
}

variable "argocd_chart_version" {
  description = "argo-cd Helm chart version. Keep equal to the version pinned for the argocd Application in deploy/argocd/root."
  type        = string
  default     = "10.10.5"
}

variable "git_revision" {
  description = "Branch the root Argo CD Application tracks."
  type        = string
  default     = "main"
}

variable "root_values_files" {
  description = "Value files of the root app-of-apps chart (relative to deploy/argocd/root)."
  type        = list(string)
  default     = ["values.yaml"]
}
