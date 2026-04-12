"""
01_load_refs.py
===============
Stage 01 — Load References

Fetches all brand and prompt library files from Google Drive,
assembles them into a single context.json object, and saves it
to S3 alongside the order.json for the sprint.

Inputs:  /runs/{sprint_id}/order.json (from S3, written by Stage 00)
         Google Drive /Brand/ folder     (brand voice, visual, compliance, writing style)
         Google Drive /Prompts/ folder   (copy playbook, examples)
         Google Drive /Performance/      (last_sprint.csv)
Outputs: /runs/{sprint_id}/context.json (to S3)

Trigger: Mind Studio calls this after Stage 00 completes.

Author:  CM (Creative Machine)
Version: 1.0
"""

import json
import os
import csv
import io
import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")

# Config path in S3 — used to look up folder IDs
CONFIG_S3_KEY = os.environ.get("CONFIG_PATH", "configs/upwork_config.json")

# Google service account JSON — stored in AWS Secrets Manager,
# injected as an env var by lambda_handler.py at cold start
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Brand files expected in Drive /Brand/ (configs folder)
# Keys become the field names in context.json["brand"]
BRAND_FILES = {
    "voice":         "voice_v1.0.md",
    "visual":        "visual_v1.0.json",
    "compliance":    "compliance_v1.0.md",
    "writing_style": "writing_style_v1.0.json",
}

# Prompt files expected in Drive /Prompts/ folder
# Keys become the field names in context.json["prompts"]
PROMPT_FILES = {
    "copy_playbook":         "copy_playbook_v1.0.md",
    "examples_prospecting":  "copy_examples_prospecting_v1.0.md",
    "examples_retargeting":  "copy_examples_retargeting_v1.0.md",
}

# Confirmed Drive folder IDs (from upwork_config.json)
# These are used as fallbacks if config can't be loaded from S3
DEFAULT_FOLDER_IDS = {
    "brand":       "1Jn42lIOVAir9QU-PAMGnDmO8gMsz6BGA",
    "prompts":     "1809GmNQFUIv1aK0pgYUC4_yG6_xRWeVv",
    "performance": "1hjTt6rvOHGby0StEeAJAsXFJl1fJpxNc",
    "sprints":     "1YpFoiUadL3pguWDJ_Uu4dasek1dj-mLY",
    "approved":    "1OO2Yg7n1E5UhTw3cEJ9mUN_GF0I5xnKv",
}

# ── DRIVE CLIENT ──────────────────────────────────────────────────────────────

