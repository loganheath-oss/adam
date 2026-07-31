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
demo_full_pipeline.py
=====================
End-to-end ADAM pipeline demo.

For one simulated order, generates 3 ads (one per photo-based visual style):
  1. Picks a photo from the Figma library (figma_library.pick_photo_for_asset)
  2. Generates on-brand copy via Anthropic's Claude API
  3. Pairs photo + copy into a complete ad concept
  4. Saves JSON output and prints a human-readable summary

Run with:
    SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())") \
    FIGMA_ACCESS_TOKEN='figd_...' \
    ANTHROPIC_API_KEY='sk-ant-...' \
    python3 pipeline/demo_full_pipeline.py
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Make figma_library importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figma_library import (
    pick_photo_for_asset,
    fetch_library_components,
    FIGMA_API_BASE,
    FIGMA_FILE_ID,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FIGMA_ACCESS_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5-20250929"  # Sonnet 4.5 for solid quality at low cost

REFS_PATH = Path(__file__).parent.parent / "configs" / "refs_context.json"
OUTPUT_DIR = Path(__file__).parent.parent / "runs"
EXPORTS_DIR = OUTPUT_DIR / "demo_exports"  # PNGs go here for the assembly plugin


def load_refs() -> dict:
    """Load the compiled reference context (brand voice, compliance, examples, etc.)."""
    if not REFS_PATH.exists():
        return {}
    with open(REFS_PATH) as f:
        return json.load(f)


def call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
    """Send a system + user message to Claude and return the text response."""
    if not ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY env var is not set.")

    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(
        ANTHROPIC_ENDPOINT, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"Anthropic API HTTP {e.code}: {err_body}")


def render_figma_node_as_png(node_id: str, asset_id: str, scale: int = 2) -> Path:
    """Render a Figma node as PNG via the image-rendering API and save to disk.

    Returns the local file path of the saved PNG.
    """
    if not FIGMA_ACCESS_TOKEN:
        raise EnvironmentError("FIGMA_ACCESS_TOKEN is required.")

    # Step 1: ask Figma to render the node, returns a temporary URL
    url = (
        f"{FIGMA_API_BASE}/images/{FIGMA_FILE_ID}"
        f"?ids={node_id}&format=png&scale={scale}"
    )
    req = urllib.request.Request(
        url, headers={"X-Figma-Token": FIGMA_ACCESS_TOKEN}, method="GET"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("err"):
        raise RuntimeError(f"Figma render error: {data['err']}")
    image_url = data.get("images", {}).get(node_id)
    if not image_url:
        raise RuntimeError(f"No image URL returned for node {node_id}")

    # Step 2: download the PNG from the temporary URL
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORTS_DIR / f"{asset_id}.png"
    with urllib.request.urlopen(image_url, timeout=60) as img_resp:
        with open(out_path, "wb") as f:
            f.write(img_resp.read())
    return out_path


def parse_json_response(raw: str) -> dict:
    """Strip markdown code fences and parse JSON from Claude's response."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def build_system_prompt(refs: dict) -> str:
    """Build a system prompt anchored in Upwork brand voice + compliance."""
    brand_voice = refs.get("brand_voice", "")[:2500]
    compliance = refs.get("compliance", "")[:1500]
    return f"""You are a senior copywriter for Upwork's Paid Acquisition team. You write direct-response paid social ad copy that drives clicks and signups. Match the brand voice exactly. Use only verified claims. Output valid JSON only.

===== UPWORK BRAND VOICE =====
{brand_voice}

===== COMPLIANCE RULES =====
{compliance}

Output requirements: return ONLY a single valid JSON object. No preamble, no explanation, no markdown code fences."""


def build_user_prompt(brief: str, visual_style: str, photo: dict, refs: dict) -> str:
    """Build the per-ad user prompt that pairs the brief, photo, and style."""
    examples = refs.get("prospecting_examples", "")[:2500]
    copy_bank = refs.get("smb_copy_bank", "")[:1500]

    photo_tags = photo.get("photo_tags", [])
    matched = photo.get("matched_tags_used", [])

    return f"""Generate ONE ad copy concept tailored to this specific photo and visual style.

===== ORDER BRIEF =====
{brief}

===== VISUAL STYLE =====
{visual_style}

===== PHOTO PAIRED WITH THIS COPY =====
The pipeline selected this photo from Upwork's approved brand library:
- Photo name: {photo.get('figma_asset_name', 'unknown')}
- Figma node ID: {photo.get('figma_asset_id', '')}
- Tags on this photo: {', '.join(photo_tags) if photo_tags else 'none'}

The copy MUST connect to what's actually in the photo. If the photo features a freelancer at a laptop, the copy can reference that. If it features a professional in a hotel, the copy can speak to business travelers, etc.

===== APPROVED COPY EXAMPLES (study these) =====
{examples}

===== APPROVED COPY BANK =====
{copy_bank}

===== YOUR ASSIGNMENT =====
Return ONE JSON object with exactly these keys:
- headline (max 40 chars) — punchy, specific, brand-aligned
- body_short (max 125 chars) — primary text short variant
- body_long (max 300 chars) — primary text long variant with more context
- description (max 25 chars) — secondary line
- cta (max 20 chars) — action button text from approved options
- concept_tag (short slug like "talent-speed-v1")
- why (one sentence — why this copy fits THIS photo specifically)

Return ONLY the JSON object."""


def run_demo():
    print("=" * 70)
    print("  ADAM PIPELINE — FULL DEMO (3 ADS)")
    print("=" * 70)

    if not ANTHROPIC_API_KEY:
        print("\nERROR: ANTHROPIC_API_KEY env var is not set.")
        sys.exit(1)

    # ── Simulated order ──────────────────────────────────────────────────────
    order = {
        "sprint_id":     "demo-2026-04-meta-9999",
        "driver":        "Logan Heath",
        "targeting":     "Prospecting",
        "brief":         "Showcase how Upwork helps small businesses hire skilled freelancers fast — emphasize speed, quality, and trust.",
        "platform":      "Meta",
        "delivery_date": "2026-05-01",
    }
    print("\nORDER:")
    for k, v in order.items():
        print(f"  {k:<14} {v}")

    # ── Load references ──────────────────────────────────────────────────────
    print("\n→ Loading reference documents...")
    refs = load_refs()
    ref_count = sum(1 for k, v in refs.items() if isinstance(v, str) and len(v) > 100)
    print(f"  {ref_count} reference documents loaded from configs/refs_context.json")

    # ── Fetch Figma library ──────────────────────────────────────────────────
    print("\n→ Fetching Figma library...")
    components = fetch_library_components()
    print(f"  {len(components)} tagged components available in the library")

    # ── Generate 3 ads ───────────────────────────────────────────────────────
    visual_styles = ["Lifestyle Photo", "Photo with Text", "Testimonial"]
    system_prompt = build_system_prompt(refs)
    ads = []

    for i, style in enumerate(visual_styles, 1):
        print()
        print("-" * 70)
        print(f"  AD #{i}: {style}")
        print("-" * 70)

        # Step 1: pick photo
        photo = pick_photo_for_asset(
            visual_style=style,
            order=order,
            sprint_id=order["sprint_id"],
            components=components,
        )
        if photo.get("needs_human_selection"):
            print(f"  No matching photo — flagged for human selection.")
            ads.append({
                "ad_number": i,
                "visual_style": style,
                "photo": photo,
                "copy": None,
                "error": "no matching photo",
            })
            continue

        print(f"  Photo:       {photo['figma_asset_name']}")
        print(f"  Node ID:     {photo['figma_asset_id']}")
        print(f"  Match:       {photo['match_strength']}")
        print(f"  Photo tags:  {', '.join(photo['photo_tags'])}")

        # Step 2: generate copy via Claude
        print(f"  → Generating copy via Claude {MODEL}...")
        user_prompt = build_user_prompt(order["brief"], style, photo, refs)
        try:
            raw = call_claude(system_prompt, user_prompt, max_tokens=800)
            copy = parse_json_response(raw)
        except Exception as e:
            print(f"  ✗ Copy generation failed: {e}")
            ads.append({
                "ad_number": i,
                "visual_style": style,
                "photo": photo,
                "copy": None,
                "error": str(e),
            })
            continue

        # Step 3: print the ad
        print(f"  HEADLINE:    {copy.get('headline')}")
        print(f"  BODY SHORT:  {copy.get('body_short')}")
        print(f"  BODY LONG:   {copy.get('body_long')}")
        print(f"  DESCRIPTION: {copy.get('description')}")
        print(f"  CTA:         {copy.get('cta')}")
        print(f"  Why this works: {copy.get('why')}")

        # Build a Figma URL so the user can click to view the picked photo
        figma_file_id = os.environ.get("FIGMA_FILE_ID", "DoDwumxELkuAuKKSP5p00e")
        node_id_url = photo["figma_asset_id"].replace(":", "-")
        figma_url = f"https://www.figma.com/design/{figma_file_id}?node-id={node_id_url}"
        print(f"  View photo:  {figma_url}")

        # The assembly plugin pulls the library image directly from Figma using
        # photo['figma_asset_id'], so we don't need to render PNGs locally.
        asset_id = f"demo-ad-{i:02d}"

        ads.append({
            "ad_number":    i,
            "asset_id":     asset_id,
            "visual_style": style,
            "photo":        photo,
            "figma_url":    figma_url,
            "copy":         copy,
        })

        time.sleep(1)  # polite pause between API calls

    # ── Save output ──────────────────────────────────────────────────────────
    output = {
        "order":        order,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model":        MODEL,
        "ads":          ads,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "demo_full_pipeline.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Also write a manifest CSV in the format the existing assembly plugin expects
    manifest_path = OUTPUT_DIR / "demo_full_pipeline_manifest.csv"
    manifest_columns = [
        "asset_id", "visual_style", "resolution",
        "headline", "Headline_On_Creative",
        "body", "Primary_Text_Short", "body_long",
        "description", "cta", "CTA",
        "concept_tag", "figma_node_id",
    ]
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_columns, extrasaction="ignore")
        writer.writeheader()
        for ad in ads:
            if not ad.get("copy"):
                continue
            copy = ad["copy"]
            row = {
                "asset_id":             ad["asset_id"],
                "visual_style":         ad["visual_style"],
                "resolution":           "1440x1440",
                "headline":             copy.get("headline", ""),
                "Headline_On_Creative": copy.get("headline", ""),
                "body":                 copy.get("body_short", ""),
                "Primary_Text_Short":   copy.get("body_short", ""),
                "body_long":            copy.get("body_long", ""),
                "description":          copy.get("description", ""),
                "cta":                  copy.get("cta", ""),
                "CTA":                  copy.get("cta", ""),
                "concept_tag":          copy.get("concept_tag", ""),
                "figma_node_id":        ad["photo"]["figma_asset_id"],
            }
            writer.writerow(row)

    print()
    print("=" * 70)
    successful = sum(1 for a in ads if a.get("copy"))
    print(f"  Demo complete. {successful}/3 ads generated successfully.")
    print(f"  JSON output:   {output_path}")
    print(f"  Manifest CSV:  {manifest_path}")
    print()
    print("  Next: open Figma, run the Upwork Pipeline Assembly plugin:")
    print(f"    1. Click 'Capture Template' (after selecting a template in Figma)")
    print(f"    2. Choose CSV: {manifest_path}")
    print(f"    3. Click 'Assemble' — library photos pull directly from Figma")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
