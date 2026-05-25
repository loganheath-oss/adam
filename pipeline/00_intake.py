"""
00_intake.py
============
Stage 00 — Intake & Validation

Receives the order form submission from Mind Studio (via webhook),
validates all required fields, generates a sprint_id, writes a
structured order.json to S3, then POSTs back to Mind Studio to
trigger Stage 01 (load_refs).

Inputs:  JSON payload from the order form (via Mind Studio webhook)
Outputs: /runs/{sprint_id}/order.json saved to S3
         POST to Mind Studio webhook with sprint_id to trigger Stage 01

Author:  CM (Creative Machine)
Version: 1.0
"""

import json
import os
import re
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET            = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
MIND_STUDIO_WEBHOOK  = os.environ.get("MIND_STUDIO_WEBHOOK_URL", "")
WEBHOOK_SECRET       = os.environ.get("WEBHOOK_SECRET", "")
SCHEMA_VERSION       = "1.0"

# ── VALIDATION ────────────────────────────────────────────────────────────────

REQUIRED_TOP_LEVEL = ["delivery_date", "driver", "targeting", "deliverable", "batches"]

VALID_TARGETING    = {"Prospecting", "Retargeting", "Prospecting and Retargeting"}
VALID_DELIVERABLE  = {"images-copy", "images-only", "copy-only"}

VALID_PLATFORMS = {
    "Meta", "LinkedIn", "Reddit", "YouTube", "3rd Party / Affiliate", "Google / Bing"
}

