# Non-sensitive outputs only (the public CI log may print them).

output "instance_id" {
  description = "k3s server instance id (R1/R2)."
  value       = module.server.instance_id
}

output "instance_architecture" {
  description = "amd64 | arm64 - build images for this platform."
  value       = module.server.architecture
}

output "data_volume_id" {
  description = "Data EBS volume id."
  value       = module.server.data_volume_id
}

output "distribution_ids" {
  description = "CloudFront distribution ids per env -> repo variables CF_DISTRIBUTION_ID_STAGING / CF_DISTRIBUTION_ID_PROD."
  value       = { for env, e in module.edge : env => e.distribution_id }
}

output "distribution_domains" {
  description = "dxxxx.cloudfront.net per env."
  value       = { for env, e in module.edge : env => e.domain_name }
}

output "queue_urls" {
  description = "Events queue URL per env (SQS_QUEUE_URL)."
  value       = { for env, q in module.queues : env => q.queue_url }
}

output "dlq_urls" {
  description = "Dead-letter queue URL per env (SQS_DLQ_URL)."
  value       = { for env, q in module.queues : env => q.dlq_url }
}

output "webhook_urls" {
  description = "Lambda Function URL per env -> GitHub App 'Webhook URL'."
  value       = { for env, l in module.ingest : env => l.function_url }
}

output "bucket_names" {
  description = "All bucket names."
  value = {
    web        = { for env, b in module.storage.web_buckets : env => b.id }
    artifacts  = module.storage.artifacts_bucket.id
    backups    = module.storage.backups_bucket.id
    repo_cache = module.storage.repo_cache_bucket.id
  }
}

output "ecr_repository_url" {
  description = "ECR repository for docify/backend."
  value       = module.registry.repository_url
}

output "hosted_zone_id" {
  description = "Route 53 zone id (cert-manager ClusterIssuer hostedZoneID)."
  value       = module.dns.zone_id
}

output "name_servers" {
  description = "Set these at the registrar if the zone was (re)created."
  value       = module.dns.name_servers
}

output "alerts_topic_arn" {
  description = "SNS topic for Grafana's contact point."
  value       = module.alerts.topic_arn
}
