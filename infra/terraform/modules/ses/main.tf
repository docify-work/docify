# -----------------------------------------------------------------------------
# Module: ses
#
# Amazon SES for transactional email (verification, password reset, invites;
# D23). Master Doc §12.6.
#
#   domain identity + Easy DKIM   3 CNAMEs; AWS rotates the keys for us
#   MAIL FROM mail.<domain>       MX + SPF TXT on the subdomain, so SPF aligns
#                                 with our domain instead of amazonses.com
#   DMARC p=quarantine            tells receivers what to do with spoofed mail
#   account suppression list      SES stops sending to addresses that bounced
#                                 or complained (protects sender reputation)
#
# The identity was created by hand in Phase 0 (production-access request needs
# it early). In Phase 8 it is IMPORTED - uncomment these blocks in the ROOT
# module (envs/main/imports.tf), import blocks cannot live inside a module:
#
# import {
#   to = module.ses.aws_sesv2_email_identity.this
#   id = "<domain>"
# }
# import {
#   to = module.ses.aws_sesv2_email_identity_mail_from_attributes.this
#   id = "<domain>"
# }
# import {
#   to = module.ses.aws_route53_record.dkim[0]    # repeat for [1], [2]
#   id = "<zone-id>_<token>._domainkey.<domain>_CNAME"
# }
# -----------------------------------------------------------------------------

data "aws_region" "current" {}

resource "aws_sesv2_email_identity" "this" {
  email_identity = var.domain

  # Easy DKIM (AWS-managed 2048-bit keys).
  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

# Easy DKIM always returns exactly 3 tokens -> 3 CNAME records.
resource "aws_route53_record" "dkim" {
  count = 3

  zone_id = var.zone_id
  name    = "${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}._domainkey.${var.domain}"
  type    = "CNAME"
  ttl     = 1800
  records = ["${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

# --- custom MAIL FROM domain --------------------------------------------------------

locals {
  mail_from_domain = "${var.mail_from_subdomain}.${var.domain}"
}

resource "aws_sesv2_email_identity_mail_from_attributes" "this" {
  email_identity         = aws_sesv2_email_identity.this.email_identity
  mail_from_domain       = local.mail_from_domain
  behavior_on_mx_failure = "USE_DEFAULT_VALUE" # fall back to amazonses.com rather than reject
}

resource "aws_route53_record" "mail_from_mx" {
  zone_id = var.zone_id
  name    = local.mail_from_domain
  type    = "MX"
  ttl     = 1800
  records = ["10 feedback-smtp.${data.aws_region.current.region}.amazonses.com"]
}

resource "aws_route53_record" "mail_from_spf" {
  zone_id = var.zone_id
  name    = local.mail_from_domain
  type    = "TXT"
  ttl     = 1800
  records = ["v=spf1 include:amazonses.com ~all"]
}

# --- DMARC ------------------------------------------------------------------------

resource "aws_route53_record" "dmarc" {
  zone_id = var.zone_id
  name    = "_dmarc.${var.domain}"
  type    = "TXT"
  ttl     = 1800
  records = [
    var.dmarc_rua_email == ""
    ? "v=DMARC1; p=quarantine"
    : "v=DMARC1; p=quarantine; rua=mailto:${var.dmarc_rua_email}"
  ]
}

# --- account-level suppression list ------------------------------------------------------

resource "aws_sesv2_account_suppression_attributes" "this" {
  suppressed_reasons = ["BOUNCE", "COMPLAINT"]
}
