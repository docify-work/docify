terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # LOCAL state on purpose: this root creates the S3 bucket that every other
  # root uses for remote state (chicken-and-egg). Run it by hand as the admin
  # user. terraform.tfstate is git-ignored; keep a copy somewhere safe
  # (e.g. upload it to the state bucket under bootstrap/ after the first apply).
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "docify"
      Env       = "shared"
      ManagedBy = "terraform"
      Repo      = "${var.github_owner}/${var.github_repo}"
    }
  }
}
