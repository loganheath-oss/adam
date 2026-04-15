# =============================================================================
# main.tf
# Upwork AI Creative Pipeline — Core Infrastructure
#
# Resources:
#   - S3 bucket              : run artifacts with lifecycle expiry
#   - IAM role               : least-privilege Lambda execution role
#   - Lambda function        : 00_intake — validates order, writes to S3, pings Mind Studio
#   - API Gateway HTTP v2    : HTTPS endpoint for order form
#   - CloudWatch log groups  : Lambda + API Gateway access logs
# =============================================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = var.tags
  }
}

# Current AWS account ID — used in IAM ARNs so they're not wildcarded
data "aws_caller_identity" "current" {}

locals {
  prefix     = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
}

# =============================================================================
# S3 — Run Artifacts Bucket
# Every pipeline run gets a prefix: runs/{sprint_id}/
# order.json, copy_outputs.json, image_prompts.csv, final PNGs all land here.
# =============================================================================

resource "aws_s3_bucket" "runs" {
  bucket = var.runs_bucket_name
  lifecycle {
    prevent_destroy = false  # flip to true once in production
  }
}

resource "aws_s3_bucket_versioning" "runs" {
  bucket = aws_s3_bucket.runs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "runs" {
  bucket                  = aws_s3_bucket.runs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Automatically delete run artifacts after N days — prevents unbounded storage costs
resource "aws_s3_bucket_lifecycle_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    id     = "expire-run-artifacts"
    status = "Enabled"
    filter { prefix = "runs/" }
    expiration { days = var.artifact_retention_days }
    noncurrent_version_expiration { noncurrent_days = 7 }
  }
}

# =============================================================================
# CloudWatch — Log Groups
# =============================================================================

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.prefix}-intake"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.prefix}-access"
  retention_in_days = var.log_retention_days
}

# =============================================================================
# IAM — Lambda Execution Role
# Least-privilege: S3 runs bucket, named Secrets Manager secrets, CloudWatch.
# VPC networking permissions only applied when vpc_subnet_ids is non-empty.
# =============================================================================

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "lambda_permissions" {

  # CloudWatch — write logs only to this function's log group
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  # S3 — runs bucket only, no other buckets
  statement {
    sid    = "S3RunsBucket"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.runs.arn,
      "${aws_s3_bucket.runs.arn}/*",
    ]
  }

  # Secrets Manager — five named secrets, exact account ID (not wildcard)
  statement {
    sid     = "SecretsManagerRead"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.mind_studio_webhook_secret_name}*",
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.webhook_secret_name}*",
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.llm_gateway_api_key_secret_name}*",
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.google_service_account_secret_name}*",
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.gemini_api_key_secret_name}*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.prefix}-lambda-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# VPC networking permissions — only attached when Lambda is VPC-configured.
# These EC2 actions do not support resource-level restrictions (AWS limitation),
# so the policy uses "*". Scoping it to a separate conditional attachment keeps
# the base policy clean for non-VPC deployments.
resource "aws_iam_role_policy" "lambda_vpc" {
  count  = length(var.vpc_subnet_ids) > 0 ? 1 : 0
  name   = "${local.prefix}-lambda-vpc-policy"
  role   = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "VpcNetworking"
      Effect = "Allow"
      Action = [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
      ]
      Resource = ["*"]
    }]
  })
}

# =============================================================================
# Lambda — 00_intake
# Receives order form POST, validates, generates sprint_id,
# writes order.json to S3, fires Mind Studio webhook.
# =============================================================================

resource "aws_lambda_function" "intake" {
  function_name = "${local.prefix}-intake"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_handler.handler"
  runtime       = "python3.11"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory
  filename      = var.lambda_zip_path

  # source_code_hash ensures Terraform detects code changes between deploys.
  # Without this, make apply after editing 00_intake.py would do nothing.
  source_code_hash = fileexists(var.lambda_zip_path) ? filebase64sha256(var.lambda_zip_path) : null

  # Cap simultaneous executions to prevent runaway invocations and cost spikes
  reserved_concurrent_executions = var.lambda_reserved_concurrency

  depends_on = [aws_cloudwatch_log_group.lambda]

  environment {
    variables = {
      # Pipeline config
      RUNS_BUCKET          = var.runs_bucket_name
      LLM_GATEWAY_ENDPOINT = var.llm_gateway_endpoint
      LLM_GATEWAY_MODEL    = var.llm_gateway_model

      # Secret NAMES — lambda_handler.py fetches actual values from Secrets Manager at cold start
      MIND_STUDIO_WEBHOOK_SECRET = var.mind_studio_webhook_secret_name
      WEBHOOK_SECRET_NAME        = var.webhook_secret_name
      LLM_GATEWAY_KEY_SECRET     = var.llm_gateway_api_key_secret_name
      GOOGLE_SA_SECRET           = var.google_service_account_secret_name
      GEMINI_KEY_SECRET          = var.gemini_api_key_secret_name
    }
  }

  # VPC config — only applied when vpc_subnet_ids is non-empty
  dynamic "vpc_config" {
    for_each = length(var.vpc_subnet_ids) > 0 ? [1] : []
    content {
      subnet_ids         = var.vpc_subnet_ids
      security_group_ids = var.vpc_security_group_ids
    }
  }
}

# =============================================================================
# API Gateway v2 (HTTP) — HTTPS endpoint for the order form
# Routes: POST /submit-order, GET /health
# =============================================================================

resource "aws_apigatewayv2_api" "intake" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"
  description   = "Upwork Creative Pipeline order intake API"

  cors_configuration {
    # Restrict to order form origin in production.
    # "*" is acceptable for alpha; tighten this before prod launch.
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Pipeline-Secret"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.intake.id
  name        = var.environment
  auto_deploy = true

  # Throttle to prevent the pipeline from being hammered
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      sourceIp       = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      protocol       = "$context.protocol"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_apigatewayv2_integration" "intake" {
  api_id                 = aws_apigatewayv2_api.intake.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.intake.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "submit_order" {
  api_id    = aws_apigatewayv2_api.intake.id
  route_key = "POST /submit-order"
  target    = "integrations/${aws_apigatewayv2_integration.intake.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.intake.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.intake.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.intake.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.intake.execution_arn}/*/*"
}
