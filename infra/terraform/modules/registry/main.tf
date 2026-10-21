# -----------------------------------------------------------------------------
# Module: registry
#
# ECR repository for the single backend image `docify/backend` (D14, §12.6).
#   - IMMUTABLE tags: a tag (= full git sha) can never be overwritten, so what
#     staging tested is exactly what prod runs.
#   - scan on push: free basic vulnerability scan for every new image.
#   - lifecycle: keep the newest 15 images (rollback window), expire the rest.
#   - prevent_destroy: survives "Off mode" (R10).
# The k3s node pulls with the kubelet ecr-credential-provider + instance role,
# so no image pull secrets are needed.
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the newest ${var.keep_images} images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.keep_images
      }
      action = { type = "expire" }
    }]
  })
}
