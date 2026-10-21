output "zone_id" {
  description = "Hosted zone id."
  value       = aws_route53_zone.this.zone_id
}

output "zone_arn" {
  description = "Hosted zone ARN (used to scope the instance role's Route 53 permissions)."
  value       = aws_route53_zone.this.arn
}

output "name_servers" {
  description = "Name servers to configure at the domain registrar."
  value       = aws_route53_zone.this.name_servers
}

output "certificate_arn" {
  description = "ARN of the validated us-east-1 ACM certificate (<domain> + *.<domain>)."
  value       = aws_acm_certificate_validation.cloudfront.certificate_arn
}

output "origin_fqdns" {
  description = "Origin FQDNs, e.g. { origin = origin.<domain>, origin-staging = origin-staging.<domain> }."
  value       = { for k, r in aws_route53_record.origin : k => r.fqdn }
}
