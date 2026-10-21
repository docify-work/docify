variable "name" {
  description = "Name prefix."
  type        = string
  default     = "docify"
}

variable "env" {
  description = "Environment name (staging | prod)."
  type        = string
}

variable "aliases" {
  description = "Hostnames served by this distribution (prod: apex + www, staging: staging.<domain>)."
  type        = list(string)
}

variable "web_bucket" {
  description = "This env's web bucket."
  type = object({
    id                   = string
    arn                  = string
    regional_domain_name = string
  })
}

variable "origin_domain" {
  description = "API origin hostname, e.g. origin.<domain> or origin-staging.<domain>."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN in us-east-1 covering the aliases."
  type        = string
}

variable "origin_verify_value" {
  description = "Secret value CloudFront sends as X-Origin-Verify to the API origin."
  type        = string
  sensitive   = true
}

variable "price_class" {
  description = "CloudFront price class (200 includes India edge locations, V15)."
  type        = string
  default     = "PriceClass_200"
}

variable "content_security_policy" {
  description = "Content-Security-Policy header value (Master Doc §10.5)."
  type        = string
  default     = "default-src 'self'; img-src 'self' https://avatars.githubusercontent.com https://*.googleusercontent.com data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://github.com https://accounts.google.com"
}
