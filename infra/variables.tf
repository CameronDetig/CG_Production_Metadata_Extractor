variable "image_uri" {
  description = "Immutable ECR image URI for releases; null preserves the adoption baseline."
  type        = string
  default     = null
  validation {
    condition     = var.image_uri == null ? true : can(regex("^001879457662\\.dkr\\.ecr\\.us-east-1\\.amazonaws\\.com/cg-metadata-extractor@sha256:[a-f0-9]{64}$", var.image_uri))
    error_message = "Use a cg-metadata-extractor image URI pinned by SHA256 digest."
  }
}
