terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Same state bucket as envs/main, separate key. Bucket passed at init:
  #   terraform init -backend-config=../main/backend.hcl
  backend "s3" {
    key          = "envs/eks-lab/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "docify"
      Env       = "eks-lab"
      ManagedBy = "terraform"
      Repo      = "docify-work/docify"
    }
  }
}
