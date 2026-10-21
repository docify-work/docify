output "web_buckets" {
  description = "Per-env web bucket attributes: { env => { id, arn, regional_domain_name } }."
  value = {
    for env, b in aws_s3_bucket.web : env => {
      id                   = b.id
      arn                  = b.arn
      regional_domain_name = b.bucket_regional_domain_name
    }
  }
}

output "artifacts_bucket" {
  description = "Artifacts bucket name and ARN."
  value       = { id = aws_s3_bucket.artifacts.id, arn = aws_s3_bucket.artifacts.arn }
}

output "backups_bucket" {
  description = "Backups bucket name and ARN."
  value       = { id = aws_s3_bucket.backups.id, arn = aws_s3_bucket.backups.arn }
}

output "repo_cache_bucket" {
  description = "Repo-cache bucket name and ARN."
  value       = { id = aws_s3_bucket.repo_cache.id, arn = aws_s3_bucket.repo_cache.arn }
}
