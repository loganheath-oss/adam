"""
02_copy_gen.py
==============
Stage 02 — Copy Generation

Reads context.json and order.json from S3, calls Upwork's internal
LLM Gateway (Claude) to generate ad copy for each batch in the order,
and saves structured copy_outputs.json back to S3.

Inputs:  /runs/{sprint_id}/order.json      (from S3)
         /runs/{sprint_id}/context.json    (from S3, built by Stage 01)
Outputs: /runs/{sprint_id}/copy_outputs.json (to S3)

Skipped: If order.includes_copy is False (images-only order).

Trigger: Mind Studio calls this after Stage 01 completes.

Author:  CM (Creative Machine)
Version: 1.0
"""

import json
import os
import time
import boto3
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────

S3_BUCKET             = os.environ.get("RUNS_BUCKET", "PLACEHOLDER_runs_bucket")
LLM_GATEWAY_ENDPOINT  = os.environ.get("LLM_GATEWAY_ENDPOINT", "")
LLM_GATEWAY_API_KEY   = os.environ.get("LLM_GATEWAY_API_KEY", "")
LLM_GATEWAY_MODEL     = os.environ.get("LLM_GATEWAY_MODEL", "")

# Fallback to direct Anthropic API for local dev only
# Remove this before production deployment
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_ENDPOINT    = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL       = "claude-sonnet-4-6"

# Copy generation settings
MAX_TOKENS            = 4096
TEMPERATURE           = 0.7
RETRY_ATTEMPTS        = 3
RETRY_DELAY_SECONDS   = 5

# Channel character limits — mirrors upwork_config.json channel_specs
CHANNEL_SPECS = {
    "Meta": {
        "primary_text_max_chars": 125,
        "headline_max_chars":     40,
        "description_max_chars":  25,
        "cta_options": [
            "Get started for free", "Get started",
            "Post a job for free", "Learn more", "Sign up"
        ]
    },
    "LinkedIn": {
        "intro_text_max_chars":             600,
        "intro_text_mobile_truncation":     150,
        "headline_max_chars":               70,
        "text_ad_headline_max_chars":       25,
        "text_ad_description_max_chars":    75
    },
    "Reddit": {
        "headline_max_chars":   300,
        "body_max_chars":       10000,
    },
    "YouTube": {
        "script_length_seconds": 15,
        "framework":             "ABCD"
    },
    "Google / Bing": {
        "headline_max_chars":     30,
        "description_max_chars":  90,
        "headline_count":         "10-12",
        "description_count":      "3-4"
    },
    "3rd Party / Affiliate": {
        "headline_max_chars":     60,
        "body_max_chars":         150,
    }
}

# ── S3 HELPERS ────────────────────────────────────────────────────────────────

def load_json_from_s3(sprint_id: str, filename: str) -> dict:
    """Load a JSON file from S3 at /runs/{sprint_id}/{filename}"""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def save_json_to_s3(sprint_id: str, filename: str, data: dict) -> None:
    """Save a JSON file to S3 at /runs/{sprint_id}/{filename}"""
    s3 = boto3.client("s3")
    key = f"runs/{sprint_id}/{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    print(f"[02_copy_gen] Saved → s3://{S3_BUCKET}/{key}")


