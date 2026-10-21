output "distribution_id" {
  description = "CloudFront distribution id (used for cache invalidations in CI)."
  value       = aws_cloudfront_distribution.this.id
}

output "distribution_arn" {
  description = "CloudFront distribution ARN."
  value       = aws_cloudfront_distribution.this.arn
}

output "domain_name" {
  description = "dxxxx.cloudfront.net hostname (target of the Route 53 aliases)."
  value       = aws_cloudfront_distribution.this.domain_name
}

output "hosted_zone_id" {
  description = "CloudFront's Route 53 zone id for alias records."
  value       = aws_cloudfront_distribution.this.hosted_zone_id
}
