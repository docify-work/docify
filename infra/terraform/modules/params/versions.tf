terraform {
  # value_wo / value_wo_version (write-only arguments) need Terraform >= 1.11
  # and AWS provider >= 6 (verified V16 against provider 6.69).
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.7"
    }
  }
}
