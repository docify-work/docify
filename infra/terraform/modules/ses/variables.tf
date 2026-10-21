variable "domain" {
  description = "Domain to send email from, e.g. docify.work."
  type        = string
}

variable "zone_id" {
  description = "Route 53 hosted zone id for the domain."
  type        = string
}

variable "mail_from_subdomain" {
  description = "Subdomain used as custom MAIL FROM (bounce) domain."
  type        = string
  default     = "mail"
}

variable "dmarc_rua_email" {
  description = "Optional mailbox for DMARC aggregate reports (empty = no reports). Never commit a personal address."
  type        = string
  default     = ""
}
