output "identity_arn" {
  description = "ARN of the SES domain identity (scope for ses:SendEmail)."
  value       = aws_sesv2_email_identity.this.arn
}

output "mail_from_domain" {
  description = "Custom MAIL FROM domain."
  value       = local.mail_from_domain
}