# ── LLM GATEWAY CLIENT ────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call Upwork's LLM Gateway with retry logic.
    Falls back to direct Anthropic API if LLM_GATEWAY_ENDPOINT is not set
    (local development only — remove fallback before production).

    Returns the raw text content of the response.
    """
    # Determine which endpoint to use
    if LLM_GATEWAY_ENDPOINT:
        endpoint  = LLM_GATEWAY_ENDPOINT
        api_key   = LLM_GATEWAY_API_KEY
        model     = LLM_GATEWAY_MODEL
        auth_header = f"Bearer {api_key}"
    elif ANTHROPIC_API_KEY:
        # Local dev fallback only
        print("[02_copy_gen] WARNING: Using direct Anthropic API (local dev only)")
        endpoint    = ANTHROPIC_ENDPOINT
        api_key     = ANTHROPIC_API_KEY
        model       = ANTHROPIC_MODEL
        auth_header = f"x-api-key"  # handled separately below
    else:
        raise EnvironmentError(
            "No LLM endpoint configured. Set LLM_GATEWAY_ENDPOINT or "
            "ANTHROPIC_API_KEY for local dev."
        )

    payload = {
        "model":      model,
        "max_tokens": MAX_TOKENS,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_prompt}],
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            body = json.dumps(payload).encode("utf-8")

            # Build headers
            if LLM_GATEWAY_ENDPOINT:
                headers = {
                    "Content-Type":  "application/json",
                    "Authorization": auth_header,
                }
            else:
                # Anthropic-specific headers for local dev
                headers = {
                    "Content-Type":      "application/json",
                    "x-api-key":         api_key,
                    "anthropic-version": "2023-06-01",
                }

            req = urllib.request.Request(
                endpoint,
                data=body,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
                # Handle both Gateway and Anthropic response shapes
                if "content" in response_data:
                    return response_data["content"][0]["text"]
                elif "choices" in response_data:
                    return response_data["choices"][0]["message"]["content"]
                else:
                    return str(response_data)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[02_copy_gen] LLM call attempt {attempt} failed: HTTP {e.code} — {error_body}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
            else:
                raise

        except Exception as e:
            print(f"[02_copy_gen] LLM call attempt {attempt} error: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
            else:
                raise


def parse_json_response(raw: str) -> list:
    """
    Extract JSON array from LLM response.
    Handles responses with markdown code fences or preamble text.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the first [ and last ] to extract JSON array
    start = text.find("[")
    end   = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start:end + 1]

    return json.loads(text)


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────

def build_system_prompt(context: dict) -> str:
    """
    Build the system prompt from context.json brand files.
    This is injected on every LLM call.
    """
    brand   = context.get("brand", {})
    voice   = brand.get("voice", "")
    style   = brand.get("writing_style", "")
    compliance = brand.get("compliance", "")

    return f"""You are a senior copywriter for Upwork's Paid Acquisition team.
You write direct-response ad copy that drives clicks and signups.

## BRAND VOICE
{voice[:3000] if voice else "Clear, concise, user-centric. No jargon. Active voice. Short sentences."}

## WRITING STYLE
{style[:1500] if style else "Plain language. Universal words. Specific over vague. User perspective."}

## COMPLIANCE RULES
{compliance[:1000] if compliance else "Do not make guarantees. Do not use superlatives. Keep claims factual."}

## OUTPUT FORMAT
Return ONLY a valid JSON array. No preamble. No explanation. No markdown.
Each item in the array must be a JSON object with these exact keys:
  headline  — primary message, within character limit
  body      — supporting copy, within character limit
  cta       — call-to-action text, from approved list if provided
  concept_tag — 2-4 word label describing the creative concept (snake_case)

Do not number items. Do not include any text outside the JSON array."""


