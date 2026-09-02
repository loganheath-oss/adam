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
from pathlib import Path
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


# Brief scaffolding that means "nobody filled this in". A submitted brief made
# ONLY of the order form's own template text is worse than an empty one: it
# looks like direction, so it reads as intentional at Gate 2 while carrying zero
# information. Live incident 2026-08-04 (Sarah's first solo sprint) — the gate
# caught it because the agent read the text, not because intake flagged it.
# Non-blocking by design: this warns loudly, the human still decides.
_BRIEF_SECTION_HEADERS = ("theme", "copy must-dos", "design direction", "resources")
_BRIEF_PLACEHOLDER_RE = re.compile(
    r"(\(\s*(one or two sentences|a required phrase|a visual|a reference)[^)]*\))"
    r"|(\{\{[^}]*\}\})"                      # {{slot}}
    r"|(\[\s*(fill|insert|todo|tbd)[^\]]*\])"  # [fill this in], [TBD ...]
    r"|(\bremove this line if none\b)"
    r"|(\bxxx+\b)"
    r"|(\blorem ipsum\b)",
    re.IGNORECASE,
)


def _placeholder_brief_report(brief: str) -> str | None:
    """Return a warning string if the brief is (mostly) unfilled template text.

    Returns None when the brief carries real content. Deliberately conservative:
    a brief with genuine direction alongside one leftover placeholder line still
    passes with a lighter note only when placeholders dominate.
    """
    if not isinstance(brief, str) or not brief.strip():
        return None
    lines = [ln.strip() for ln in brief.splitlines() if ln.strip()]
    if not lines:
        return None

    substantive = []
    for ln in lines:
        bare = ln.lstrip("-*# ").strip()
        low = bare.lower().rstrip(":")
        if low in _BRIEF_SECTION_HEADERS:      # a section header carries no direction
            continue
        if _BRIEF_PLACEHOLDER_RE.search(bare):  # unfilled scaffolding
            continue
        if len(bare) < 3:
            continue
        substantive.append(bare)

    if substantive:
        return None
    return ("Brief looks UNFILLED — it contains only the order form's template "
            "text (section headers and example placeholders), no actual direction. "
            "Copy generation would be guessing. Replace the brief before approving "
            "Gate 2, or confirm explicitly that generic copy is intended.")


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
            # DEDUPE: the form's "+ Add Style" can add the same style twice; duplicates
            # flow into the fan-out and produce colliding concept_ids (two different
            # concepts sharing one id — found 2026-07-30 on a live sprint, scrambling
            # review display + copy/image matching). Keep first occurrence, in order;
            # style_quantities merging below already sums the quantities.
            _seen = set()
            batch["visual_styles"] = [x for x in normalized
                                      if not (x in _seen or _seen.add(x))]

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
                        # A typo used to coerce to 0 and later resurrect as 1-2 —
                        # the operator's input was silently reinterpreted (audit
                        # 2026-07-31). Reject instead.
                        errors.append(f"{prefix}: style quantity for '{k}' is not a "
                                      f"number: {v!r}")
                        continue
                    if qty < 1:
                        errors.append(f"{prefix}: style quantity for '{k}' must be >= 1")
                        continue
                    if qty > 6:
                        # The pipeline generates at most 6 concepts per style; the
                        # form used to accept up to 99 and silently deliver 6.
                        errors.append(f"{prefix}: style quantity for '{k}' is {qty} — "
                                      "the maximum is 6 per style (order the style in a "
                                      "second sprint for more)")
                        continue
                    merged[canonical] = merged.get(canonical, 0) + qty
                for _s, _q in merged.items():
                    if _q > 6:
                        errors.append(f"{prefix}: total quantity for '{_s}' is {_q} — "
                                      "the maximum is 6 per style")
                batch["style_quantities"] = merged

        # ── Non-blocking warnings (surfaced at Gate 2, never silently dropped)
        warnings = payload.setdefault("intake_warnings", [])
        try:
            _reg = json.loads((Path(__file__).parent.parent / "configs"
                               / "template_registry.json").read_text())
            _map = _reg.get("style_to_template_mapping", {}) or {}
            for _s in batch.get("visual_styles", []):
                _tpl = str((_map.get(_s) or {}).get("template", ""))
                if _tpl in ("NEEDS_TEMPLATE", "MANUAL"):
                    # August testing showed these styles usually STILL assemble in
                    # Figma — the registry is often stale rather than the template
                    # missing (Adrie's changelog, punchlist item 1). Warn without
                    # implying failure.
                    _w = (f"Style '{_s}' has no confirmed Figma template in the registry "
                          f"({_tpl}) — copy will generate, and in August testing these "
                          f"styles usually still assembled in Figma; the registry may "
                          f"simply be stale. Not a blocker.")
                    if _w not in warnings:
                        warnings.append(_w)
        except Exception:
            pass
        _brief_raw = str(payload.get("brief") or "")
        if not _brief_raw.strip() and                 "No brief provided — copy will be generic. Confirm this is intentional at Gate 2." not in warnings:
            warnings.append("No brief provided — copy will be generic. Confirm this is intentional at Gate 2.")
        else:
            _ph = _placeholder_brief_report(_brief_raw)
            if _ph and _ph not in warnings:
                warnings.append(_ph)

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

        # Audience refines which segment a batch targets, and only applies to
        # "Prospecting and Retargeting" orders. The order form defaults this
        # pill to "Both"; if the payload omits it (older form, or the JS didn't
        # emit it), default to "Both" here rather than hard-failing the whole
        # order — the top-level targeting already captures intent, and blocking
        # a multi-asset order over an optional refinement is the wrong tradeoff.
        if targeting == "Prospecting and Retargeting" and not batch.get("audience"):
            batch["audience"] = "Both"

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
        # CREATIVITY LEVEL (Lee's "weirdness knob", working session 2026-09-01).
        # standard = today's behavior; bold/wild license format-breaking concepts
        # and raise photo-pick variety. Anything unrecognized falls back safe.
        "creativity":      (str(payload.get("creativity", "") or "standard").strip().lower()
                            if str(payload.get("creativity", "") or "standard").strip().lower()
                            in ("standard", "bold", "wild") else "standard"),
        # Carry the non-blocking intake warnings INTO the order. They were being
        # computed in validate_payload, written onto the payload, and then
        # dropped here — so no warning ever reached a human at Gate 2: not the
        # missing-template warning, not the empty-brief warning, and not the
        # placeholder-brief warning added 2026-08-07. The order is what the Gate
        # 2 agent reads, so this is the only channel that surfaces them.
        "intake_warnings": list(payload.get("intake_warnings") or []),
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
