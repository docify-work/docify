# TFLint config shared by every Terraform root/module under infra/terraform.
# Usage (from a root, e.g. envs/main):
#   tflint --init --config "$(pwd)/../../.tflint.hcl"
#   tflint --recursive --config "$(pwd)/../../.tflint.hcl"   (or run from infra/terraform)

config {
  call_module_type = "local" # also lint ../../modules/* through the roots
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.49.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
