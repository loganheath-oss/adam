# =============================================================================
# NON-CANONICAL — DO NOT PORT FROM, DO NOT RUN IN PRODUCTION (2026-07-31)
# This is the dormant AWS-bound scaffold. It LAGS pipeline/run_pipeline.py by
# months: old model IDs, old token caps, truncated ref slices, no legal
# blocklist, no structured output, no P&R segmentation. The audit found it
# would silently produce pre-July-spec copy if ever wired up. The ONLY port
# source is pipeline/run_pipeline.py. (00_intake.py and 01_load_refs.py are
# NOT part of this notice — intake is live and load-bearing.)
# =============================================================================

"""
04_generate_images.py
=====================
Stage 04 — Image Generation

Reads image_prompts.csv from S3. For each row where generation_method
is 'gemini_generate' or 'text_background', calls the Gemini Imagen API
(Nano Banana Pro — gemini-3-pro-image-preview) to generate a PNG.

Rows with generation_method='figma_library' are skipped — those assets
are handled in Stage 05 (Figma assembly) using the figma_asset_id from
the CSV.

Generated PNGs are saved to S3 at:
  /runs/{sprint_id}/images/{asset_id}.png

A generation_log.json is also written summarising results.

Inputs:  /runs/{sprint_id}/image_prompts.csv  (from S3, built by Stage 03)
Outputs: /runs/{sprint_id}/images/{asset_id}.png  (one per generated asset)
         /runs/{sprint_id}/generation_log.json

Trigger: Mind Studio calls this after Gate 4 (image prompt review) is approved.

Author:  CM (Creative Machine)
Version: 1.0
"""

import csv
import io
import json
import os
import time
import boto3
from datetime import datetime, timezone

# Gemini SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[04_gen_images] WARNING: google-genai not installed. Run: pip install google-genai")

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET           = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")

# Nano Banana Pro — highest quality Gemini image model
# Falls back to Imagen 4 if Nano Banana is unavailable
PRIMARY_MODEL       = "gemini-3-pro-image-preview"
FALLBACK_MODEL      = "imagen-4.0-generate-001"

# Generation settings
RETRY_ATTEMPTS      = 3
RETRY_DELAY_SECONDS = 10   # Imagen rate limits are strict — give it room
OUTPUT_FORMAT       = "png"

# Generation methods that require Gemini
GEMINI_METHODS      = {"gemini_generate", "text_background"}
FIGMA_METHOD        = "figma_library"

# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_csv_from_s3(sprint_id: str, filename: str) -> list[dict]:
    """Load a CSV file from S3, return as list of row dicts."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    content = resp["Body"].read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def save_image_to_s3(sprint_id: str, asset_id: str, image_bytes: bytes) -> str:
    """
    Save a PNG image to S3 at /runs/{sprint_id}/images/{asset_id}.png
    Returns the S3 key.
    """
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/images/{asset_id}.png"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    print(f"[04_gen_images] Image saved → s3://{S3_BUCKET}/{key}")
    return key


def save_json_to_s3(sprint_id: str, filename: str, data: dict) -> None:
    """Save a JSON file to S3."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    print(f"[04_gen_images] Log saved → s3://{S3_BUCKET}/{key}")


# ── GEMINI CLIENT ─────────────────────────────────────────────────────────────

def get_gemini_client():
    """Build and return an authenticated Gemini client."""
    if not GENAI_AVAILABLE:
        raise ImportError("google-genai package is required. Run: pip install google-genai")
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "This must be injected from AWS Secrets Manager."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_with_nano_banana(client, prompt: str, negative_prompt: str) -> bytes | None:
    """
    Generate an image using Nano Banana Pro (gemini-3-pro-image-preview).
    Returns raw PNG bytes, or None on failure.
    """
    try:
        contents = prompt
        if negative_prompt:
            contents = f"{prompt}\n\nAvoid: {negative_prompt}"

        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                return part.inline_data.data

        print(f"[04_gen_images] WARNING: No image data in Nano Banana response")
        return None

    except Exception as e:
        print(f"[04_gen_images] Nano Banana error: {e}")
        return None


