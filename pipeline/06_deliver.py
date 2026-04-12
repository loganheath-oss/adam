"""
06_deliver.py
=============
Stage 06 — Package & Deliver

Reads all assembled exports from S3, builds a full asset manifest,
uploads everything to the Google Drive Review Queue folder, and sends
a Slack notification to the review team.

This is the final automated stage. After this, a human reviews the
assets in Drive and approves or flags for revision.

Inputs:  /runs/{sprint_id}/exports/{asset_id}_final.png  (from S3, Stage 05)
         /runs/{sprint_id}/copy_outputs.json             (from S3, Stage 02)
         /runs/{sprint_id}/assembly_log.json             (from S3, Stage 05)
         /runs/{sprint_id}/order.json                    (from S3, Stage 00)

Outputs: Google Drive /Upwork/Sprints/{sprint_id}/Review-Queue/
           ├── {platform}/
           │     └── {asset_id}_final.png
           ├── asset_manifest.csv
           └── run_summary.json
         Slack notification to #paid-acquisition-pipeline

Trigger: Mind Studio calls this after Gate 5 (assembly review) is approved.

Author:  CM (Creative Machine)
Version: 1.0
"""

import csv
import io
import json
import os
import time
import urllib.request
import urllib.error
import boto3
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET                    = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
GOOGLE_SERVICE_ACCOUNT_JSON  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
SLACK_WEBHOOK_URL            = os.environ.get("SLACK_WEBHOOK_URL", "")
CONFIG_S3_KEY                = os.environ.get("CONFIG_PATH", "configs/upwork_config.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",   # create / upload files
    "https://www.googleapis.com/auth/drive.readonly" # read folder structure
]

# Confirmed Drive folder ID for review queue outputs
SPRINTS_FOLDER_ID = os.environ.get("SPRINTS_FOLDER_ID", "1YpFoiUadL3pguWDJ_Uu4dasek1dj-mLY")

# Manifest CSV columns
MANIFEST_COLUMNS = [
    "asset_id",
    "sprint_id",
    "platform",
    "format",
    "visual_style",
    "resolution",
    "aspect_ratio",
    "headline",
    "body",
    "cta",
    "concept_tag",
    "assembly_status",
    "drive_file_id",
    "drive_file_url",
    "generated_at",
]

# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_json_from_s3(sprint_id: str, filename: str) -> dict:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def load_export_from_s3(sprint_id: str, asset_id: str) -> bytes | None:
    """Load a final assembled PNG from S3. Returns None if not found."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/exports/{asset_id}_final.png"
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return resp["Body"].read()
    except Exception:
        return None


def list_export_asset_ids(sprint_id: str) -> list[str]:
    """List all asset IDs that have a final export in S3."""
    s3 = boto3.client("s3")
    prefix = f"runs/{sprint_id}/exports/"
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    asset_ids = []
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        filename = key.replace(prefix, "")
        if filename.endswith("_final.png"):
            asset_id = filename.replace("_final.png", "")
            asset_ids.append(asset_id)
    return asset_ids


def save_json_to_s3(sprint_id: str, filename: str, data: dict) -> None:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )


# ── GOOGLE DRIVE HELPERS ──────────────────────────────────────────────────────

def get_drive_service():
    """Build an authenticated Google Drive service client."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_drive_folder(service, name: str, parent_id: str) -> str:
    """Create a folder in Drive under parent_id. Returns the new folder ID."""
    metadata = {
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [parent_id],
    }
    folder = service.files().create(
        body=metadata,
        fields="id"
    ).execute()
    return folder["id"]


def get_or_create_folder(service, name: str, parent_id: str) -> str:
    """Get existing folder by name under parent, or create it."""
    query = (
        f"'{parent_id}' in parents "
        f"and name = '{name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    result = service.files().list(q=query, fields="files(id, name)").execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    return create_drive_folder(service, name, parent_id)


def upload_to_drive(
    service,
    name: str,
    content: bytes,
    mime_type: str,
    parent_id: str,
) -> tuple[str, str]:
    """
    Upload a file to Drive.
    Returns (file_id, web_view_link).
    """
    metadata = {
        "name":    name,
        "parents": [parent_id],
    }
    media = MediaIoBaseUpload(
        io.BytesIO(content),
        mimetype=mime_type,
        resumable=False,
    )
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink",
    ).execute()
    return file["id"], file.get("webViewLink", "")


# ── MANIFEST BUILDER ──────────────────────────────────────────────────────────

