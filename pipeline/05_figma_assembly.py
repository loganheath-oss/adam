"""
05_figma_assembly.py
====================
Stage 05 — Figma Assembly

For each image asset in image_prompts.csv:

  1. Looks up the correct Figma template frame using the platform,
     format, and aspect ratio from upwork_config.json

  2. Fills the 'image-slot' layer:
       - figma_library assets: uses the figma_asset_id from the CSV
         (the approved asset Brandon tagged in the library)
       - gemini_generate / text_background: uploads the PNG from S3
         and fills the frame via the Figma API

  3. Exports the assembled frame as a final-quality PNG via
     the Figma /images endpoint

  4. Saves the exported PNG to S3 at:
       /runs/{sprint_id}/exports/{asset_id}_final.png

Inputs:  /runs/{sprint_id}/image_prompts.csv      (from S3)
         /runs/{sprint_id}/images/{asset_id}.png  (from S3, Stage 04)
         configs/upwork_config.json               (from S3, for node IDs)
Outputs: /runs/{sprint_id}/exports/{asset_id}_final.png
         /runs/{sprint_id}/assembly_log.json

NOTE: The Figma node IDs in upwork_config.json will be PLACEHOLDER_NODE_ID
until Brandon completes the templates. The script handles this gracefully —
assets with placeholder node IDs are logged as 'pending_template' rather
than failing the run.

Trigger: Mind Studio calls this after Gate 4 is approved.

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

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET          = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
FIGMA_ACCESS_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FIGMA_FILE_ID      = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")
CONFIG_S3_KEY      = os.environ.get("CONFIG_PATH", "configs/upwork_config.json")

FIGMA_API_BASE     = "https://api.figma.com/v1"

# Layer name the pipeline targets — must match Brandon's templates exactly
IMAGE_SLOT_LAYER   = "image-slot"

RETRY_ATTEMPTS     = 3
RETRY_DELAY_SECONDS = 8

PLACEHOLDER_NODE   = "PLACEHOLDER_NODE_ID"

# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_csv_from_s3(sprint_id: str, filename: str) -> list[dict]:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    reader = csv.DictReader(io.StringIO(resp["Body"].read().decode("utf-8")))
    return list(reader)


def load_json_from_s3(key: str) -> dict:
    s3 = boto3.client("s3")
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def load_image_from_s3(sprint_id: str, asset_id: str) -> bytes | None:
    """Load a generated PNG from S3. Returns None if not found."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/images/{asset_id}.png"
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return resp["Body"].read()
    except s3.exceptions.NoSuchKey:
        print(f"[05_assembly] Image not found in S3: {key}")
        return None


def save_image_to_s3(sprint_id: str, asset_id: str, image_bytes: bytes) -> str:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/exports/{asset_id}_final.png"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    print(f"[05_assembly] Export saved → s3://{S3_BUCKET}/{key}")
    return key


def save_json_to_s3(sprint_id: str, filename: str, data: dict) -> None:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    print(f"[05_assembly] Log saved → s3://{S3_BUCKET}/{key}")


# ── FIGMA API HELPERS ─────────────────────────────────────────────────────────