def build_user_prompt(
    batch: dict,
    order: dict,
    context: dict,
    quantity: int,
) -> str:
    """
    Build the per-batch user prompt.
    Pulls channel specs, targeting, and performance signals.
    """
    platform    = batch["platform"]
    fmt         = batch["format"]
    targeting   = order["targeting"]
    brief       = order.get("brief", "")
    audience    = batch.get("audience") or targeting
    styles      = batch.get("visual_styles", [])

    # Channel character limits
    specs = CHANNEL_SPECS.get(platform, {})
    specs_text = json.dumps(specs, indent=2) if specs else "No specific limits — keep copy concise."

    # Performance signals from last sprint
    perf = context.get("performance", {})
    perf_rows = perf.get("last_sprint_rows", [])
    perf_text = ""
    if perf_rows:
        top = [r for r in perf_rows if r.get("performance") == "top"][:3]
        if top:
            perf_text = f"\n\nTOP PERFORMING CONCEPTS FROM LAST SPRINT:\n"
            for r in top:
                perf_text += f"- {r.get('concept_tag', '')}: {r.get('headline', '')} — CTR {r.get('ctr', '')}\n"

    # Copy playbook examples
    playbook = context.get("prompts", {}).get("copy_playbook", "")
    examples_key = "examples_retargeting" if "retargeting" in targeting.lower() else "examples_prospecting"
    examples = context.get("prompts", {}).get(examples_key, "")

    # Visual style context
    style_context = ""
    if styles:
        style_context = f"\nVISUAL STYLES FOR THIS BATCH: {', '.join(styles)}\nWrite copy that complements these visual approaches."

    prompt = f"""Generate {quantity} unique ad copy concepts for Upwork.

PLATFORM: {platform}
FORMAT: {fmt}
TARGETING: {targeting}
AUDIENCE SEGMENT: {audience}

CHARACTER LIMITS:
{specs_text}
{style_context}

CREATIVE BRIEF:
{brief if brief else "Highlight how Upwork connects businesses with top freelancers quickly and confidently."}
{perf_text}

COPY PLAYBOOK REFERENCE:
{playbook[:2000] if playbook else ""}

EXAMPLE ADS FOR REFERENCE (do not copy — use as tone/style reference only):
{examples[:1500] if examples else ""}

Generate {quantity} distinct concepts. Each must feel different — vary the hook, angle, and proof point.
Return as a JSON array only."""

    return prompt


# ── MAIN GENERATION LOGIC ─────────────────────────────────────────────────────

