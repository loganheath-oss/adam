# =============================================================================
# variables.tf
# Upwork AI Creative Pipeline — Infrastructure Variables
#
# DO NOT edit defaults marked PLACEHOLDER_* here.
# Copy terraform.tfvars.example → terraform.tfvars, fill it in.
# Never commit terraform.tfvars to git.
# =============================================================================

variable "project" {
  description = "Project name prefix used on all AWS resource names."
  type        = string
  default     = "upwork-adam"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.project))
    error_message = "project must be lowercase letters, numbers and hyphens, 3-25 chars."
  }
}

variable "environment" {
  description = "Deployment environment (alpha, staging, prod)."
  type        = string
  default     = "alpha"
  validation {
    condition     = contains(["alpha", "staging", "prod"], var.environment)
    error_message = "environment must be one of: alpha, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "Must be a valid AWS region string e.g. us-east-1."
  }
}

# ── S3 ────────────────────────────────────────────────────────────────────────

variable "runs_bucket_name" {
  description = "Globally unique S3 bucket name for pipeline run artifacts."
  type        = string
  default     = "PLACEHOLDER_runs_bucket_name"
  # Example: "upwork-adam-runs-alpha" — must be unique across all AWS accounts.
  validation {
    condition     = var.runs_bucket_name != "PLACEHOLDER_runs_bucket_name"
    error_message = "Set runs_bucket_name in terraform.tfvars — see terraform.tfvars.example."
  }
}

variable "artifact_retention_days" {
  description = "Days before S3 run artifacts are automatically deleted. Prevents unbounded storage costs."
  type        = number
  default     = 90
  validation {
    condition     = var.artifact_retention_days >= 1
    error_message = "artifact_retention_days must be at least 1."
  }
}

# ── Lambda ────────────────────────────────────────────────────────────────────

variable "lambda_timeout" {
  description = "Lambda timeout in seconds. Gemini image gen + Pillow cropping needs headroom."
  type        = number
  default     = 60   # 30s was too tight — raised to 60
  validation {
    condition     = var.lambda_timeout >= 30 && var.lambda_timeout <= 900
    error_message = "lambda_timeout must be 30–900 seconds."
  }
}

variable "lambda_memory" {
  description = "Lambda memory in MB. Higher memory = faster CPU for image processing."
  type        = number
  default     = 1024   # 512 was marginal for Pillow — raised to 1024
  validation {
    condition     = var.lambda_memory >= 128 && var.lambda_memory <= 10240
    error_message = "lambda_memory must be between 128 and 10240 MB."
  }
}

variable "lambda_reserved_concurrency" {
  description = "Max simultaneous Lambda executions. Caps runaway invocations and costs. -1 = unreserved (uses account pool)."
  type        = number
  default     = 10
  validation {
    condition     = var.lambda_reserved_concurrency == -1 || var.lambda_reserved_concurrency >= 1
    error_message = "lambda_reserved_concurrency must be -1 (unreserved) or a positive integer. 0 throttles all invocations."
  }
}

variable "lambda_zip_path" {
  description = "Path to the packaged Lambda zip. Built by: make package"
  type        = string
  default     = "../intake/intake.zip"
}

# ── VPC (optional) ────────────────────────────────────────────────────────────
# Leave both empty to run Lambda outside a VPC. Only needed if Lambda must
# reach Upwork internal services over private networking.

variable "vpc_subnet_ids" {
  description = "VPC subnet IDs for Lambda. Empty list = no VPC."
  type        = list(string)
  default     = []
}

variable "vpc_security_group_ids" {
  description = "VPC security group IDs for Lambda. Empty list = no VPC."
  type        = list(string)
  default     = []
}

# ── LLM Gateway ───────────────────────────────────────────────────────────────
# Provided by Haresh's engineering team. Do NOT call Anthropic directly in prod.

variable "llm_gateway_endpoint" {
  description = "Upwork internal LLM Gateway endpoint URL."
  type        = string
  default     = "PLACEHOLDER_llm_gateway_endpoint"
  # Example: "https://llm-gateway.upwork.internal/v1/messages"
  validation {
    condition     = var.llm_gateway_endpoint != "PLACEHOLDER_llm_gateway_endpoint"
    error_message = "Set llm_gateway_endpoint in terraform.tfvars — get URL from Haresh's team."
  }
}

variable "llm_gateway_model" {
  description = "Model identifier as recognised by the LLM Gateway."
  type        = string
  default     = "PLACEHOLDER_llm_gateway_model"
  # Example: "claude-sonnet-4-20250514" — confirm exact string with Haresh's team.
  validation {
    condition     = var.llm_gateway_model != "PLACEHOLDER_llm_gateway_model"
    error_message = "Set llm_gateway_model in terraform.tfvars — confirm string with Haresh's team."
  }
}

# ── Secrets Manager — secret NAMES only (not values) ─────────────────────────
# Create these five secrets in AWS Secrets Manager BEFORE terraform apply.
# Lambda fetches actual values at cold start via lambda_handler.py.

variable "mind_studio_webhook_secret_name" {
  description = "Secrets Manager name for the Mind Studio webhook URL."
  type        = string
  default     = "upwork-adam/mind-studio-webhook-url"
}

variable "webhook_secret_name" {
  description = "Secrets Manager name for the pipeline webhook signing secret."
  type        = string
  default     = "upwork-adam/webhook-secret"
}

variable "llm_gateway_api_key_secret_name" {
  description = "Secrets Manager name for the LLM Gateway API key."
  type        = string
  default     = "upwork-adam/llm-gateway-api-key"
}

variable "google_service_account_secret_name" {
  description = "Secrets Manager name for the Google Drive service account JSON."
  type        = string
  default     = "upwork-adam/google-service-account"
}

variable "gemini_api_key_secret_name" {
  description = "Secrets Manager name for the Gemini API key."
  type        = string
  default     = "upwork-adam/gemini-api-key"
}

# ── Observability ─────────────────────────────────────────────────────────────

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 180, 365], var.log_retention_days)
    error_message = "Must be a valid CloudWatch retention period."
  }
}

# ── Tags ──────────────────────────────────────────────────────────────────────

variable "tags" {
  description = "Tags applied to every AWS resource for cost allocation and compliance."
  type        = map(string)
  default = {
    Project   = "upwork-adam"
    ManagedBy = "terraform"
    Team      = "paid-acquisition"
    Owner     = "creative-machine"
  }
}