# Visual styles supported by the pipeline (all 24 from the order form)
VALID_STYLES = {
    "Graphic with Text", "Split Screen", "Us vs Them",
    "Photo with Text", "Lifestyle Photo", "Testimonial",
    "Social Media Profile", "Pie Chart", "Hybrid",
    "Search Results", "Search Bar with Talent Badge", "Text Only",
    "Chat Bubble", "Notification", "Reminder",
    "Device UI", "Platform UI", "Meme",
    "Sticky Note", "Poll", "Tweet / Post Mockup",
    "Text with Button", "Text with Button and Cursor",  # latter is legacy alias
    "Talent Profile", "Bespoke",
    # Pipeline routing aliases
    "Image Library", "Illustration", "Text Based",
    # Legacy names
    "Graphic Hero", "Graph/Chart", "Photo Bio", "Text Hero", "UI Hero",
    "Other"
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Case-insensitive lookup of canonical style names
_STYLE_LOOKUP = {s.lower(): s for s in VALID_STYLES}


def normalize_style(raw: str) -> str | None:
    """Normalize a form-supplied visual style to a canonical pipeline style.

    Strips parenthetical descriptors (e.g. "Lifestyle Photo (full bleed)" ->
    "Lifestyle Photo") and matches case-insensitively. Returns the canonical
    name, or None if no match.
    """
    if not isinstance(raw, str):
        return None
    base = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    return _STYLE_LOOKUP.get(base.lower())


def validate_payload(payload: dict) -> list[str]:
    """
    Validate the incoming order form payload.
    Returns a list of error strings (empty = valid).
    """
    errors = []

    # ── Top-level required fields
    for field in REQUIRED_TOP_LEVEL:
        if not payload.get(field):
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors  # Stop early if basics are missing

    # ── Delivery date format
    delivery_date = payload.get("delivery_date", "")
    if not DATE_PATTERN.match(delivery_date):
        errors.append(f"delivery_date must be YYYY-MM-DD format, got: {delivery_date!r}")

    # ── Targeting
    targeting = payload.get("targeting", "")
    if targeting not in VALID_TARGETING:
        errors.append(f"targeting must be one of {sorted(VALID_TARGETING)}, got: {targeting!r}")

    # ── Deliverable
    deliverable = payload.get("deliverable", "")
    if deliverable not in VALID_DELIVERABLE:
        errors.append(f"deliverable must be one of {sorted(VALID_DELIVERABLE)}, got: {deliverable!r}")

    # ── Batches
    batches = payload.get("batches", [])
    if not isinstance(batches, list) or len(batches) == 0:
        errors.append("batches must be a non-empty list")
        return errors

    for i, batch in enumerate(batches):
        prefix = f"batches[{i}]"

        # Platform
        platform = batch.get("platform", "")
        if not platform:
            errors.append(f"{prefix}: missing platform")
        elif platform not in VALID_PLATFORMS:
            errors.append(f"{prefix}: unknown platform {platform!r}")

        # Format
        if not batch.get("format"):
            errors.append(f"{prefix}: missing format")

        # Visual styles — normalize form-supplied names (e.g. strip
        # "(full bleed)" suffix, fix casing) before validating, and write
        # the canonical names back so downstream stages see values they know.
        styles = batch.get("visual_styles", [])
        if not styles:
            errors.append(f"{prefix}: at least one visual_style is required")
        else:
            normalized: list[str] = []
            for style in styles:
                canonical = normalize_style(style)
                if canonical is None:
                    errors.append(f"{prefix}: unknown visual_style {style!r}")
                    normalized.append(style)
                else:
                    normalized.append(canonical)
            batch["visual_styles"] = normalized

            # Canonicalize style_quantities keys so downstream lookups by
            # canonical style name find the right quantity.
            raw_qtys = batch.get("style_quantities") or {}
            if isinstance(raw_qtys, dict) and raw_qtys:
                merged: dict[str, int] = {}
                for k, v in raw_qtys.items():
                    canonical = normalize_style(k) or k
                    try:
                        qty = int(v)
                    except (TypeError, ValueError):
                        qty = 0
                    merged[canonical] = merged.get(canonical, 0) + qty
                batch["style_quantities"] = merged

        # Resolutions
        resolutions = batch.get("resolutions", [])
        if not resolutions:
            errors.append(f"{prefix}: at least one resolution is required")

        # Quantity
        qty = batch.get("quantity")
        if qty is None:
            errors.append(f"{prefix}: missing quantity")
        elif not isinstance(qty, int) or qty < 1:
            errors.append(f"{prefix}: quantity must be a positive integer, got: {qty!r}")

        # Carousel slide count (only required if carousel=True)
        if batch.get("carousel"):
            slides = batch.get("carousel_slides")
            if slides is None:
                errors.append(f"{prefix}: carousel_slides is required when carousel=True")
            elif not isinstance(slides, int) or not (2 <= slides <= 10):
                errors.append(f"{prefix}: carousel_slides must be an integer between 2 and 10")

        # Audience (only required for Prospecting and Retargeting orders)
        if targeting == "Prospecting and Retargeting":
            if not batch.get("audience"):
                errors.append(f"{prefix}: audience is required for Prospecting and Retargeting orders")

    return errors


# ── SPRINT ID ─────────────────────────────────────────────────────────────────

def generate_sprint_id(payload: dict) -> str:
    """
    Generate a unique sprint ID.
    Format: YYYY-MM-{platform_slug}-{4_char_uid}
    Example: 2026-04-meta-a3f2
    """
    now = datetime.now(timezone.utc)
    year_month = now.strftime("%Y-%m")

    # Get primary platform from first batch
    batches = payload.get("batches", [{}])
    platform_raw = batches[0].get("platform", "unknown")
    platform_slug = (
        platform_raw
        .lower()
        .replace(" / ", "-")
        .replace("/", "-")
        .replace(" ", "-")
        .replace("3rd-party", "affiliate")
    )

    uid = uuid.uuid4().hex[:4]
    return f"{year_month}-{platform_slug}-{uid}"


# ── ORDER.JSON BUILDER ────────────────────────────────────────────────────────

def build_order(payload: dict, sprint_id: str) -> dict:
    """
    Build the canonical order.json from the validated payload.
    This is the contract between Stage 00 and all downstream stages.
    """
    deliverable = payload["deliverable"]
    includes_images = deliverable in {"images-copy", "images-only"}
    includes_copy   = deliverable in {"images-copy", "copy-only"}

    # Normalise batches
    batches = []
    for batch in payload["batches"]:
        normalised = {
            "platform":          batch["platform"],
            "format":            batch["format"],
            "quantity":          int(batch.get("quantity", 1)),
            "visual_styles":     batch.get("visual_styles", []),
            "style_quantities":  batch.get("style_quantities", {}),
            "resolutions":       batch.get("resolutions", []),
            "carousel":          bool(batch.get("carousel", False)),
            "carousel_slides":   batch.get("carousel_slides"),
            "audience":          batch.get("audience"),
        }
        batches.append(normalised)

    # Determine primary platform (used in output path naming)
    primary_platform = batches[0]["platform"] if batches else "unknown"
    platform_slug = (
        primary_platform
        .lower()
        .replace(" / ", "-")
        .replace("/", "-")
        .replace(" ", "-")
    )

    return {
        "schema_version":  SCHEMA_VERSION,
        "sprint_id":       sprint_id,
        "submitted_at":    datetime.now(timezone.utc).isoformat(),
        "delivery_date":   payload["delivery_date"],
        "driver":          payload["driver"],
        "targeting":       payload["targeting"],
        "deliverable":     deliverable,
        "includes_images": includes_images,
        "includes_copy":   includes_copy,
        "platform":        primary_platform,
        "batches":         batches,
        "brief":           payload.get("brief", ""),
        "output_path":     f"Upwork/Sprints/{sprint_id}/Review-Queue",
        "pipeline_state": {
            "stage_00_intake":          "complete",
            "stage_01_load_refs":       "pending",
            "stage_02_copy_gen":        "pending",
            "stage_03_img_prompts":     "pending",
            "stage_04_generate_images": "pending",
            "stage_05_assemble":        "pending",
            "stage_06_deliver":         "pending",
        },
    }


# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def save_order_to_s3(sprint_id: str, order: dict) -> None:
    """Save order.json to S3 at /runs/{sprint_id}/order.json"""
    import boto3  # lazy: only needed when actually saving to S3
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/order.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(order, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    print(f"[00_intake] order.json saved → s3://{S3_BUCKET}/{key}")


# ── SLACK SUMMARY BUILDER ─────────────────────────────────────────────────────

def build_slack_summary(order: dict) -> dict:
    """
    Builds a Slack-ready message block from a normalised order.
    Included in the Mind Studio webhook payload so Leon's workflow
    can post it directly to #paid-acquisition-pipeline without
    any additional formatting.

    Format follows Slack Block Kit — plain text fallback also included.
    """
    sprint_id    = order["sprint_id"]
    driver       = order["driver"]
    targeting    = order["targeting"]
    deliverable  = order["deliverable"]
    platform     = order.get("platform") or "Copy Only"
    delivery     = order["delivery_date"]
    brief        = order.get("brief", "").strip()
    batches      = order.get("batches", [])

    # Deliverable label
    deliverable_labels = {
        "images-copy": "Images & Copy",
        "images-only": "Just Images",
        "copy-only":   "Just Copy"
    }
    deliverable_label = deliverable_labels.get(deliverable, deliverable)

    # Build batch summary lines
    batch_lines = []
    for b in batches:
        fmt      = b.get("format", "")
        qty      = b.get("quantity", 1)
        styles   = b.get("visual_styles", [])
        audience = b.get("audience", "")
        sizes    = [r.get("size", "") for r in b.get("resolutions", []) if r.get("size")]

        line = f"• *{fmt}* — {qty} set{'s' if qty != 1 else ''}"
        if styles:
            line += f" | Style: {', '.join(styles)}"
        if sizes:
            line += f" | Sizes: {', '.join(sizes)}"
        if audience and audience != "Both":
            line += f" | Audience: {audience}"
        batch_lines.append(line)

    batches_text = "\n".join(batch_lines) if batch_lines else "_(copy only — no image batches)_"

    # Plain text fallback
    plain_text = (
        f"New order received — Sprint {sprint_id}\n"
        f"Driver: {driver} | Platform: {platform} | Targeting: {targeting}\n"
        f"Deliverable: {deliverable_label} | Due: {delivery}"
    )

    # Slack Block Kit payload
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📋 New Ad Creative Order"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Sprint ID*\n{sprint_id}"},
                {"type": "mrkdwn", "text": f"*Driver*\n{driver}"},
                {"type": "mrkdwn", "text": f"*Platform*\n{platform}"},
                {"type": "mrkdwn", "text": f"*Audience Segment*\n{targeting}"},
                {"type": "mrkdwn", "text": f"*Deliverable*\n{deliverable_label}"},
                {"type": "mrkdwn", "text": f"*Delivery Date*\n{delivery}"}
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Ad Formats*\n{batches_text}"
            }
        }
    ]

    # Add brief section if provided
    if brief:
        brief_preview = brief[:300] + "..." if len(brief) > 300 else brief
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Creative Brief*\n_{brief_preview}_"
            }
        })

    # Footer divider
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Pipeline started • Order saved to S3 • Sprint `{sprint_id}`"
            }
        ]
    })

    return {
        "text":    plain_text,   # fallback for notifications
        "blocks":  blocks,       # rich Slack message
        "channel": "#paid-acquisition-pipeline"
    }


