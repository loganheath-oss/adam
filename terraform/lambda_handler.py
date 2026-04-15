"""
lambda_handler.py
=================
AWS Lambda entry point for the Upwork Creative Pipeline — Stage 00 (Intake).

How it works:
  1. At cold start, fetches all five secrets from AWS Secrets Manager and
     injects them into os.environ so 00_intake.py can read them normally.
  2. Receives API Gateway HTTP v2 events and routes them to the right handler.
  3. Returns properly formatted API Gateway proxy responses.

Architecture note:
  Handles the API Gateway event dict directly — no Flask, no Mangum.
  Simpler, faster cold starts, no extra dependencies.

Deploy path:
  Lives inside intake.zip alongside 00_intake.py.
  Built by: make package (from the terraform/ directory)
"""

import json
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# Secret injection — runs once per container (cold start only)
# =============================================================================

# Module-level Secrets Manager client — reused across warm invocations
_sm_client = None


def _get_sm_client():
    global _sm_client
    if _sm_client is None:
        _sm_client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _sm_client


def _fetch_secret(secret_name: str) -> str:
    """Fetch a plaintext secret from Secrets Manager. Raises on failure."""
    try:
        response = _get_sm_client().get_secret_value(SecretId=secret_name)
        return response.get("SecretString", "")
    except ClientError as e:
        logger.error(f"[lambda_handler] Failed to fetch secret '{secret_name}': {e}")
        raise


def _inject_secrets() -> list[str]:
    """
    Read secret NAMES from env vars, fetch actual VALUES from Secrets Manager,
    inject into os.environ. Returns list of any secrets that failed to load.

    env var holding the name  →  env var 00_intake.py reads
    """
    secret_map = {
        "MIND_STUDIO_WEBHOOK_SECRET": "MIND_STUDIO_WEBHOOK_URL",
        "WEBHOOK_SECRET_NAME":        "WEBHOOK_SECRET",
        "LLM_GATEWAY_KEY_SECRET":     "LLM_GATEWAY_API_KEY",
        "GOOGLE_SA_SECRET":           "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GEMINI_KEY_SECRET":          "GEMINI_API_KEY",
    }

    failed = []
    for name_env_var, target_env_var in secret_map.items():
        secret_name = os.environ.get(name_env_var)
        if not secret_name:
            logger.warning(f"[lambda_handler] Env var '{name_env_var}' not set — skipping")
            continue
        try:
            os.environ[target_env_var] = _fetch_secret(secret_name)
            logger.info(f"[lambda_handler] Secret loaded: {name_env_var} → {target_env_var}")
        except Exception:
            failed.append(name_env_var)

    return failed


# Inject secrets at module load (cold start). If any required secret fails,
# log loudly but don't crash — the handler will return a 503 instead.
_missing_secrets = _inject_secrets()
if _missing_secrets:
    logger.error(f"[lambda_handler] COLD START — secrets not loaded: {_missing_secrets}")

# Import pipeline logic AFTER secrets are injected
# 00_intake.py is copied into the zip as intake_00.py by: make package
try:
    import intake_00 as intake
    logger.info("[lambda_handler] intake_00 imported successfully")
except ImportError as e:
    logger.error(f"[lambda_handler] Could not import intake_00: {e}")
    intake = None

# =============================================================================
# Response helpers
# =============================================================================

def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def _ok(body: dict) -> dict:
    return _response(200, body)


def _error(status_code: int, message: str) -> dict:
    return _response(status_code, {"success": False, "error": message})


# =============================================================================
# Route handlers
# =============================================================================

def _handle_health(event: dict) -> dict:
    return _ok({
        "status": "ok",
        "service": "upwork-creative-pipeline-intake",
        "secrets_loaded": len(_missing_secrets) == 0,
        "missing_secrets": _missing_secrets,
    })


def _handle_submit_order(event: dict) -> dict:
    # Guard: abort early if cold-start secret injection failed
    if _missing_secrets:
        logger.error(f"[lambda_handler] Rejecting request — secrets not loaded: {_missing_secrets}")
        return _error(503, f"Service unavailable — secrets not loaded: {_missing_secrets}")

    if intake is None:
        return _error(503, "Service unavailable — intake module failed to load")

    # Parse the request body
    try:
        raw_body = event.get("body", "{}")
        if isinstance(raw_body, str):
            order_data = json.loads(raw_body)
        else:
            order_data = raw_body or {}
    except json.JSONDecodeError as e:
        logger.warning(f"[lambda_handler] Invalid JSON body: {e}")
        return _error(400, f"Invalid JSON: {e}")

    if not order_data:
        return _error(400, "Empty request body")

    logger.info(f"[lambda_handler] Processing order from: {order_data.get('driver', 'unknown')}")

    # Delegate to intake pipeline
    try:
        result = intake.process_intake(order_data)
        logger.info(f"[lambda_handler] Order processed: {result.get('sprint_id', '?')}")
        return _ok(result)
    except ValueError as e:
        # Validation errors from 00_intake.py (missing fields, bad data)
        logger.warning(f"[lambda_handler] Validation error: {e}")
        return _error(422, str(e))
    except Exception as e:
        logger.exception(f"[lambda_handler] Unexpected error processing order: {e}")
        return _error(500, f"Internal error: {str(e)}")


# =============================================================================
# Main handler — entry point Lambda calls on every invocation
# =============================================================================

def handler(event: dict, context) -> dict:
    method     = event.get("requestContext", {}).get("http", {}).get("method", "")
    raw_path   = event.get("rawPath", "/")

    logger.info(f"[lambda_handler] {method} {raw_path}")

    # Route
    if raw_path == "/health" and method == "GET":
        return _handle_health(event)

    if raw_path == "/submit-order" and method == "POST":
        return _handle_submit_order(event)

    # OPTIONS — handled by API Gateway CORS config but Lambda may receive it too
    if method == "OPTIONS":
        return _response(200, {})

    return _error(404, f"Not found: {method} {raw_path}")
