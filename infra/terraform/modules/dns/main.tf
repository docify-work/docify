# -----------------------------------------------------------------------------
# Module: dns
#
# Route 53 hosted zone + records, and the CloudFront TLS certificate.
#
#   zone <domain>                created manually in Phase 0 (SES needs it
#                                early) -> imported here in Phase 8
#   <domain>, www, staging       ALIAS A/AAAA -> CloudFront (free queries)
#   origin, origin-staging       A records -> EC2 public IP, TTL 60. The
#                                server's boot script UPSERTs them on every
#                                start (D26); Terraform only creates them once
#                                and then ignores the value.
#   ACM cert (us-east-1)         <domain> + *.<domain>, DNS-validated.
#                                CloudFront only accepts us-east-1 certs.
# -----------------------------------------------------------------------------

# Phase 8: the zone already exists (created by hand in P0). Import it instead of
# creating a second one (a new zone = new name servers = broken domain).
# Uncomment in the ROOT module (import blocks must live in the root), e.g.:
#
# import {
#   to = module.dns.aws_route53_zone.this
#   id = "<hosted-zone-id>"     # aws route53 list-hosted-zones-by-name --dns-name <domain>
# }

resource "aws_route53_zone" "this" {
  name    = var.domain
  comment = "Docify (managed by Terraform)"
}

# --- origin records (owned by the server at runtime) ------------------------------

resource "aws_route53_record" "origin" {
  for_each = toset(var.origin_hostnames)

  zone_id = aws_route53_zone.this.zone_id
  name    = "${each.value}.${var.domain}"
  type    = "A"
  ttl     = 60
  # 192.0.2.1 = TEST-NET-1 documentation address (RFC 5737): a harmless
  # placeholder until the server boots and writes its real public IP.
  records = ["192.0.2.1"]

  lifecycle {
    # docify-dns.service on the instance UPSERTs the real IP at every boot.
    ignore_changes = [records]
  }
}

# --- CloudFront aliases --------------------------------------------------------------

locals {
  # host => which environment's distribution it points to
  alias_hosts = {
    (var.domain)            = "prod"
    "www.${var.domain}"     = "prod"
    "staging.${var.domain}" = "staging"
  }

  alias_records = merge([
    for host, env in local.alias_hosts : {
      for type in ["A", "AAAA"] : "${host}/${type}" => { host = host, env = env, type = type }
    }
  ]...)
}

resource "aws_route53_record" "alias" {
  for_each = local.alias_records

  zone_id = aws_route53_zone.this.zone_id
  name    = each.value.host
  type    = each.value.type

  alias {
    name                   = var.distributions[each.value.env].domain_name
    zone_id                = var.distributions[each.value.env].hosted_zone_id
    evaluate_target_health = false
  }
}

# --- ACM certificate for CloudFront (must be us-east-1) ---------------------------------

resource "aws_acm_certificate" "cloudfront" {
  provider = aws.us_east_1

  domain_name               = var.domain
  subject_alternative_names = ["*.${var.domain}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# The apex and the wildcard share the SAME validation CNAME, so two map entries
# write the same record; allow_overwrite makes that idempotent.
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id         = aws_route53_zone.this.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 300
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "cloudfront" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}
