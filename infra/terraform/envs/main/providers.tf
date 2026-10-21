# Default provider: everything lives in ap-south-1 (Mumbai, D29) ...
provider "aws" {
  region = var.region

  # Tags added to EVERY resource -> Cost Explorer can filter on Project=docify.
  # Env-specific resources override Env with "staging" / "prod".
  default_tags {
    tags = local.default_tags
  }
}

# ... except the CloudFront certificate, which AWS requires in us-east-1.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.default_tags
  }
}

locals {
  default_tags = {
    Project   = "docify"
    Env       = "shared"
    ManagedBy = "terraform"
    Repo      = var.github_repository
  }
}
