# =============================================================================
# outputs.tf
# Values printed after terraform apply.
# The intake_endpoint is the most important — it goes in upwork_config.json
# and in Mind Studio as the webhook trigger.
# =============================================================================

output "intake_endpoint" {
  description = "HTTPS URL the order form POSTs to. Set in upwork_config.json and Mind Studio webhook."
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/submit-order"
}

output "health_endpoint" {
  description = "GET this URL to verify Lambda is alive. Also available via: make ping"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/health"
}

output "runs_bucket_name" {
  description = "S3 bucket where all pipeline run artifacts are stored."
  value       = aws_s3_bucket.runs.bucket
}

output "lambda_function_name" {
  description = "Lambda function name — use for log tailing: make logs"
  value       = aws_lambda_function.intake.function_name
}

output "lambda_role_arn" {
  description = "IAM role ARN — share with Haresh's team for security review."
  value       = aws_iam_role.lambda.arn
}

output "api_gateway_id" {
  description = "API Gateway ID — useful for debugging in the AWS console."
  value       = aws_apigatewayv2_api.intake.id
}

output "aws_account_id" {
  description = "AWS account ID this was deployed into — confirm with Haresh's team."
  value       = data.aws_caller_identity.current.account_id
}
