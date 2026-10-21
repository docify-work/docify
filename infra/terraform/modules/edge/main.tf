# -----------------------------------------------------------------------------
# Module: edge  (one CloudFront distribution per environment)
#
# CloudFront is the ONLY public entrypoint (D07). One hostname serves both:
#   /*      -> S3 web bucket (the React SPA), read through OAC
#   /api/*  -> the k3s server at origin[-staging].<domain> over HTTPS
# Same origin for SPA and API = first-party cookies and no CORS at all.
#
# Key choices (Master Doc §12.5):
#   - OAC (Origin Access Control): bucket stays private; only this
#     distribution may read it (bucket policy below).
#   - API origin: HTTPS only, TLS 1.2, 1 connection attempt, 3 s connect
#     timeout (a sleeping server fails fast -> the SPA shows "backend
#     sleeping"), 60 s response timeout (chat streams), secret header
#     X-Origin-Verify so the app can reject requests that skip CloudFront.
#   - /api/*: managed CachingDisabled + our own origin request policy: an explicit
#     header allow-list (never Host — it would break origin TLS/Ingress routing)
#     plus CloudFront-Viewer-Address, the only trustworthy client IP for rate
#     limits (X-Forwarded-For's first entry is client-controlled, V25).
#   - default: managed CachingOptimized + spa-rewrite function.
#   - NO custom error responses: they would turn API 404s into index.html.
#   - Price class 200 (includes India), HTTP/2 + HTTP/3, standard logs off.
# -----------------------------------------------------------------------------

locals {
  prefix        = "${var.name}-${var.env}"
  s3_origin_id  = "s3-web"
  api_origin_id = "api-origin"
}

# --- AWS-managed policies (looked up by name, never copied) -----------------------

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

resource "aws_cloudfront_origin_request_policy" "api" {
  name    = "${local.prefix}-api"
  comment = "Docify API: cookies, query strings, explicit headers + viewer address (no Host)"

  cookies_config {
    cookie_behavior = "all"
  }
  query_strings_config {
    query_string_behavior = "all"
  }
  headers_config {
    header_behavior = "whitelist"
    headers {
      items = [
        "Accept", "Accept-Language", "Content-Type", "Origin", "Referer", "User-Agent",
        "X-Docify-CSRF", "X-Request-Id",
        "CloudFront-Viewer-Address", "CloudFront-Viewer-Country",
      ]
    }
  }
}

# --- origin access control for the S3 bucket ------------------------------------------

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.prefix}-web"
  description                       = "CloudFront -> ${var.web_bucket.id}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# --- viewer-request function: www redirect + SPA rewrite ---------------------------------

resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${local.prefix}-spa-rewrite"
  comment = "www -> apex 301 and SPA routes -> /index.html"
  runtime = "cloudfront-js-2.0"
  code    = file("${path.module}/functions/spa-rewrite.js")
  publish = true
}

# --- security response headers (§10.5) -------------------------------------------------------

resource "aws_cloudfront_response_headers_policy" "security" {
  name    = "${local.prefix}-security-headers"
  comment = "HSTS, nosniff, referrer policy, frame deny, CSP (Master Doc §10.5)"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000 # 1 year
      include_subdomains         = true
      override                   = true
    }

    content_type_options {
      override = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    content_security_policy {
      content_security_policy = var.content_security_policy
      override                = true
    }
  }
}

# --- the distribution --------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  comment             = "Docify ${var.env}"
  aliases             = var.aliases
  default_root_object = "index.html"
  price_class         = var.price_class
  http_version        = "http2and3"
  is_ipv6_enabled     = true

  # Origin 1: the SPA in S3 (private, OAC-signed requests).
  origin {
    origin_id                = local.s3_origin_id
    domain_name              = var.web_bucket.regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  # Origin 2: the API on the k3s server (Traefik, Let's Encrypt cert).
  origin {
    origin_id           = local.api_origin_id
    domain_name         = var.origin_domain
    connection_attempts = 1
    connection_timeout  = 3

    custom_origin_config {
      http_port                = 80 # required by the API, never used (https-only)
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = var.origin_verify_value
    }
  }

  # /api/* -> server, never cached, all methods.
  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = local.api_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id   = aws_cloudfront_origin_request_policy.api.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  # Everything else -> S3 SPA.
  default_cache_behavior {
    target_origin_id           = local.s3_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    compress                   = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = { Env = var.env }
}

# --- web bucket policy: only this distribution may read; TLS only ------------------------------

data "aws_iam_policy_document" "web_bucket" {
  statement {
    sid       = "AllowCloudFrontOACRead"
    actions   = ["s3:GetObject"]
    resources = ["${var.web_bucket.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.this.arn]
    }
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [var.web_bucket.arn, "${var.web_bucket.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = var.web_bucket.id
  policy = data.aws_iam_policy_document.web_bucket.json
}
