variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run and Artifact Registry."
  type        = string
  default     = "asia-south1"
}

variable "service_name" {
  type    = string
  default = "vigil"
}

variable "env" {
  description = "demo = public synthetic-data showcase, prod = API keys required."
  type        = string
  default     = "demo"
  validation {
    condition     = contains(["demo", "prod"], var.env)
    error_message = "env must be demo or prod."
  }
}

variable "public_access" {
  description = "Allow unauthenticated invocation. Use true only for the synthetic-data demo."
  type        = bool
  default     = false
}

variable "llm_enabled" {
  description = "Let Vigil call Gemini on Vertex AI for explanations and semantic checks."
  type        = bool
  default     = false
}

variable "api_key_digests" {
  description = "Comma-separated SHA-256 hex digests of accepted API keys (never the keys themselves)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "audit_retention_days" {
  description = "Days to keep audit rows in BigQuery."
  type        = number
  default     = 400
}

variable "image" {
  description = "Initial container image. Cloud Build replaces it on every deploy."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
