# -----------------------------------------------------------------------------
# Phase 8: adopt resources that were created by hand in Phase 0 (§12.2):
#   - Route 53 hosted zone (P0.6) - needed early for SES verification
#   - SES domain identity + DKIM/MAIL FROM/DMARC records (P0.7)
#
# Uncomment, fill the <placeholders> LOCALLY (don't commit ids), run
# `terraform plan` -> expect "N to import". After the apply, comment them out
# again. Record import ids: "<zone-id>_<record-name>_<type>".
# Any record that did NOT exist yet is simply created - no import needed.
# -----------------------------------------------------------------------------

# import {
#   to = module.dns.aws_route53_zone.this
#   id = "<hosted-zone-id>"
# }

# import {
#   to = module.ses.aws_sesv2_email_identity.this
#   id = "docify.work"
# }

# import {
#   to = module.ses.aws_sesv2_email_identity_mail_from_attributes.this
#   id = "docify.work"
# }

# Easy DKIM records (tokens: aws sesv2 get-email-identity --email-identity docify.work)
# import {
#   to = module.ses.aws_route53_record.dkim[0]
#   id = "<hosted-zone-id>_<token-1>._domainkey.docify.work_CNAME"
# }
# import {
#   to = module.ses.aws_route53_record.dkim[1]
#   id = "<hosted-zone-id>_<token-2>._domainkey.docify.work_CNAME"
# }
# import {
#   to = module.ses.aws_route53_record.dkim[2]
#   id = "<hosted-zone-id>_<token-3>._domainkey.docify.work_CNAME"
# }

# import {
#   to = module.ses.aws_route53_record.mail_from_mx
#   id = "<hosted-zone-id>_mail.docify.work_MX"
# }
# import {
#   to = module.ses.aws_route53_record.mail_from_spf
#   id = "<hosted-zone-id>_mail.docify.work_TXT"
# }
# import {
#   to = module.ses.aws_route53_record.dmarc
#   id = "<hosted-zone-id>__dmarc.docify.work_TXT"
# }