def build_manifest(
    order: dict,
    copy_outputs: dict,
    assembly_log: dict,
    drive_results: dict,
) -> list[dict]:
    """
    Build the asset manifest by joining:
    - order batches (platform, format, resolution)
    - copy outputs (headline, body, cta, concept_tag)
    - assembly log (status)
    - drive results (file_id, file_url)
    """
    # Build lookups
    copy_by_id = {a["asset_id"]: a for a in copy_outputs.get("assets", [])}
    assembly_by_id = {r["asset_id"]: r for r in assembly_log.get("results", [])}

    rows = []

    for batch_idx, batch in enumerate(order.get("batches", [])):
        platform = batch["platform"]
        fmt      = batch["format"]
        quantity = batch.get("quantity", 1)
        styles   = batch.get("visual_styles", [])

        for i in range(quantity):
            # Image asset ID convention matches Stage 03/04/05
            img_asset_id  = f"{order['sprint_id']}-b{batch_idx:02d}-i{i+1:02d}"
            copy_asset_id = f"{order['sprint_id']}-b{batch_idx:02d}-c{i+1:02d}"

            copy  = copy_by_id.get(copy_asset_id, {})
            asm   = assembly_by_id.get(img_asset_id, {})
            drive = drive_results.get(img_asset_id, {})

            resolutions = batch.get("resolutions", [{}])
            resolution  = resolutions[0].get("size", "") if resolutions else ""
            ratio       = resolutions[0].get("ratio", "") if resolutions else ""

            rows.append({
                "asset_id":        img_asset_id,
                "sprint_id":       order["sprint_id"],
                "platform":        platform,
                "format":          fmt,
                "visual_style":    styles[0] if styles else "",
                "resolution":      resolution,
                "aspect_ratio":    ratio,
                "headline":        copy.get("headline", ""),
                "body":            copy.get("body", ""),
                "cta":             copy.get("cta", ""),
                "concept_tag":     copy.get("concept_tag", ""),
                "assembly_status": asm.get("status", "unknown"),
                "drive_file_id":   drive.get("file_id", ""),
                "drive_file_url":  drive.get("file_url", ""),
                "generated_at":    datetime.now(timezone.utc).isoformat(),
            })

    return rows


