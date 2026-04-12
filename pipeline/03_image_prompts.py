"""
03_image_prompts.py
===================
Stage 03 — Image Prompt Generation

Reads copy_outputs.json and context.json from S3.
Branches on visual style per batch:

  Image Library  → Selects an approved asset from the Figma asset library
                   via the Figma API. No image generation needed.

  Illustration   → Calls the LLM Gateway to generate a Gemini Imagen prompt
                   for each asset. Passed to Stage 04 (generate_images).

  Text Based     → Generates a simple background texture/gradient prompt.
                   Minimal image complexity — text carries the ad.

Outputs image_prompts.csv to S3 with one row per image asset.

Inputs:  /runs/{sprint_id}/order.json
         /runs/{sprint_id}/context.json
         /runs/{sprint_id}/copy_outputs.json
Outputs: /runs/{sprint_id}/image_prompts.csv

Skipped: If order.includes_images is False (copy-only order).

Trigger: Mind Studio calls this in parallel with Stage 02.

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

S3_BUCKET             = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
LLM_GATEWAY_ENDPOINT  = os.environ.get("LLM_GATEWAY_ENDPOINT", "")
LLM_GATEWAY_API_KEY   = os.environ.get("LLM_GATEWAY_API_KEY", "")
LLM_GATEWAY_MODEL     = os.environ.get("LLM_GATEWAY_MODEL", "")
FIGMA_ACCESS_TOKEN    = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FIGMA_FILE_ID         = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")

# Fallback for local dev
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_ENDPOINT    = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL       = "claude-sonnet-4-20250514"
FIGMA_API_BASE        = "https://api.figma.com/v1"

MAX_TOKENS            = 1024   # Prompts are short
TEMPERATURE           = 0.5    # Lower for more consistent visual prompts
RETRY_ATTEMPTS        = 3
RETRY_DELAY_SECONDS   = 5

# Visual style routing
STYLE_IMAGE_LIBRARY   = "Image Library"
STYLE_ILLUSTRATION    = "Illustration"
STYLE_TEXT_BASED      = "Text Based"

# CSV column order for image_prompts.csv
CSV_COLUMNS = [
    "asset_id",
    "sprint_id",
    "batch_index",
    "platform",
    "format",
    "resolution",
    "visual_style",
    "generation_method",    # figma_library | gemini_generate | text_background
    "figma_asset_id",       # populated for Image Library style
    "figma_asset_url",      # populated for Image Library style
    "gemini_prompt",        # populated for Illustration and Text Based styles
    "negative_prompt",      # what to avoid in the image
    "aspect_ratio",         # e.g. "1:1", "4:5", "9:16"
    "linked_copy_asset_id", # asset_id from copy_outputs.json
    "concept_tag",          # from linked copy asset
]

# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_json_from_s3(sprint_id: str, filename: str) -> dict:
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def save_csv_to_s3(sprint_id: str, filename: str, rows: list[dict]) -> None:
    """Save a list of dicts as CSV to S3."""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=output.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    print(f"[03_img_prompts] Saved → s3://{S3_BUCKET}/{key}")


# ── LLM CLIENT ────────────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the LLM Gateway with retry. Returns raw response text."""
    if LLM_GATEWAY_ENDPOINT:
        endpoint    = LLM_GATEWAY_ENDPOINT
        api_key     = LLM_GATEWAY_API_KEY
        model       = LLM_GATEWAY_MODEL
        use_gateway = True
    elif ANTHROPIC_API_KEY:
        print("[03_img_prompts] WARNING: Using direct Anthropic API (local dev only)")
        endpoint    = ANTHROPIC_ENDPOINT
        api_key     = ANTHROPIC_API_KEY
        model       = ANTHROPIC_MODEL
        use_gateway = False
    else:
        raise EnvironmentError("No LLM endpoint configured.")

    payload = {
        "model":      model,
        "max_tokens": MAX_TOKENS,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_prompt}],
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            body = json.dumps(payload).encode("utf-8")
            headers = (
                {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
                if use_gateway else
                {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            )
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "content" in data:
                    return data["content"][0]["text"]
                elif "choices" in data:
                    return data["choices"][0]["message"]["content"]
                return str(data)

        except Exception as e:
            print(f"[03_img_prompts] LLM attempt {attempt} failed: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
            else:
                raise


# ── FIGMA LIBRARY CLIENT ──────────────────────────────────────────────────────

def fetch_figma_library_assets(concept_tag: str, platform: str, fmt: str) -> dict:
    """
    Query the Figma file's component library for an approved asset
    that matches the concept tag, platform, and format.

    Returns a dict with figma_asset_id and figma_asset_url,
    or empty strings if no match found.

    NOTE: This requires Brandon to have tagged assets in the Figma library
    with properties matching the tagging structure agreed on.
    """
    if not FIGMA_ACCESS_TOKEN:
        print("[03_img_prompts] FIGMA_ACCESS_TOKEN not set — skipping library lookup")
        return {"figma_asset_id": "", "figma_asset_url": ""}

    try:
        url = f"{FIGMA_API_BASE}/files/{FIGMA_FILE_ID}/components"
        req = urllib.request.Request(
            url,
            headers={"X-Figma-Token": FIGMA_ACCESS_TOKEN},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        components = data.get("meta", {}).get("components", [])

        # Simple matching: look for components whose name or description
        # contains relevant keywords from the concept tag, platform, or format.
        # Once Brandon establishes the tagging system this logic will be refined.
        search_terms = [
            t.lower() for t in
            concept_tag.replace("_", " ").split() + [platform.lower(), fmt.lower()]
        ]

        for component in components:
            name = component.get("name", "").lower()
            desc = component.get("description", "").lower()
            combined = f"{name} {desc}"

            if any(term in combined for term in search_terms):
                node_id  = component.get("node_id", "")
                thumb    = component.get("thumbnail_url", "")
                print(f"[03_img_prompts] Figma match: {component.get('name')} ({node_id})")
                return {
                    "figma_asset_id":  node_id,
                    "figma_asset_url": thumb,
                }

        # No match — log and return empty (Stage 05 will handle missing assets)
        print(f"[03_img_prompts] No Figma asset matched for: {concept_tag} / {platform} / {fmt}")
        return {"figma_asset_id": "", "figma_asset_url": ""}

    except Exception as e:
        print(f"[03_img_prompts] Figma library lookup failed: {e}")
        return {"figma_asset_id": "", "figma_asset_url": ""}


# ── PROMPT BUILDERS ───────────────────────────────────────────────────────────

ILLUSTRATION_SYSTEM = """You are a visual prompt engineer for Gemini Imagen.
You write precise, detailed image generation prompts for paid social ads.

Rules for every prompt:
- NO text, words, letters, or numbers in the image
- NO logos or brand marks (added in Figma template layer)
- Subject should have natural negative space at edges for text overlay
- Center subject with balanced composition
- Photorealistic style unless explicitly artistic
- Describe lighting, mood, color palette, and subject clearly
- Keep prompts under 200 words

Return ONLY the prompt text. No explanation. No preamble."""


def build_illustration_prompt(
    copy_asset: dict,
    batch: dict,
    context: dict,
) -> tuple[str, str]:
    """
    Generate a Gemini Imagen prompt for an Illustration style asset.
    Returns (gemini_prompt, negative_prompt).
    """
    headline     = copy_asset.get("headline", "")
    concept_tag  = copy_asset.get("concept_tag", "")
    platform     = batch["platform"]
    fmt          = batch["format"]
    resolution   = _get_resolution_label(batch)

    # Pull visual guidelines from context
    visual = context.get("brand", {}).get("visual", "")

    user_prompt = f"""Generate a Gemini Imagen prompt for a paid social ad image.

AD DETAILS:
- Platform: {platform}
- Format: {fmt}
- Resolution: {resolution}
- Ad concept: {concept_tag}
- Headline this image will support: "{headline}"

VISUAL GUIDELINES:
{visual[:1000] if visual else "Clean, professional, modern. Warm and human. Not stock-photo generic."}

The image will have text and a logo added on top via Figma template.
Generate a photorealistic scene that gives ample negative space for overlay elements.
Make it feel authentic, not staged."""

    raw_prompt = call_llm(ILLUSTRATION_SYSTEM, user_prompt).strip()

    negative_prompt = (
        "text, words, letters, numbers, logos, watermarks, "
        "blurry, low quality, distorted faces, unrealistic proportions, "
        "harsh shadows, oversaturated colors"
    )

    return raw_prompt, negative_prompt


def build_text_based_prompt(batch: dict, copy_asset: dict) -> tuple[str, str]:
    """
    Generate a simple background prompt for Text Based style assets.
    These are texture/gradient/pattern backgrounds — the ad is copy-driven.
    """
    concept_tag = copy_asset.get("concept_tag", "")
    platform    = batch["platform"]

    # Map common concept themes to background styles
    if any(w in concept_tag for w in ["speed", "fast", "quick", "instant"]):
        style = "dynamic diagonal gradient, deep indigo to electric green, clean and minimal"
    elif any(w in concept_tag for w in ["trust", "reliable", "quality", "verified"]):
        style = "solid deep navy background with subtle geometric texture, professional"
    elif any(w in concept_tag for w in ["growth", "scale", "business", "hire"]):
        style = "clean white background with soft warm amber gradient in corner"
    else:
        style = "modern gradient background, Upwork green (#14A800) to deep navy, minimal texture"

    prompt = (
        f"Abstract background for a digital advertisement. "
        f"{style}. "
        f"No text, no logos, no people, no objects. "
        f"Optimized for {platform} ad placement. "
        f"Clean negative space throughout for text overlay."
    )

    negative_prompt = "text, logos, people, objects, busy patterns, low quality"

    return prompt, negative_prompt


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _get_aspect_ratio(batch: dict) -> str:
    """Extract aspect ratio from first resolution in batch, or default to 1:1."""
    resolutions = batch.get("resolutions", [])
    if resolutions:
        return resolutions[0].get("ratio", "1:1")
    return "1:1"


def _get_resolution_label(batch: dict) -> str:
    """Get the size string from first resolution, e.g. '1080 x 1080'."""
    resolutions = batch.get("resolutions", [])
    if resolutions:
        return resolutions[0].get("size", "1080 x 1080")
    return "1080 x 1080"


def _get_primary_style(batch: dict) -> str:
    """Get the primary visual style from the batch."""
    styles = batch.get("visual_styles", [])
    if styles:
        return styles[0]
    return STYLE_ILLUSTRATION  # default to Illustration if unset


# ── MAIN ──────────────────────────────────────────────────────────────────────

def generate_image_prompts(sprint_id: str) -> dict:
    """
    Main function. Loads inputs from S3, routes each asset by visual style,
    writes image_prompts.csv to S3.
    """
    print(f"[03_img_prompts] Starting image prompt generation for sprint: {sprint_id}")

    # Load inputs
    order        = load_json_from_s3(sprint_id, "order.json")
    context      = load_json_from_s3(sprint_id, "context.json")

    # Skip if images not required
    if not order.get("includes_images", True):
        print("[03_img_prompts] Order is copy-only — skipping image prompt generation")
        return {"sprint_id": sprint_id, "skipped": True, "rows_generated": 0}

    # Load copy outputs (may not exist yet if running in parallel)
    # Try up to 3 times with a delay
    copy_outputs = None
    for attempt in range(3):
        try:
            copy_outputs = load_json_from_s3(sprint_id, "copy_outputs.json")
            break
        except Exception:
            if attempt < 2:
                print(f"[03_img_prompts] copy_outputs.json not ready yet, waiting... (attempt {attempt + 1})")
                time.sleep(10)
            else:
                print("[03_img_prompts] copy_outputs.json unavailable — generating prompts without copy context")
                copy_outputs = {"assets": []}

    # Build lookup: batch_index -> list of copy assets
    copy_by_batch: dict[int, list] = {}
    for asset in copy_outputs.get("assets", []):
        idx = asset.get("batch_index", 0)
        copy_by_batch.setdefault(idx, []).append(asset)

    # Generate image prompt rows
    all_rows = []

    for batch_index, batch in enumerate(order.get("batches", [])):
        platform     = batch["platform"]
        fmt          = batch["format"]
        quantity     = batch.get("quantity", 1)
        aspect_ratio = _get_aspect_ratio(batch)
        resolution   = _get_resolution_label(batch)
        primary_style = _get_primary_style(batch)

        print(f"[03_img_prompts] Batch {batch_index}: {platform}/{fmt} — style: {primary_style}")

        # Get linked copy assets for this batch
        copy_assets = copy_by_batch.get(batch_index, [])

        for i in range(quantity):
            copy_asset = copy_assets[i] if i < len(copy_assets) else {}
            asset_id   = f"{sprint_id}-b{batch_index:02d}-i{i+1:02d}"
            linked_id  = copy_asset.get("asset_id", "")
            concept_tag = copy_asset.get("concept_tag", f"concept_{i+1}")

            row = {
                "asset_id":           asset_id,
                "sprint_id":          sprint_id,
                "batch_index":        batch_index,
                "platform":           platform,
                "format":             fmt,
                "resolution":         resolution,
                "visual_style":       primary_style,
                "aspect_ratio":       aspect_ratio,
                "linked_copy_asset_id": linked_id,
                "concept_tag":        concept_tag,
                "figma_asset_id":     "",
                "figma_asset_url":    "",
                "gemini_prompt":      "",
                "negative_prompt":    "",
            }

            # ── Route by visual style ──────────────────────────────────────

            if primary_style == STYLE_IMAGE_LIBRARY:
                row["generation_method"] = "figma_library"
                figma = fetch_figma_library_assets(concept_tag, platform, fmt)
                row["figma_asset_id"]  = figma["figma_asset_id"]
                row["figma_asset_url"] = figma["figma_asset_url"]

            elif primary_style == STYLE_ILLUSTRATION:
                row["generation_method"] = "gemini_generate"
                prompt, neg = build_illustration_prompt(copy_asset, batch, context)
                row["gemini_prompt"]   = prompt
                row["negative_prompt"] = neg

            elif primary_style == STYLE_TEXT_BASED:
                row["generation_method"] = "text_background"
                prompt, neg = build_text_based_prompt(batch, copy_asset)
                row["gemini_prompt"]   = prompt
                row["negative_prompt"] = neg

            else:
                # Unknown style — default to Illustration
                print(f"[03_img_prompts] Unknown style '{primary_style}' — defaulting to Illustration")
                row["generation_method"] = "gemini_generate"
                prompt, neg = build_illustration_prompt(copy_asset, batch, context)
                row["gemini_prompt"]   = prompt
                row["negative_prompt"] = neg

            all_rows.append(row)

        # Small pause between batches
        if batch_index < len(order["batches"]) - 1:
            time.sleep(0.5)

    # Save CSV to S3
    save_csv_to_s3(sprint_id, "image_prompts.csv", all_rows)

    # Summarise by generation method
    methods = {}
    for row in all_rows:
        m = row["generation_method"]
        methods[m] = methods.get(m, 0) + 1

    print(f"[03_img_prompts] Stage 03 complete — {len(all_rows)} rows | {methods}")
    return {
        "sprint_id":       sprint_id,
        "skipped":         False,
        "rows_generated":  len(all_rows),
        "by_method":       methods,
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

        result = generate_image_prompts(sprint_id)
        return {"statusCode": 200, "body": json.dumps(result)}

    except Exception as e:
        print(f"[03_img_prompts] ERROR: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — validates routing logic without S3 or API calls.

    Run with:
        python3 03_image_prompts.py
    """
    import pprint

    # Test the style routing logic directly
    MOCK_BATCH_LIBRARY = {
        "platform": "Meta",
        "format": "Static Feed",
        "quantity": 1,
        "visual_styles": ["Image Library"],
        "resolutions": [{"size": "1080 x 1080", "ratio": "1:1"}],
        "carousel": False,
    }

    MOCK_BATCH_ILLUSTRATION = {
        "platform": "Meta",
        "format": "Static Feed",
        "quantity": 1,
        "visual_styles": ["Illustration"],
        "resolutions": [{"size": "1440 x 1800", "ratio": "4:5"}],
        "carousel": False,
    }

    MOCK_BATCH_TEXT = {
        "platform": "LinkedIn",
        "format": "Single Image",
        "quantity": 1,
        "visual_styles": ["Text Based"],
        "resolutions": [{"size": "1200 x 628", "ratio": "~1.91:1"}],
        "carousel": False,
    }

    MOCK_COPY_ASSET = {
        "asset_id":    "2026-04-meta-test-b00-c01",
        "headline":    "Hire your next expert in days, not weeks.",
        "body":        "Upwork connects you with top freelancers — fast.",
        "cta":         "Get started",
        "concept_tag": "speed_hire_quality",
    }

    MOCK_CONTEXT = {
        "brand": {
            "visual": "Clean, modern, human. Warm lighting. Authentic not staged."
        }
    }

    print("\n── ROUTING TEST ────────────────────────────────────────────")
    for batch, label in [
        (MOCK_BATCH_LIBRARY, "Image Library"),
        (MOCK_BATCH_ILLUSTRATION, "Illustration"),
        (MOCK_BATCH_TEXT, "Text Based"),
    ]:
        style = _get_primary_style(batch)
        print(f"\n{label}:")
        print(f"  style detected: {style}")
        print(f"  aspect_ratio:   {_get_aspect_ratio(batch)}")
        print(f"  resolution:     {_get_resolution_label(batch)}")

        if style == STYLE_TEXT_BASED:
            prompt, neg = build_text_based_prompt(batch, MOCK_COPY_ASSET)
            print(f"  prompt preview: {prompt[:120]}...")
        elif style == STYLE_ILLUSTRATION and ANTHROPIC_API_KEY:
            prompt, neg = build_illustration_prompt(MOCK_COPY_ASSET, batch, MOCK_CONTEXT)
            print(f"  prompt preview: {prompt[:120]}...")
        elif style == STYLE_IMAGE_LIBRARY:
            print("  → Would query Figma library (requires FIGMA_ACCESS_TOKEN)")

    print("\nDone.")