def generate_copy_for_batch(
    batch: dict,
    order: dict,
    context: dict,
    sprint_id: str,
    batch_index: int,
) -> list:
    """
    Generate copy for a single batch from the order.
    Returns a list of copy asset dicts with asset_id assigned.
    """
    platform  = batch["platform"]
    fmt       = batch["format"]
    quantity  = batch.get("quantity", 1)

    print(f"[02_copy_gen] Generating copy: {platform} / {fmt} — {quantity} concept(s)")

    system_prompt = build_system_prompt(context)
    user_prompt   = build_user_prompt(batch, order, context, quantity)

    raw_response  = call_llm(system_prompt, user_prompt)
    concepts      = parse_json_response(raw_response)

    # Assign asset IDs and enrich with metadata
    results = []
    for i, concept in enumerate(concepts[:quantity]):  # cap at requested quantity
        asset_id = f"{sprint_id}-b{batch_index:02d}-c{i+1:02d}"
        results.append({
            "asset_id":     asset_id,
            "sprint_id":    sprint_id,
            "batch_index":  batch_index,
            "platform":     platform,
            "format":       fmt,
            "variant_num":  i + 1,
            "visual_styles": batch.get("visual_styles", []),
            "resolutions":  batch.get("resolutions", []),
            "headline":     concept.get("headline", ""),
            "body":         concept.get("body", ""),
            "cta":          concept.get("cta", ""),
            "concept_tag":  concept.get("concept_tag", f"concept_{i+1}"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    print(f"[02_copy_gen] Generated {len(results)} concept(s) for batch {batch_index}")
    return results


def generate_copy(sprint_id: str) -> dict:
    """
    Main function. Loads context + order from S3, generates copy for
    every batch, saves copy_outputs.json to S3.
    Returns a summary dict.
    """
    print(f"[02_copy_gen] Starting copy generation for sprint: {sprint_id}")

    # Load inputs
    order   = load_json_from_s3(sprint_id, "order.json")
    context = load_json_from_s3(sprint_id, "context.json")

    # Skip if copy not required
    if not order.get("includes_copy", True):
        print(f"[02_copy_gen] Order is images-only — skipping copy generation")
        return {"sprint_id": sprint_id, "skipped": True, "assets_generated": 0}

    # Generate copy for each batch
    all_assets = []
    for i, batch in enumerate(order.get("batches", [])):
        assets = generate_copy_for_batch(batch, order, context, sprint_id, i)
        all_assets.extend(assets)
        # Brief pause between batches to avoid rate limiting
        if i < len(order["batches"]) - 1:
            time.sleep(1)

    # Build output object
    copy_outputs = {
        "schema_version":  "1.0",
        "sprint_id":       sprint_id,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "total_assets":    len(all_assets),
        "assets":          all_assets,
    }

    # Save to S3
    save_json_to_s3(sprint_id, "copy_outputs.json", copy_outputs)

    summary = {
        "sprint_id":        sprint_id,
        "skipped":          False,
        "assets_generated": len(all_assets),
        "batches":          len(order.get("batches", [])),
    }

    print(f"[02_copy_gen] Stage 02 complete — {len(all_assets)} assets generated")
    return summary


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

        result = generate_copy(sprint_id)

        return {
            "statusCode": 200,
            "body": json.dumps(result),
        }

    except Exception as e:
        print(f"[02_copy_gen] ERROR: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


# ── LOCAL DEV ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Local test — requires ANTHROPIC_API_KEY to be set.
    Builds a mock context.json inline so no S3 or Drive access needed.

    Run with:
        ANTHROPIC_API_KEY=sk-ant-... python3 02_copy_gen.py
    """
    import pprint

    # Minimal mock context — in production this comes from Stage 01
    MOCK_CONTEXT = {
        "schema_version": "1.0",
        "sprint_id": "2026-04-meta-test",
        "brand": {
            "voice": """
## Voice Pillars
- Clear and Concise: Use as few words as possible without losing meaning.
- Supportive and Perceptive: Acknowledge user needs without being preachy.
- Calm and Guiding: Reassure without pressure.
- Levity: Light, not jokey.

## Copy Rules — Do
- Get to the point. Short sentences. Active voice.
- Write from the user perspective (what they gain, not what we built).
- Use plain language accessible to non-native English speakers.
- Be specific. "Hire in 3 days" beats "Hire fast."

## Copy Rules — Do Not
- No lofty or overly wordy language.
- No pressure or fear-based language.
- No idioms or culturally-specific phrases.
- Don't make it about Upwork — make it about the user.
""",
            "compliance": "Do not guarantee outcomes. Keep claims factual and verifiable.",
        },
        "prompts": {
            "copy_playbook": "Focus on time savings and quality of talent.",
            "examples_prospecting": """
awareness_client:
  headline: "The future of hiring, built for now."
  body: "AI-powered tools to hire, work, and get more done."
  cta: "Learn more"
""",
        },
        "performance": {"last_sprint_rows": [], "row_count": 0},
    }

    MOCK_ORDER = {
        "schema_version":  "1.0",
        "sprint_id":       "2026-04-meta-test",
        "delivery_date":   "2026-04-18",
        "driver":          "Logan Heath",
        "targeting":       "Prospecting",
        "deliverable":     "images-copy",
        "includes_copy":   True,
        "includes_images": True,
        "platform":        "Meta",
        "batches": [
            {
                "platform":      "Meta",
                "format":        "Static Feed",
                "quantity":      2,
                "visual_styles": ["Image Library"],
                "resolutions":   [{"size": "1080 x 1080", "ratio": "1:1"}],
                "carousel":      False,
                "audience":      None,
            }
        ],
        "brief": "Showcase how Upwork connects businesses with top freelancers quickly and confidently.",
    }

    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY to run local test")
        exit(1)

    print("\n── BUILDING PROMPTS ────────────────────────────────────────")
    system = build_system_prompt(MOCK_CONTEXT)
    user   = build_user_prompt(MOCK_ORDER["batches"][0], MOCK_ORDER, MOCK_CONTEXT, 2)
    print("System prompt (first 300 chars):", system[:300])
    print("\nUser prompt (first 500 chars):", user[:500])

    print("\n── CALLING LLM ─────────────────────────────────────────────")
    raw    = call_llm(system, user)
    parsed = parse_json_response(raw)
    print(f"Got {len(parsed)} concepts:")
    pprint.pprint(parsed, width=80)
