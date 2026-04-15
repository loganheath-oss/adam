# =============================================================================
# Makefile — Upwork Creative Pipeline Terraform helpers
#
# Run all commands from the terraform/ directory.
#
# Quick start:
#   make package   — build intake.zip (run after any code change)
#   make init      — initialise Terraform (once per fresh checkout)
#   make plan      — preview changes (no AWS resources touched)
#   make apply     — deploy to AWS
#   make logs      — tail Lambda logs live
#   make output    — print current deployed endpoint URLs
# =============================================================================

# Override with: make logs FUNCTION_NAME=upwork-adam-staging-intake
FUNCTION_NAME ?= $(shell terraform output -raw lambda_function_name 2>/dev/null || echo "upwork-adam-alpha-intake")
AWS_REGION    ?= us-east-1
PACKAGE_DIR   := ../intake/package
ZIP_PATH      := ../intake/intake.zip
PYTHON        := python3

# Detect if running on Apple Silicon — pip must target Lambda's x86_64 Linux
ARCH := $(shell uname -m)
ifeq ($(ARCH),arm64)
  PIP_PLATFORM := --platform manylinux2014_x86_64 --only-binary=:all:
  $(info → Apple Silicon detected: building for Lambda x86_64)
else
  PIP_PLATFORM :=
endif

.PHONY: package init validate fmt plan apply deploy destroy logs output clean help

## ── Build ────────────────────────────────────────────────────────────────────

## Build the Lambda deployment zip from pipeline/00_intake.py
package:
	@echo "→ Creating package directory..."
	@mkdir -p $(PACKAGE_DIR) ../intake
	@echo "→ Installing Python dependencies (targeting Lambda Linux x86_64)..."
	@pip install \
		boto3==1.34.0 \
		botocore==1.34.0 \
		requests==2.31.0 \
		google-auth==2.29.0 \
		google-api-python-client==2.125.0 \
		google-genai==0.5.0 \
		pillow==10.3.0 \
		$(PIP_PLATFORM) \
		--target $(PACKAGE_DIR) \
		--upgrade \
		--quiet
	@echo "→ Copying pipeline source files..."
	@cp ../pipeline/00_intake.py    $(PACKAGE_DIR)/intake_00.py
	@cp lambda_handler.py           $(PACKAGE_DIR)/lambda_handler.py
	@echo "→ Removing unnecessary files to keep zip lean..."
	@find $(PACKAGE_DIR) -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
	@find $(PACKAGE_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(PACKAGE_DIR) -name "*.pyc" -delete 2>/dev/null || true
	@echo "→ Zipping package..."
	@cd $(PACKAGE_DIR) && zip -r ../../intake/intake.zip . -q
	@echo "✓ Package built: $(ZIP_PATH) ($(shell du -sh $(ZIP_PATH) | cut -f1))"

## ── Terraform lifecycle ──────────────────────────────────────────────────────

## Initialise Terraform — run once after fresh checkout or backend change
init:
	terraform init

## Validate Terraform config syntax (no AWS calls)
validate:
	terraform validate

## Format all .tf files to canonical style
fmt:
	terraform fmt -recursive

## Preview what will be created or changed — no AWS resources touched
plan: validate
	terraform plan

## Deploy to AWS (builds package first)
apply: package validate
	terraform apply

## Build package + apply in one step — use this for routine deploys
deploy: apply

## Tear down all resources — DESTRUCTIVE, requires typing 'yes'
destroy:
	@echo "WARNING: This will delete ALL pipeline infrastructure."
	terraform destroy

## ── Operations ───────────────────────────────────────────────────────────────

## Tail Lambda CloudWatch logs (live, Ctrl+C to stop)
logs:
	aws logs tail /aws/lambda/$(FUNCTION_NAME) \
		--follow \
		--format short \
		--region $(AWS_REGION)

## Print current deployed endpoint URLs and resource names
output:
	terraform output

## Test the live health endpoint
ping:
	@ENDPOINT=$$(terraform output -raw intake_endpoint 2>/dev/null | sed 's|/submit-order||'); \
	if [ -z "$$ENDPOINT" ]; then echo "No endpoint found — has terraform apply run?"; exit 1; fi; \
	echo "→ GET $${ENDPOINT}/health"; \
	curl -s "$${ENDPOINT}/health" | python3 -m json.tool

## ── Cleanup ──────────────────────────────────────────────────────────────────

## Remove build artifacts (zip and package dir)
clean:
	@rm -rf $(PACKAGE_DIR) $(ZIP_PATH)
	@echo "✓ Build artifacts removed"

## ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Upwork Creative Pipeline — Terraform Makefile"
	@echo "=============================================="
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /'
	@echo ""