def figma_get(path: str) -> dict:
    """Make an authenticated GET request to the Figma API."""
    url = f"{FIGMA_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={"X-Figma-Token": FIGMA_ACCESS_TOKEN},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def figma_post(path: str, payload: dict) -> dict:
    """Make an authenticated POST request to the Figma API."""
    url = f"{FIGMA_API_BASE}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "X-Figma-Token": FIGMA_ACCESS_TOKEN,
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_url(url: str) -> bytes:
    """Download bytes from a URL."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# ── NODE ID LOOKUP ────────────────────────────────────────────────────────────

def get_template_node_id(config: dict, platform: str, fmt: str, aspect_ratio: str) -> str | None:
    """
    Look up the Figma frame node ID for a given platform / format / aspect ratio
    from upwork_config.json.

    Returns None if the entry is a PLACEHOLDER_NODE_ID (template not built yet)
    or if the platform/format combination is not found.
    """
    templates = config.get("figma", {}).get("templates", {})

    # Normalise keys to match config structure
    platform_key = (
        platform.lower()
        .replace(" / ", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("3rd_party", "3rd_party_affiliate")
    )

    fmt_key = (
        fmt.lower()
        .replace(" (instagram)", "")
        .replace("(instagram)", "")
        .replace(" ", "_")
    )

    # Normalise aspect ratio to config key format: "1:1" → "1_1", "4:5" → "4_5"
    ratio_key = (
        aspect_ratio
        .replace(":", "_")
        .replace("~", "")
        .replace(".", "_")
        .replace(" ", "")
    )

    platform_templates = templates.get(platform_key, {})
    format_templates   = platform_templates.get(fmt_key, {})
    node_id            = format_templates.get(ratio_key, "")

    if not node_id or node_id == PLACEHOLDER_NODE:
        return None

    return node_id


# ── FIGMA IMAGE FILL ──────────────────────────────────────────────────────────

def upload_image_to_figma(image_bytes: bytes) -> str | None:
    """
    Upload an image to Figma's image storage.
    Returns the Figma image hash, or None on failure.

    Figma requires images to be uploaded before they can be used
    as fills. The hash is then used in the node fill update.
    """
    url = f"{FIGMA_API_BASE}/images/{FIGMA_FILE_ID}"
    req = urllib.request.Request(
        url,
        data=image_bytes,
        headers={
            "X-Figma-Token":  FIGMA_ACCESS_TOKEN,
            "Content-Type":   "image/png",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("meta", {}).get("images", {}).get("imageHash")
    except Exception as e:
        print(f"[05_assembly] Image upload to Figma failed: {e}")
        return None


def find_image_slot_node(file_id: str, frame_node_id: str) -> str | None:
    """
    Within a given frame, find the node named 'image-slot'.
    Returns the node ID, or None if not found.
    """
    try:
        data = figma_get(f"/files/{file_id}/nodes?ids={frame_node_id}")
        frame = data.get("nodes", {}).get(frame_node_id, {})
        document = frame.get("document", {})

        def search(node):
            if node.get("name") == IMAGE_SLOT_LAYER:
                return node.get("id")
            for child in node.get("children", []):
                result = search(child)
                if result:
                    return result
            return None

        return search(document)
    except Exception as e:
        print(f"[05_assembly] Could not find image-slot node: {e}")
        return None


def fill_image_slot(frame_node_id: str, image_hash: str) -> bool:
    """
    Update the 'image-slot' layer fill in the Figma frame
    with the uploaded image hash.
    Returns True on success.
    """
    # Find the image-slot node ID within the frame
    slot_node_id = find_image_slot_node(FIGMA_FILE_ID, frame_node_id)
    if not slot_node_id:
        print(f"[05_assembly] image-slot layer not found in frame {frame_node_id}")
        return False

    # Update the fill
    payload = {
        "nodes": {
            slot_node_id: {
                "document": {
                    "fills": [
                        {
                            "type":        "IMAGE",
                            "scaleMode":   "FILL",
                            "imageHash":   image_hash,
                            "imageRef":    image_hash,
                            "blendMode":   "NORMAL",
                            "opacity":     1,
                            "visible":     True,
                        }
                    ]
                }
            }
        }
    }

    try:
        figma_post(f"/files/{FIGMA_FILE_ID}/nodes", payload)
        return True
    except Exception as e:
        print(f"[05_assembly] Fill update failed: {e}")
        return False


def export_frame(frame_node_id: str, scale: float = 2.0) -> bytes | None:
    """
    Export a Figma frame as a PNG at 2x scale.
    Returns raw PNG bytes, or None on failure.
    """
    # Step 1: Request the export URL
    node_id_encoded = frame_node_id.replace(":", "%3A")
    path = f"/images/{FIGMA_FILE_ID}?ids={node_id_encoded}&scale={scale}&format=png"

    try:
        data = figma_get(path)
        image_url = data.get("images", {}).get(frame_node_id)

        if not image_url:
            print(f"[05_assembly] No export URL returned for frame {frame_node_id}")
            return None

        # Step 2: Download the exported image
        # Figma may take a moment to render — retry if URL returns 404
        for attempt in range(3):
            try:
                return download_url(image_url)
            except urllib.error.HTTPError as e:
                if e.code == 404 and attempt < 2:
                    time.sleep(5)
                else:
                    raise

    except Exception as e:
        print(f"[05_assembly] Frame export failed: {e}")
        return None


# ── ASSEMBLY LOGIC ────────────────────────────────────────────────────────────

def assemble_asset(row: dict, sprint_id: str, config: dict) -> dict:
    """
    Assemble a single asset:
    1. Look up the correct Figma template node ID
    2. Get the image (either from S3 or Figma library)
    3. Fill the image-slot layer
    4. Export the frame
    5. Save the export to S3

    Returns a result dict with status and s3_key.
    """
    asset_id  = row.get("asset_id", "unknown")
    platform  = row.get("platform", "")
    fmt       = row.get("format", "")
    ratio     = row.get("aspect_ratio", "1:1")
    method    = row.get("generation_method", "")

    print(f"[05_assembly] Assembling: {asset_id} ({platform}/{fmt} {ratio})")

    # ── Step 1: Get template node ID ──────────────────────────────────────────
    node_id = get_template_node_id(config, platform, fmt, ratio)

    if not node_id:
        print(f"[05_assembly] Template not ready for {platform}/{fmt}/{ratio} — marking as pending")
        return {
            "asset_id":  asset_id,
            "status":    "pending_template",
            "s3_key":    None,
            "note":      f"Node ID is PLACEHOLDER for {platform}/{fmt}/{ratio}. Build template first.",
        }

    # ── Step 2: Get the image bytes ───────────────────────────────────────────
    image_bytes = None

    if method == "figma_library":
        # Use the Figma library asset directly — fetch it via the Figma API
        figma_asset_id = row.get("figma_asset_id", "")
        if not figma_asset_id:
            print(f"[05_assembly] No figma_asset_id for {asset_id}")
            return {"asset_id": asset_id, "status": "failed", "s3_key": None,
                    "note": "figma_asset_id missing from image_prompts.csv"}
        try:
            export_data = figma_get(
                f"/images/{FIGMA_FILE_ID}?ids={figma_asset_id}&scale=2&format=png"
            )
            lib_url = export_data.get("images", {}).get(figma_asset_id)
            if lib_url:
                image_bytes = download_url(lib_url)
        except Exception as e:
            print(f"[05_assembly] Failed to fetch Figma library asset: {e}")

    else:
        # Load the Gemini-generated PNG from S3
        image_bytes = load_image_from_s3(sprint_id, asset_id)

    if not image_bytes:
        return {
            "asset_id": asset_id,
            "status":   "failed",
            "s3_key":   None,
            "note":     "Image bytes could not be loaded",
        }

    # ── Step 3: Upload image to Figma ─────────────────────────────────────────
    image_hash = upload_image_to_figma(image_bytes)
    if not image_hash:
        return {
            "asset_id": asset_id,
            "status":   "failed",
            "s3_key":   None,
            "note":     "Image upload to Figma failed",
        }

    # ── Step 4: Fill the image-slot layer ─────────────────────────────────────
    filled = fill_image_slot(node_id, image_hash)
    if not filled:
        return {
            "asset_id": asset_id,
            "status":   "failed",
            "s3_key":   None,
            "note":     "image-slot fill failed — check layer name in template",
        }

    # Allow Figma to re-render before exporting
    time.sleep(3)

    # ── Step 5: Export the assembled frame ────────────────────────────────────
    export_bytes = export_frame(node_id)
    if not export_bytes:
        return {
            "asset_id": asset_id,
            "status":   "failed",
            "s3_key":   None,
            "note":     "Frame export from Figma failed",
        }

    # ── Step 6: Save to S3 ────────────────────────────────────────────────────
    s3_key = save_image_to_s3(sprint_id, asset_id, export_bytes)

    return {
        "asset_id":   asset_id,
        "status":     "success",
        "s3_key":     s3_key,
        "node_id":    node_id,
        "method":     method,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────

def assemble_all(sprint_id: str) -> dict:
    """
    Main function. Assembles all assets for the sprint.
    """
    print(f"[05_assembly] Starting Figma assembly for sprint: {sprint_id}")

    if not FIGMA_ACCESS_TOKEN:
        raise EnvironmentError(
            "FIGMA_ACCESS_TOKEN is not set. "
            "Generate a token in Figma Settings → Security → Personal access tokens."
        )

    # Load inputs
    rows   = load_csv_from_s3(sprint_id, "image_prompts.csv")
    config = load_json_from_s3(CONFIG_S3_KEY)

    print(f"[05_assembly] Loaded {len(rows)} rows from image_prompts.csv")

    results      = []
    success      = 0
    failed       = 0
    pending      = 0

    for i, row in enumerate(rows):
        print(f"[05_assembly] [{i+1}/{len(rows)}]")

        result = assemble_asset(row, sprint_id, config)
        results.append(result)

        status = result["status"]
        if status == "success":
            success += 1
        elif status == "pending_template":
            pending += 1
        else:
            failed += 1

        # Respect Figma API rate limits
        if i < len(rows) - 1:
            time.sleep(2)

    # Save assembly log
    log = {
        "schema_version": "1.0",
        "sprint_id":      sprint_id,
        "assembled_at":   datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total":   len(rows),
            "success": success,
            "failed":  failed,
            "pending_template": pending,
        },
        "results": results,
    }
    save_json_to_s3(sprint_id, "assembly_log.json", log)

    print(
        f"[05_assembly] Stage 05 complete — "
        f"success: {success}, failed: {failed}, pending_template: {pending}"
    )

    return {
        "sprint_id": sprint_id,
        "success":   success,
        "failed":    failed,
        "pending_template": pending,
    }


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

        result = assemble_all(sprint_id)
        status_code = 200 if result["failed"] == 0 else 207
        return {"statusCode": status_code, "body": json.dumps(result)}

    except Exception as e:
        print(f"[05_assembly] ERROR: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — validates node ID lookup logic without calling Figma.

    Run with:
        python3 05_figma_assembly.py
    """
    import pprint

    # Mock config matching current upwork_config.json structure
    MOCK_CONFIG = {
        "figma": {
            "file_id": "DoDwumxELkuAuKKSP5p00e",
            "templates": {
                "meta": {
                    "static_feed": {
                        "1_1":  "PLACEHOLDER_NODE_ID",
                        "4_5":  "PLACEHOLDER_NODE_ID",
                        "9_16": "PLACEHOLDER_NODE_ID",
                    }
                }
            },
            "layer_names": {
                "image_frame": "image-slot"
            }
        }
    }

    # Test cases — expected: None (placeholder) until Brandon builds templates
    TEST_CASES = [
        ("Meta", "Static Feed", "1:1"),
        ("Meta", "Static Feed", "4:5"),
        ("Meta", "Carousel Feed", "1:1"),
        ("LinkedIn", "Single Image", "1:1"),
    ]

    print("\n── NODE ID LOOKUP TEST ──────────────────────────────────────")
    for platform, fmt, ratio in TEST_CASES:
        node_id = get_template_node_id(MOCK_CONFIG, platform, fmt, ratio)
        status  = "PLACEHOLDER — template not built yet" if not node_id else node_id
        print(f"  {platform} / {fmt} / {ratio} → {status}")

    print("\n── WHAT HAPPENS WHEN NODE IS PLACEHOLDER ────────────────────")
    print("  Assets are logged as 'pending_template' instead of failing.")
    print("  The run continues. Once Brandon adds real node IDs to")
    print("  upwork_config.json, re-run Stage 05 to assemble those assets.")

    print("\nDone.")