# ── MIND STUDIO TRIGGER ───────────────────────────────────────────────────────

def trigger_stage_01(sprint_id: str, order: dict) -> None:
    """
    POST to Mind Studio webhook to trigger Stage 01 (load_refs).
    Payload includes sprint_id, stage, and a pre-built Slack notification
    so Leon's workflow can forward it directly to #paid-acquisition-pipeline.
    """
    if not MIND_STUDIO_WEBHOOK:
        print("[00_intake] MIND_STUDIO_WEBHOOK_URL not set — skipping trigger")
        return

    payload_bytes = json.dumps({
        "sprint_id":          sprint_id,
        "stage":              "01_load_refs",
        "secret":             WEBHOOK_SECRET,
        "slack_notification": build_slack_summary(order),
    }).encode("utf-8")

    req = urllib.request.Request(
        MIND_STUDIO_WEBHOOK,
        data=payload_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
            print(f"[00_intake] Mind Studio triggered → HTTP {status}")
    except urllib.error.URLError as e:
        # Log but don't fail — Mind Studio may poll S3 instead
        print(f"[00_intake] WARNING: Mind Studio trigger failed: {e.reason}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def process_intake(raw_payload: dict) -> dict:
    """
    Main intake logic. Validates, builds order, saves to S3, triggers Stage 01.
    Returns a result dict with sprint_id and status.
    """
    print(f"[00_intake] Received order from: {raw_payload.get('driver', 'unknown')}")

    # Validate
    errors = validate_payload(raw_payload)
    if errors:
        print(f"[00_intake] Validation failed: {errors}")
        return {
            "success":   False,
            "errors":    errors,
            "sprint_id": None,
        }

    # Generate sprint ID
    sprint_id = generate_sprint_id(raw_payload)
    print(f"[00_intake] Sprint ID: {sprint_id}")

    # Build canonical order
    order = build_order(raw_payload, sprint_id)

    # Save to S3
    save_order_to_s3(sprint_id, order)

    # Trigger Stage 01 via Mind Studio (includes pre-built Slack notification)
    trigger_stage_01(sprint_id, order)

    print(f"[00_intake] Stage 00 complete → sprint: {sprint_id}")

    return {
        "success":   True,
        "sprint_id": sprint_id,
        "platform":  order["platform"],
        "batches":   len(order["batches"]),
        "errors":    [],
    }


# ── LAMBDA ENTRY POINT ────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    Mind Studio POSTs the order form payload in the request body.
    """
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        result = process_intake(body)

        status_code = 200 if result["success"] else 400
        return {
            "statusCode": status_code,
            "body": json.dumps(result),
        }

    except Exception as e:
        print(f"[00_intake] ERROR: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — run with:
        python3 00_intake.py

    Uses a sample Meta Static Feed order to verify validation,
    sprint_id generation, and order.json structure.
    Skips S3 save and Mind Studio trigger unless env vars are set.
    """
    import pprint

    SAMPLE_ORDER = {
        "delivery_date": "2026-04-18",
        "driver":        "Logan Heath",
        "targeting":     "Prospecting",
        "deliverable":   "images-copy",
        "batches": [
            {
                "platform":      "Meta",
                "format":        "Static Feed",
                "quantity":      1,
                "visual_styles": ["Image Library"],
                "resolutions":   [{"size": "1080 x 1080", "ratio": "1:1"}],
                "carousel":      False,
            }
        ],
        "brief": "Showcase how Upwork helps businesses find freelancers fast.",
    }

    # Run validation only (no S3/Mind Studio calls)
    print("\n── VALIDATION ──────────────────────────────────────────")
    errors = validate_payload(SAMPLE_ORDER)
    if errors:
        print(f"FAILED: {errors}")
    else:
        sprint_id = generate_sprint_id(SAMPLE_ORDER)
        order     = build_order(SAMPLE_ORDER, sprint_id)
        print(f"PASSED → sprint_id: {sprint_id}")
        print("\n── ORDER.JSON ──────────────────────────────────────────")
        pprint.pprint(order, width=80)
