# =============================================================================
# backend.tf
# Upwork AI Creative Pipeline — Terraform Remote State
#
# Why this matters:
#   Terraform state tracks what's deployed. Without a remote backend, state
#   lives on one person's laptop. If two engineers run terraform at the same
#   time they corrupt it. S3 + DynamoDB gives shared, locked, versioned state.
#
# Before running terraform init, Haresh's team must:
#   1. Create an S3 bucket for state (e.g. "upwork-adam-tf-state")
#      aws s3api create-bucket --bucket upwork-adam-tf-state --region us-east-1
#      aws s3api put-bucket-versioning \
#        --bucket upwork-adam-tf-state \
#        --versioning-configuration Status=Enabled
#
#   2. Create a DynamoDB table for state locking (e.g. "upwork-adam-tf-locks")
#      aws dynamodb create-table \
#        --table-name upwork-adam-tf-locks \
#        --attribute-definitions AttributeName=LockID,AttributeType=S \
#        --key-schema AttributeName=LockID,KeyType=HASH \
#        --billing-mode PAY_PER_REQUEST \
#        --region us-east-1
#
#   3. Update the bucket and dynamodb_table values below, then run:
#      terraform init
# =============================================================================

terraform {
  backend "s3" {
    bucket         = "PLACEHOLDER_tf_state_bucket"   # e.g. "upwork-adam-tf-state"
    key            = "adam/alpha/terraform.tfstate"
    # Terraform does not support variable interpolation in backend config,
    # so the key is hardcoded. Update this manually when deploying to staging or prod
    # (e.g. "adam/staging/terraform.tfstate") before running terraform init.
    region         = "us-east-1"
    dynamodb_table = "PLACEHOLDER_tf_lock_table"     # e.g. "upwork-adam-tf-locks"
    encrypt        = true
  }
}