def get_drive_service():
    """Build an authenticated Google Drive service client."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. "
            "This must be injected from AWS Secrets Manager."
        )
    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def find_file_in_folder(service, folder_id: str, filename: str) -> str | None:
    """
    Return the Drive file ID for `filename` inside `folder_id`.
    Returns None if the file is not found.
    """
    query = (
        f"'{folder_id}' in parents "
        f"and name = '{filename}' "
        f"and trashed = false"
    )
    result = service.files().list(
        q=query,
        fields="files(id, name)",
        pageSize=5
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def download_file_as_text(service, file_id: str) -> str:
    """Download a Drive file by ID and return its contents as a UTF-8 string."""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer.read().decode("utf-8")


# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_config_from_s3() -> dict:
    """Load upwork_config.json from S3. Returns empty dict on failure."""
    s3 = boto3.client("s3")
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=CONFIG_S3_KEY)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except Exception as e:
        print(f"[01_load_refs] WARNING: Could not load config from S3: {e}")
        return {}


def load_order_from_s3(sprint_id: str) -> dict:
    """Load order.json from S3 for the given sprint."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/order.json"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def save_context_to_s3(sprint_id: str, context: dict) -> None:
    """Save context.json to S3 at /runs/{sprint_id}/context.json"""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/context.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(context, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    print(f"[01_load_refs] context.json saved → s3://{S3_BUCKET}/{key}")


# ── PERFORMANCE DATA ──────────────────────────────────────────────────────────

def load_performance_csv(service, folder_id: str) -> list:
    """
    Download last_sprint.csv from the Performance folder and parse it.
    Returns a list of row dicts. Returns empty list if file not found.
    """
    file_id = find_file_in_folder(service, folder_id, "last_sprint.csv")
    if not file_id:
        print("[01_load_refs] last_sprint.csv not found in Performance folder — skipping")
        return []

    raw = download_file_as_text(service, file_id)
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    print(f"[01_load_refs] Loaded {len(rows)} rows from last_sprint.csv")
    return rows


# ── MAIN ──────────────────────────────────────────────────────────────────────

def load_refs(sprint_id: str) -> dict:
    """
    Main function. Fetches all reference files from Drive and
    assembles them into a context object for Stages 02 and 03.
    """
    print(f"[01_load_refs] Loading references for sprint: {sprint_id}")

    # Load config to get folder IDs (falls back to hardcoded defaults)
    config  = load_config_from_s3()
    folders = config.get("google_drive", {}).get("folders", {})

    brand_folder_id       = folders.get("brand",       DEFAULT_FOLDER_IDS["brand"])
    prompts_folder_id     = folders.get("prompts",     DEFAULT_FOLDER_IDS["prompts"])
    performance_folder_id = folders.get("performance", DEFAULT_FOLDER_IDS["performance"])

    # Load order from S3
    order = load_order_from_s3(sprint_id)
    print(f"[01_load_refs] Order loaded — platform: {order.get('platform')}, targeting: {order.get('targeting')}")

    # Build Drive service client
    service = get_drive_service()

    # ── Brand files ───────────────────────────────────────────────────────────
    brand = {}
    for key, filename in BRAND_FILES.items():
        file_id = find_file_in_folder(service, brand_folder_id, filename)
        if file_id:
            brand[key] = download_file_as_text(service, file_id)
            print(f"[01_load_refs] Loaded brand file: {filename}")
        else:
            print(f"[01_load_refs] WARNING: {filename} not found in Brand folder")
            brand[key] = ""

    # ── Prompt library files ──────────────────────────────────────────────────
    prompts = {}
    for key, filename in PROMPT_FILES.items():
        file_id = find_file_in_folder(service, prompts_folder_id, filename)
        if file_id:
            prompts[key] = download_file_as_text(service, file_id)
            print(f"[01_load_refs] Loaded prompt file: {filename}")
        else:
            print(f"[01_load_refs] WARNING: {filename} not found in Prompts folder")
            prompts[key] = ""

    # ── Performance data ──────────────────────────────────────────────────────
    performance = load_performance_csv(service, performance_folder_id)

    # ── Assemble context.json ─────────────────────────────────────────────────
    context = {
        "schema_version": "1.0",
        "sprint_id":      sprint_id,
        "order":          order,
        "brand":          brand,
        "prompts":        prompts,
        "performance": {
            "last_sprint_rows": performance,
            "row_count":        len(performance),
        },
        "pipeline_state": {
            **order.get("pipeline_state", {}),
            "stage_01_load_refs": "complete",
        },
    }

    # Save to S3
    save_context_to_s3(sprint_id, context)
    print(f"[01_load_refs] Stage 01 complete for sprint: {sprint_id}")

    return context


# ── LAMBDA ENTRY POINT ────────────────────────────────────────────────────────

def lambda_handler(event, context_obj):
    """
    AWS Lambda entry point.
    Mind Studio POSTs { "sprint_id": "..." } to trigger this stage.
    """
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        sprint_id = body.get("sprint_id")
        if not sprint_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "sprint_id is required"}),
            }

        context = load_refs(sprint_id)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success":              True,
                "sprint_id":            sprint_id,
                "brand_files_loaded":   list(context["brand"].keys()),
                "prompt_files_loaded":  list(context["prompts"].keys()),
                "performance_rows":     context["performance"]["row_count"],
            }),
        }

    except Exception as e:
        print(f"[01_load_refs] ERROR: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — requires GOOGLE_SERVICE_ACCOUNT_JSON to be set.

    Run with:
        GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }' python3 01_load_refs.py 2026-04-meta-test
    """
    import sys
    sprint_id = sys.argv[1] if len(sys.argv) > 1 else "2026-04-meta-test"

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        print("ERROR: Set GOOGLE_SERVICE_ACCOUNT_JSON to run local test")
        print("  export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... service account JSON ... }'")
        exit(1)

    load_refs(sprint_id)