def generate_with_imagen4(client, prompt: str, aspect_ratio: str) -> bytes | None:
    """
    Fallback: generate using Imagen 4.
    Returns raw PNG bytes, or None on failure.
    """
    try:
        # Normalise aspect ratio to Imagen format
        # Imagen accepts: "1:1", "9:16", "16:9", "3:4", "4:3"
        ar_map = {
            "1:1":      "1:1",
            "4:5":      "3:4",
            "9:16":     "9:16",
            "16:9":     "16:9",
            "~1.91:1":  "16:9",
            "4:3":      "4:3",
        }
        imagen_ratio = ar_map.get(aspect_ratio, "1:1")

        response = client.models.generate_images(
            model=FALLBACK_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=imagen_ratio,
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="ALLOW_ADULT",
                output_mime_type="image/png",
            )
        )

        if response.generated_images:
            return response.generated_images[0].image._image_bytes

        print("[04_gen_images] WARNING: No image data in Imagen 4 response")
        return None

    except Exception as e:
        print(f"[04_gen_images] Imagen 4 error: {e}")
        return None


def generate_image(client, row: dict) -> bytes | None:
    """
    Generate an image for a single CSV row.
    Tries Nano Banana Pro first, falls back to Imagen 4.
    Retries up to RETRY_ATTEMPTS times on failure.
    """
    prompt          = row.get("gemini_prompt", "")
    negative_prompt = row.get("negative_prompt", "")
    aspect_ratio    = row.get("aspect_ratio", "1:1")
    asset_id        = row.get("asset_id", "unknown")

    if not prompt:
        print(f"[04_gen_images] Skipping {asset_id} — no gemini_prompt")
        return None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        print(f"[04_gen_images] Generating {asset_id} (attempt {attempt}/{RETRY_ATTEMPTS})")

        # Try Nano Banana Pro first
        image_bytes = generate_with_nano_banana(client, prompt, negative_prompt)

        if image_bytes:
            return image_bytes

        # Fallback to Imagen 4
        print(f"[04_gen_images] Nano Banana failed — trying Imagen 4 fallback")
        image_bytes = generate_with_imagen4(client, prompt, aspect_ratio)

        if image_bytes:
            return image_bytes

        # Both failed — wait before retry
        if attempt < RETRY_ATTEMPTS:
            wait = RETRY_DELAY_SECONDS * attempt
            print(f"[04_gen_images] Both models failed — waiting {wait}s before retry")
            time.sleep(wait)

    print(f"[04_gen_images] FAILED: Could not generate image for {asset_id} after {RETRY_ATTEMPTS} attempts")
    return None


# ── MAIN ──────────────────────────────────────────────────────────────────────