def manifest_to_csv(rows: list[dict]) -> bytes:
    """Convert manifest rows to CSV bytes."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=MANIFEST_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


# ── SLACK NOTIFICATION ────────────────────────────────────────────────────────

def send_slack_notification(
    order: dict,
    summary: dict,
    review_folder_url: str,
) -> None:
    """
    POST a Slack Block Kit notification to #paid-acquisition-pipeline.
    Includes sprint details, asset counts, and a link to the Drive folder.
    """
    if not SLACK_WEBHOOK_URL:
        print("[06_deliver] SLACK_WEBHOOK_URL not set — skipping notification")
        return

    sprint_id   = order["sprint_id"]
    driver      = order.get("driver", "Unknown")
    platform    = order.get("platform", "")
    targeting   = order.get("targeting", "")
    delivery    = order.get("delivery_date", "")
    total       = summary.get("total_assets", 0)
    uploaded    = summary.get("uploaded", 0)
    pending     = summary.get("pending_template", 0)
    failed      = summary.get("failed", 0)

    status_emoji = "✅" if failed == 0 and pending == 0 else "⚠️" if failed == 0 else "❌"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{status_emoji} Review Queue Ready"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Sprint ID*\n`{sprint_id}`"},
                {"type": "mrkdwn", "text": f"*Driver*\n{driver}"},
                {"type": "mrkdwn", "text": f"*Platform*\n{platform}"},
                {"type": "mrkdwn", "text": f"*Targeting*\n{targeting}"},
                {"type": "mrkdwn", "text": f"*Delivery Date*\n{delivery}"},
                {"type": "mrkdwn", "text": f"*Assets*\n{uploaded}/{total} uploaded"},
            ]
        },
    ]

    # Add warning if any assets are pending or failed
    if pending > 0 or failed > 0:
        notes = []
        if pending > 0:
            notes.append(f"{pending} asset(s) pending Figma template — node IDs not yet set")
        if failed > 0:
            notes.append(f"{failed} asset(s) failed — check assembly_log.json")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚠️ *Notes*\n" + "\n".join(f"• {n}" for n in notes)
            }
        })

    # Review folder link
    if review_folder_url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Review Queue*\n<{review_folder_url}|Open in Google Drive>"
            }
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"Pipeline complete • Sprint `{sprint_id}` • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        }]
    })

    plain_text = (
        f"Review queue ready — Sprint {sprint_id} | "
        f"{uploaded}/{total} assets uploaded | "
        f"Driver: {driver}"
    )

    payload = json.dumps({
        "text":   plain_text,
        "blocks": blocks,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[06_deliver] Slack notification sent → HTTP {resp.getcode()}")
    except urllib.error.URLError as e:
        print(f"[06_deliver] WARNING: Slack notification failed: {e.reason}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def deliver(sprint_id: str) -> dict:
    """
    Main function. Packages all exports, uploads to Drive, sends notification.
    """
    print(f"[06_deliver] Starting delivery for sprint: {sprint_id}")

    # Load inputs
    order        = load_json_from_s3(sprint_id, "order.json")
    copy_outputs = load_json_from_s3(sprint_id, "copy_outputs.json")
    assembly_log = load_json_from_s3(sprint_id, "assembly_log.json")

    # Build Drive service
    service = get_drive_service()

    # ── Create sprint folder in Drive ────────────────────────────────────────
    # Structure: /Sprints/{sprint_id}/Review-Queue/
    sprint_folder_id = get_or_create_folder(service, sprint_id, SPRINTS_FOLDER_ID)
    review_folder_id = get_or_create_folder(service, "Review-Queue", sprint_folder_id)
    print(f"[06_deliver] Drive folder ready: /Sprints/{sprint_id}/Review-Queue/")

    # Get the review folder URL for the Slack notification
    folder_meta = service.files().get(
        fileId=review_folder_id,
        fields="webViewLink"
    ).execute()
    review_folder_url = folder_meta.get("webViewLink", "")

    # ── Upload final exports ─────────────────────────────────────────────────
    asset_ids    = list_export_asset_ids(sprint_id)
    drive_results = {}
    uploaded     = 0
    failed       = 0
    pending      = len([
        r for r in assembly_log.get("results", [])
        if r.get("status") == "pending_template"
    ])

    for asset_id in asset_ids:
        image_bytes = load_export_from_s3(sprint_id, asset_id)
        if not image_bytes:
            print(f"[06_deliver] No export found for {asset_id} — skipping")
            failed += 1
            continue

        # Get platform from assembly log for subfolder organisation
        asm = next(
            (r for r in assembly_log.get("results", []) if r.get("asset_id") == asset_id),
            {}
        )
        platform = asm.get("platform") or order.get("platform", "unknown")
        platform_slug = platform.lower().replace(" / ", "-").replace(" ", "-")

        # Create platform subfolder
        platform_folder_id = get_or_create_folder(service, platform_slug, review_folder_id)

        # Upload the PNG
        filename = f"{asset_id}_final.png"
        try:
            file_id, file_url = upload_to_drive(
                service,
                name=filename,
                content=image_bytes,
                mime_type="image/png",
                parent_id=platform_folder_id,
            )
            drive_results[asset_id] = {"file_id": file_id, "file_url": file_url}
            print(f"[06_deliver] Uploaded: {filename}")
            uploaded += 1
        except Exception as e:
            print(f"[06_deliver] Upload failed for {asset_id}: {e}")
            failed += 1

        time.sleep(0.5)  # Polite pause for Drive API

    # ── Build and upload manifest ────────────────────────────────────────────
    manifest_rows = build_manifest(order, copy_outputs, assembly_log, drive_results)
    manifest_csv  = manifest_to_csv(manifest_rows)

    try:
        manifest_file_id, _ = upload_to_drive(
            service,
            name="asset_manifest.csv",
            content=manifest_csv,
            mime_type="text/csv",
            parent_id=review_folder_id,
        )
        print(f"[06_deliver] Manifest uploaded (Drive ID: {manifest_file_id})")
    except Exception as e:
        print(f"[06_deliver] Manifest upload failed: {e}")
        manifest_file_id = ""

    # ── Build and upload run summary ─────────────────────────────────────────
    summary = {
        "schema_version":    "1.0",
        "sprint_id":         sprint_id,
        "delivered_at":      datetime.now(timezone.utc).isoformat(),
        "total_assets":      len(asset_ids) + pending,
        "uploaded":          uploaded,
        "failed":            failed,
        "pending_template":  pending,
        "review_folder_id":  review_folder_id,
        "review_folder_url": review_folder_url,
        "manifest_file_id":  manifest_file_id,
        "order_summary": {
            "driver":       order.get("driver"),
            "platform":     order.get("platform"),
            "targeting":    order.get("targeting"),
            "deliverable":  order.get("deliverable"),
            "delivery_date": order.get("delivery_date"),
        },
    }

    try:
        upload_to_drive(
            service,
            name="run_summary.json",
            content=json.dumps(summary, indent=2).encode("utf-8"),
            mime_type="application/json",
            parent_id=review_folder_id,
        )
        print("[06_deliver] Run summary uploaded")
    except Exception as e:
        print(f"[06_deliver] Run summary upload failed: {e}")

    # Save summary to S3 too
    save_json_to_s3(sprint_id, "run_summary.json", summary)

    # ── Send Slack notification ───────────────────────────────────────────────
    send_slack_notification(order, summary, review_folder_url)

    print(
        f"[06_deliver] Stage 06 complete — "
        f"uploaded: {uploaded}, failed: {failed}, pending: {pending}"
    )

    return summary


# ── LAMBDA ENTRY POINT ────────────────────────────────────────────────────────

def lambda_handler(event, context_obj):
    """AWS Lambda entry point."""
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        sprint_id = body.get("sprint_id")
        if not sprint_id:
            return {"statusCode": 400, "body": json.dumps({"error": "sprint_id is required"})}

        summary = deliver(sprint_id)
        status_code = 200 if summary["failed"] == 0 else 207
        return {"statusCode": status_code, "body": json.dumps(summary)}

    except Exception as e:
        print(f"[06_deliver] ERROR: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — validates manifest builder and Slack message format
    without calling Drive or Slack APIs.

    Run with:
        python3 06_deliver.py
    """
    import pprint

    MOCK_ORDER = {
        "sprint_id":     "2026-04-meta-test",
        "driver":        "Logan Heath",
        "platform":      "Meta",
        "targeting":     "Prospecting",
        "deliverable":   "images-copy",
        "delivery_date": "2026-04-18",
        "batches": [{
            "platform":      "Meta",
            "format":        "Static Feed",
            "quantity":      2,
            "visual_styles": ["Image Library"],
            "resolutions":   [{"size": "1080 x 1080", "ratio": "1:1"}],
        }]
    }

    MOCK_COPY = {
        "assets": [
            {
                "asset_id":    "2026-04-meta-test-b00-c01",
                "batch_index": 0,
                "headline":    "Hire your next expert in days.",
                "body":        "Upwork connects you with top freelancers fast.",
                "cta":         "Get started",
                "concept_tag": "speed_hire_quality",
            },
            {
                "asset_id":    "2026-04-meta-test-b00-c02",
                "batch_index": 0,
                "headline":    "5 million freelancers. One platform.",
                "body":        "Find the right talent for any project on Upwork.",
                "cta":         "Post a job for free",
                "concept_tag": "scale_and_choice",
            },
        ]
    }

    MOCK_ASSEMBLY = {
        "results": [
            {"asset_id": "2026-04-meta-test-b00-i01", "status": "success",  "platform": "Meta"},
            {"asset_id": "2026-04-meta-test-b00-i02", "status": "success",  "platform": "Meta"},
        ]
    }

    MOCK_DRIVE_RESULTS = {
        "2026-04-meta-test-b00-i01": {
            "file_id":  "fake_drive_id_1",
            "file_url": "https://drive.google.com/file/fake1",
        },
        "2026-04-meta-test-b00-i02": {
            "file_id":  "fake_drive_id_2",
            "file_url": "https://drive.google.com/file/fake2",
        },
    }

    print("\n── MANIFEST BUILD TEST ──────────────────────────────────────")
    rows = build_manifest(MOCK_ORDER, MOCK_COPY, MOCK_ASSEMBLY, MOCK_DRIVE_RESULTS)
    for row in rows:
        print(f"  {row['asset_id']} | {row['platform']} | {row['headline'][:40]} | {row['assembly_status']}")

    print("\n── SLACK MESSAGE PREVIEW ────────────────────────────────────")
    MOCK_SUMMARY = {
        "total_assets": 2, "uploaded": 2, "failed": 0, "pending_template": 0
    }
    # Build and print the plain text fallback
    sprint_id = MOCK_ORDER["sprint_id"]
    uploaded  = MOCK_SUMMARY["uploaded"]
    total     = MOCK_SUMMARY["total_assets"]
    driver    = MOCK_ORDER["driver"]
    print(f"  plain_text: Review queue ready — Sprint {sprint_id} | {uploaded}/{total} assets uploaded | Driver: {driver}")
    print(f"  channel: #paid-acquisition-pipeline")
    print(f"  status_emoji: ✅ (no failures)")

    print("\nDone.")
