variable "domain" {
  description = "Apex domain, e.g. docify.work."
  type        = string
}

variable "origin_hostnames" {
  description = "Origin host labels whose A records the server updates at boot."
  type        = list(string)
  default     = ["origin", "origin-staging"]
}

variable "distributions" {
  description = "CloudFront distributions per env (keys: prod, staging) for the alias records."
  type = map(object({
    domain_name    = string
    hosted_zone_id = string
  }))
}