def generate_images(sprint_id: str) -> dict:
    """
    Main function. Reads image_prompts.csv, generates images for all
    gemini_generate and text_background rows, saves PNGs to S3.
    Returns a summary dict.
    """
    print(f"[04_gen_images] Starting image generation for sprint: {sprint_id}")

    # Load CSV
    rows = load_csv_from_s3(sprint_id, "image_prompts.csv")
    print(f"[04_gen_images] Loaded {len(rows)} rows from image_prompts.csv")

    # Split rows by generation method
    to_generate = [r for r in rows if r.get("generation_method") in GEMINI_METHODS]
    skipped     = [r for r in rows if r.get("generation_method") == FIGMA_METHOD]

    print(f"[04_gen_images] To generate: {len(to_generate)} | Skipped (figma_library): {len(skipped)}")

    if not to_generate:
        print("[04_gen_images] No images to generate — all assets are from Figma library")
        return {
            "sprint_id":  sprint_id,
            "generated":  0,
            "skipped":    len(skipped),
            "failed":     0,
        }

    # Build Gemini client
    client = get_gemini_client()

    # Generate images
    results = []
    generated = 0
    failed    = 0

    for i, row in enumerate(to_generate):
        asset_id = row.get("asset_id", f"unknown_{i}")
        method   = row.get("generation_method", "")

        print(f"[04_gen_images] [{i+1}/{len(to_generate)}] {asset_id} ({method})")

        image_bytes = generate_image(client, row)

        if image_bytes:
            s3_key = save_image_to_s3(sprint_id, asset_id, image_bytes)
            results.append({
                "asset_id":  asset_id,
                "status":    "success",
                "s3_key":    s3_key,
                "method":    method,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            generated += 1
        else:
            results.append({
                "asset_id":  asset_id,
                "status":    "failed",
                "s3_key":    None,
                "method":    method,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed += 1

        # Rate limiting pause between generations
        if i < len(to_generate) - 1:
            time.sleep(3)

    # Save generation log
    log = {
        "schema_version": "1.0",
        "sprint_id":      sprint_id,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_rows":   len(rows),
            "generated":    generated,
            "skipped":      len(skipped),
            "failed":       failed,
        },
        "results": results,
    }
    save_json_to_s3(sprint_id, "generation_log.json", log)

    print(f"[04_gen_images] Stage 04 complete — generated: {generated}, failed: {failed}, skipped: {len(skipped)}")

    return {
        "sprint_id": sprint_id,
        "generated": generated,
        "skipped":   len(skipped),
        "failed":    failed,
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
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "sprint_id is required"}),
            }

        summary = generate_images(sprint_id)

        # 207 = partial success if any images failed
        status_code = 200 if summary["failed"] == 0 else 207
        return {
            "statusCode": status_code,
            "body": json.dumps(summary),
        }

    except Exception as e:
        print(f"[04_gen_images] ERROR: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — validates CSV routing logic without calling Gemini.
    Pass a sprint_id to test full generation (requires GEMINI_API_KEY).

    Run with:
        python3 04_generate_images.py              # routing test only
        GEMINI_API_KEY=... python3 04_generate_images.py  # full test
    """
    import sys

    # Test routing logic with mock CSV rows
    MOCK_ROWS = [
        {
            "asset_id":          "2026-04-meta-b00-i01",
            "generation_method": "gemini_generate",
            "gemini_prompt":     "A confident small business owner at a modern desk, warm office light, looking at laptop. No text or logos.",
            "negative_prompt":   "text, logos, blurry, low quality",
            "aspect_ratio":      "1:1",
        },
        {
            "asset_id":          "2026-04-meta-b00-i02",
            "generation_method": "text_background",
            "gemini_prompt":     "Abstract gradient background, deep navy to Upwork green. No text, no people.",
            "negative_prompt":   "text, people, logos",
            "aspect_ratio":      "1:1",
        },
        {
            "asset_id":          "2026-04-meta-b00-i03",
            "generation_method": "figma_library",
            "gemini_prompt":     "",
            "figma_asset_id":    "123:456",
            "aspect_ratio":      "1:1",
        },
    ]

    print("\n── ROUTING TEST ────────────────────────────────────────────")
    for row in MOCK_ROWS:
        method = row.get("generation_method")
        asset  = row.get("asset_id")
        if method in GEMINI_METHODS:
            print(f"  {asset} → GENERATE via Gemini ({method})")
            print(f"    Prompt preview: {row.get('gemini_prompt', '')[:80]}...")
        elif method == FIGMA_METHOD:
            print(f"  {asset} → SKIP (figma_library — handled in Stage 05)")

    to_generate = [r for r in MOCK_ROWS if r.get("generation_method") in GEMINI_METHODS]
    skipped     = [r for r in MOCK_ROWS if r.get("generation_method") == FIGMA_METHOD]
    print(f"\n  Total: {len(MOCK_ROWS)} rows | Generate: {len(to_generate)} | Skip: {len(skipped)}")

    # Full generation test if API key is set
    if GEMINI_API_KEY:
        sprint_id = sys.argv[1] if len(sys.argv) > 1 else "2026-04-meta-test"
        print(f"\n── LIVE GENERATION TEST (sprint: {sprint_id}) ──────────────")
        generate_images(sprint_id)
    else:
        print("\nSet GEMINI_API_KEY to run a live generation test.")
        print("Routing logic verified OK.")
