terraform {
  # >= 1.11 for write-only arguments (value_wo) on SSM parameters (D15).
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  # Remote state in the bucket created by ../../bootstrap. The bucket name
  # contains the account id, so it is NOT written here (public repo): pass it
  # at init time:
  #   terraform init -backend-config=backend.hcl        (copy backend.hcl.example)
  #   terraform init -backend-config="bucket=docify-tfstate-<aws-account-id>"   (CI)
  backend "s3" {
    key          = "envs/main/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true # S3-native locking (<key>.tflock), no DynamoDB
  }
}
