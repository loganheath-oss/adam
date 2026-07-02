#!/usr/bin/env python3
"""
run_pipeline.py
===============
Local Pipeline Runner

Chains Stages 00 through 06 using the local filesystem instead of S3.
Each stage reads from and writes to runs/{sprint_id}/ on disk.

Usage:
    # Run with a CSV from the order form
    python3 pipeline/run_pipeline.py --csv path/to/order.csv

    # Run with a JSON payload
    python3 pipeline/run_pipeline.py --json path/to/order.json

    # Run with the built-in test order
    python3 pipeline/run_pipeline.py --test

Requires .env file with API keys. Copy .env.example to .env and fill in values.

Author:  CM (Creative Machine)
Version: 1.0
"""

import json
import csv
import os
import re
import sys
import threading
import time
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Load .env file
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

# Project paths
BASE_DIR = Path(__file__).parent.parent
RUNS_DIR = Path(os.environ.get("RUNS_DIR", str(BASE_DIR / "runs")))
RUNS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = BASE_DIR / "configs" / "upwork_config.json"
TEMPLATE_REGISTRY_PATH = BASE_DIR / "configs" / "template_registry.json"

_TEMPLATE_REGISTRY_CACHE = None  # populated on first load_template_registry() call


def load_template_registry() -> dict:
    """Read configs/template_registry.json once, cache for the run."""
    global _TEMPLATE_REGISTRY_CACHE
    if _TEMPLATE_REGISTRY_CACHE is None:
        with open(TEMPLATE_REGISTRY_PATH) as f:
            _TEMPLATE_REGISTRY_CACHE = json.load(f)
    return _TEMPLATE_REGISTRY_CACHE


# Styles that need TWO distinct library photos (left + right placeholder).
# Add new dual-image styles here and the row builder will pick two photos.
DUAL_PHOTO_LIBRARY_STYLES = {"Split Screen"}

# Styles that produce multiple variant outputs per concept. The pipeline emits
# one image-prompt row per variant. Brandon gets every variant as a separate
# deliverable so he can compare them. Variant names must match a `variant_name`
# inside the template_registry.json entry for the style's template.
MULTI_VARIANT_STYLES = {
    # Logan, May 11: ship white-border and no-border for every Text Only
    # concept. Skip the inverted (green-border-on-black) until Brandon asks.
    "Text Only": ["WhiteBorder_GreenBg", "NoBorder_GreenBg"],
    # Logan's call carried forward May 18 for Meme — same white-border +
    # no-border pair. Black-border variant registered but not emitted.
    "Meme": ["WhiteBorder_Cream", "NoBorder_Cream"],
}


def _variants_from_registry(template_name: str) -> list[dict]:
    """Return the `variants` list from the registry for a given template."""
    reg = load_template_registry()
    for tmpl in reg.get("templates", []):
        if tmpl.get("template_name") == template_name:
            return tmpl.get("variants", []) or []
    return []


def _variant_frame_id(template_name: str, variant_name: str) -> str:
    """Look up the Figma frame ID for a (template, variant) pair. '' if not found."""
    for v in _variants_from_registry(template_name):
        if v.get("variant_name") == variant_name:
            return v.get("figma_frame_id", "") or ""
    return ""


# Pie Chart: pull the data percentage from the concept copy so the plugin can
# size the chart slice + fill the center callout (Elise's Figma comment #8).
_CHART_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

def _extract_chart_pct(concept: dict, row: dict) -> str:
    """First percentage found in the concept copy, as a plain number string
    ('73'), or '' if none. The slice angle = pct/100 of a full circle."""
    text = " ".join(str(concept.get(k, "")) for k in
                     ("headline", "body", "body_short", "body_long", "stat", "description"))
    text += " " + str(row.get("headline", ""))
    m = _CHART_PCT_RE.search(text)
    if not m:
        return ""
    try:
        v = float(m.group(1))
        if not (0 <= v <= 100):
            return ""
        return str(int(v)) if v == int(v) else str(v)
    except Exception:
        return ""


def _join_bullets(val) -> str:
    """Flatten a bullet list (or string) into a '|'-joined manifest cell. The
    plugin splits on '|' to fill each bullet layer."""
    if isinstance(val, list):
        return "|".join(str(x).strip() for x in val if str(x).strip())
    return str(val or "").strip()

# =============================================================================
# STAGE 00: INTAKE (local version)
# =============================================================================

def stage_00_intake(payload):
    """Validate order, generate sprint ID, save order.json locally."""
    print("\n" + "="*60)
    print("  STAGE 00: INTAKE")
    print("="*60)

    # Import validation from the real intake script
    sys.path.insert(0, str(BASE_DIR / "pipeline"))
    from importlib import import_module

    intake = import_module("00_intake")

    errors = intake.validate_payload(payload)
    if errors:
        print(f"  Validation FAILED:")
        for e in errors:
            print(f"    - {e}")
        return None

    sprint_id = payload.get("sprint_id") or intake.generate_sprint_id(payload)
    order = intake.build_order(payload, sprint_id)

    # Save locally instead of S3
    run_dir = RUNS_DIR / sprint_id
    run_dir.mkdir(parents=True, exist_ok=True)

    order_path = run_dir / "order.json"
    with open(order_path, "w") as f:
        json.dump(order, f, indent=2)

    print(f"  Sprint ID: {sprint_id}")
    print(f"  Driver: {order['driver']}")
    print(f"  Platform: {order['platform']}")
    print(f"  Batches: {len(order['batches'])}")
    print(f"  Saved: {order_path}")

    return sprint_id, order


# =============================================================================
# STAGE 01: LOAD REFS (local version)
# =============================================================================

def stage_01_load_refs(sprint_id, order):
    """Load pre-built reference context and merge with order-specific data.

    Priority order (highest to lowest):
    1. Order-specific data (brief, targeting, style choices) — OVERRIDES everything
    2. Pre-built refs_context.json (brand voice, compliance, examples) — standing rules
    """
    print("\n" + "="*60)
    print("  STAGE 01: LOAD REFERENCES")
    print("="*60)

    run_dir = RUNS_DIR / sprint_id
    refs_json_path = BASE_DIR / "configs" / "refs_context.json"

    # Load pre-built reference context
    if refs_json_path.exists():
        with open(refs_json_path) as f:
            context = json.load(f)
        # Remove the _meta key from the refs
        context.pop("_meta", None)
        context["source"] = "pre-built refs_context.json"

        # Count loaded refs
        loaded = sum(1 for k, v in context.items()
                     if isinstance(v, str) and len(v) > 100 and k != "source")
        print(f"  Loaded refs_context.json ({loaded} reference documents)")
    else:
        print(f"  refs_context.json not found — run: python3 pipeline/build_refs.py")
        context = {"source": "empty"}

    # Filter examples based on targeting type
    targeting = order.get("targeting", "Prospecting")
    if "Retargeting" in targeting and "Prospecting" not in targeting:
        # Retargeting only — remove prospecting examples to avoid confusion
        context.pop("prospecting_examples", None)
        print(f"  Targeting: {targeting} — using retargeting examples only")
    elif "Prospecting" in targeting and "Retargeting" not in targeting:
        # Prospecting only — remove retargeting examples
        context.pop("retargeting_examples", None)
        print(f"  Targeting: {targeting} — using prospecting examples only")
    else:
        print(f"  Targeting: {targeting} — using both example sets")

    # Merge order-specific data ON TOP of refs (order takes priority)
    context["sprint_id"] = sprint_id
    context["order"] = order

    # Order-specific overrides — these fields from the order brief
    # take priority over anything in the reference docs
    brief = order.get("brief", "").strip()
    if brief:
        context["order_brief"] = brief
        context["_priority_note"] = (
            "The order brief below is the most current instruction for this sprint. "
            "If anything in the brief contradicts the standing reference documents, "
            "follow the brief. The brief represents what the team wants RIGHT NOW."
        )
        print(f"  Order brief: \"{brief[:80]}{'...' if len(brief) > 80 else ''}\"")
        print(f"  Priority: order brief overrides standing reference docs")
    else:
        print(f"  No order brief provided — using reference docs only")

    # Save per-run context (slim — just order data + pointers, not the full ref text)
    # But for the prompt builder, keep the full context in memory
    slim_context = {
        "source": context["source"],
        "sprint_id": sprint_id,
        "order": order,
        "order_brief": brief,
        "refs_loaded": loaded if refs_json_path.exists() else 0,
        "targeting_examples": targeting,
    }

    context_path = run_dir / "context.json"
    with open(context_path, "w") as f:
        json.dump(slim_context, f, indent=2)

    print(f"\n  Loaded {loaded} reference documents")
    print(f"  Saved: {context_path}")

    return context


# =============================================================================
# STAGE 02: COPY GENERATION (local version)
# =============================================================================

def stage_02_copy_gen(sprint_id, order, context):
    """Generate ad copy using Anthropic API directly."""
    print("\n" + "="*60)
    print("  STAGE 02: COPY GENERATION")
    print("="*60)

    if not order.get("includes_copy", True):
        print("  Skipped (images-only order)")
        return None

    run_dir = RUNS_DIR / sprint_id
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("  No ANTHROPIC_API_KEY set. Generating placeholder copy.")
        copy_outputs = _generate_placeholder_copy(order)
    else:
        # Step 1: Generate 6x copy concepts per style
        print("  Phase 1: Generating 6x concepts per style...")
        copy_outputs = _generate_real_copy(order, context, api_key, sprint_id)

        # Step 2: Self-review — Claude scores all concepts and picks top 3
        if copy_outputs.get("concepts"):
            print("  Phase 2: Self-review — scoring and ranking...")
            copy_outputs = _review_and_rank_copy(copy_outputs, order, context, api_key, sprint_id)

    copy_path = run_dir / "copy_outputs.json"
    with open(copy_path, "w") as f:
        json.dump(copy_outputs, f, indent=2)

    print(f"  Generated {len(copy_outputs.get('concepts', []))} concepts")
    print(f"  Saved: {copy_path}")

    return copy_outputs


def _generate_placeholder_copy(order):
    """Generate placeholder copy when no API key is available."""
    concepts = []
    for i, batch in enumerate(order.get("batches", [])):
        for style in batch.get("visual_styles", ["default"]):
            concepts.append({
                "concept_id": f"concept_{i}_{style.lower().replace(' ', '_')}",
                "batch_index": i,
                "visual_style": style,
                "headline": f"[PLACEHOLDER] Headline for {style}",
                "body": f"[PLACEHOLDER] Body copy for {batch.get('platform', 'unknown')} {style} ad",
                "cta": "Get Started",
                "concept_tag": f"{style.lower().replace(' ', '-')}-v1"
            })
    return {"concepts": concepts, "generated_at": datetime.now(timezone.utc).isoformat()}


def _generate_copy_for_style(i, batch, style, order, context, api_key, sprint_id=None):
    """Generate 6 copy concepts for one visual style (one Claude call).

    Extracted so styles can run concurrently — each call is independent and
    ~120s I/O-bound, so a serial loop stacked minutes on wide orders."""
    import httpx

    OVERGENERATE_MULTIPLIER = 6
    concepts = []
    qty = OVERGENERATE_MULTIPLIER  # Always generate 6 regardless of ordered quantity

    # Build rich prompt with all reference context
    brand_voice = context.get("brand_voice", "Professional, clear, human")
    writing_style = context.get("writing_style", "")
    compliance = context.get("compliance", "")
    playbook = context.get("copy_playbook", "")
    claims = context.get("approved_claims", "")
    copy_bank = context.get("smb_copy_bank", "")
    copy_style_rules = context.get("copy_style_rules", "")

    # Pick examples based on targeting
    targeting_type = order.get("targeting", "Prospecting")
    examples = ""
    if "Prospecting" in targeting_type:
        examples = context.get("prospecting_examples", "")
    elif "Retargeting" in targeting_type:
        examples = context.get("retargeting_examples", "")
    if not examples and context.get("prospecting_examples"):
        examples = context.get("prospecting_examples", "")

    # Get order brief for priority override
    order_brief = context.get("order_brief", order.get("brief", ""))
    priority_note = context.get("_priority_note", "")

    # Multi-field styles need extra structured copy beyond headline/body/cta.
    _sl = style.strip().lower().replace(" ", "")
    multi_field_instructions = ""
    multi_field_keys = ""
    if _sl == "usvsthem":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Us vs Them\" =====\n"
            "This is a side-by-side comparison ad. ALSO provide:\n"
            "- us_headline (max 18 chars — the Upwork/positive side label)\n"
            "- them_headline (max 18 chars — the old-way/negative side label)\n"
            "- us_bullets (array of EXACTLY 3 strings, max 28 chars each — Upwork-side wins)\n"
            "- them_bullets (array of EXACTLY 3 strings, max 28 chars each — old-way pains)\n"
        )
        multi_field_keys = ", us_headline, them_headline, us_bullets, them_bullets"
    elif _sl == "stickynote":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Sticky Note\" =====\n"
            "This is a two-column sticky-note ad. ALSO provide:\n"
            "- left_headline (max 12 chars — left column title)\n"
            "- right_headline (max 12 chars — right column title)\n"
            "- left_bullets (array of EXACTLY 2 strings, max 30 chars each)\n"
            "- right_bullets (array of EXACTLY 2 strings, max 30 chars each)\n"
        )
        multi_field_keys = ", left_headline, right_headline, left_bullets, right_bullets"

    prompt = f"""You are writing paid acquisition ad copy for Upwork. Follow every brand rule below exactly.

===== ORDER BRIEF (HIGHEST PRIORITY) =====
{f"This brief is the most current instruction. If it contradicts any reference document below, follow the brief." if order_brief else "No specific brief provided."}

{order_brief if order_brief else "General: Showcase how Upwork helps businesses find freelancers fast."}

===== BRAND VOICE =====
{brand_voice[:3000]}

===== WRITING STYLE =====
{writing_style[:4000]}

===== COMPLIANCE AND LEGAL RULES =====
{compliance[:4000]}

===== COPY PLAYBOOK =====
{playbook[:2000]}

===== APPROVED CLAIMS AND STATS =====
Use only these verified claims. Do not invent statistics.
{claims[:2000]}

===== COPY BANK (approved headlines and copy) =====
Reference these for tone and structure. Match this quality.
{copy_bank[:3000]}

===== REAL AD EXAMPLES ({targeting_type}) =====
Study these examples closely. Your output should match this quality and style.
{examples[:4000]}

===== PERFORMANCE DATA — WHAT ACTUALLY WORKS =====
The following shows real ad performance ranked by cost per job post.
Use this to inform your creative decisions. Lean into patterns that perform well.
Black backgrounds dominate the top performers. Quote-driven messaging outperforms
other approaches. Specific freelancer categories outperform generic talent messaging.
{context.get('performance_data', '')[:3000]}

===== VISUAL STYLE COPY RULES =====
Find the rules for "{style}" below and follow them exactly. Adapt headline length,
body format, and CTA approach based on what this visual style requires.
{copy_style_rules[:5000]}

===== YOUR ASSIGNMENT =====
Generate {qty} ad copy concepts.

Platform: {batch.get('platform', 'Meta')}
Format: {batch.get('format', 'Static Feed')}
Visual Style: {style}
Targeting: {targeting_type}
Brief: {order.get('brief', 'Showcase how Upwork helps businesses find freelancers fast')}

For each concept provide these exact fields:
- headline (max 40 characters — this goes on the ad creative AND in the ad platform headline field)
- body_short (max 125 characters — Primary Text short variant for the ad platform)
- body_long (max 300 characters — Primary Text long variant with more detail)
- description (max 25 characters — ad platform description field)
- cta (max 20 characters — this goes on the CTA button in the creative)
- concept_tag (short slug like "talent-speed-v1")
{multi_field_instructions}
RULES:
- Match the brand voice exactly — clear, concise, supportive, professional
- Use only approved claims and statistics from the section above
- Follow all compliance and legal rules
- Study the real ad examples and match their quality
- No generic marketing speak — be specific about what Upwork offers
- Headlines should follow the 95/5 rule: 95% informative, 5% personality

Return as JSON array of objects with exactly these keys: headline, body_short, body_long, description, cta, concept_tag{multi_field_keys}. No other text."""

    # Retry transient failures with backoff. Previously a single 429/5xx/timeout
    # silently returned zero concepts for the style, and stage 03 then shipped a
    # lone placeholder ("Find talent fast") while the sprint reported success.
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=120
            )

            if response.status_code == 200:
                _rj = response.json()
                text = _rj["content"][0]["text"].strip()
                _u = _rj.get("usage", {})
                _add_token_usage(sprint_id, "claude-sonnet-4-6",
                                 _u.get("input_tokens"), _u.get("output_tokens"))
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]

                parsed = json.loads(text.strip())
                if isinstance(parsed, list):
                    for j, concept in enumerate(parsed):
                        concept["concept_id"] = f"concept_{i}_{style.lower().replace(' ', '_')}_{j}"
                        concept["batch_index"] = i
                        concept["visual_style"] = style
                        concepts.append(concept)
                print(f"    {style}: {len(parsed)} concepts generated")
                return concepts

            if response.status_code in (429, 500, 502, 503, 529) and attempt < max_attempts - 1:
                wait = 2 ** attempt
                print(f"    {style}: API {response.status_code}, retry in {wait}s ({attempt+1}/{max_attempts})")
                time.sleep(wait)
                continue
            print(f"    {style}: API error {response.status_code} (gave up after {attempt+1})")
            return concepts

        except Exception as e:
            if attempt < max_attempts - 1:
                wait = 2 ** attempt
                print(f"    {style}: {str(e)[:50]}, retry in {wait}s ({attempt+1}/{max_attempts})")
                time.sleep(wait)
                continue
            print(f"    {style}: Error - {str(e)[:60]} (gave up)")
            return concepts

    return concepts


def _generate_real_copy(order, context, api_key, sprint_id=None):
    """Generate copy concepts, fanning out one call per style concurrently.

    Per-style calls are independent + I/O-bound (~120s each); a serial loop
    stacked minutes on wide orders. Bounded by COPY_CONCURRENCY (default 5)
    to respect API rate limits."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tasks = []
    for i, batch in enumerate(order.get("batches", [])):
        for style in batch.get("visual_styles", ["default"]):
            tasks.append((i, batch, style))
    total = len(tasks)
    if total == 0:
        return {"concepts": [], "generated_at": datetime.now(timezone.utc).isoformat()}

    try:
        workers = int(os.environ.get("COPY_CONCURRENCY", "5") or "5")
    except ValueError:
        workers = 5
    workers = max(1, min(workers, total))

    results = {}
    done = 0
    lock = threading.Lock()

    def _run(idx, i, batch, style):
        nonlocal done
        res = _generate_copy_for_style(i, batch, style, order, context, api_key, sprint_id)
        with lock:
            done += 1
            _save_progress(sprint_id, "stage_02_copy_gen", done, total, f"Copy: {style}")
        return idx, res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run, idx, i, batch, style)
                   for idx, (i, batch, style) in enumerate(tasks)]
        for fut in as_completed(futures):
            try:
                idx, res = fut.result()
                results[idx] = res
            except Exception as e:
                print(f"    copy task error: {str(e)[:60]}")

    concepts = []
    failed_styles = []
    for idx in range(total):
        res = results.get(idx, [])
        concepts.extend(res)
        if not res:
            failed_styles.append(tasks[idx][2])  # style name
    out = {"concepts": concepts, "generated_at": datetime.now(timezone.utc).isoformat()}
    if failed_styles:
        # Record + surface so the Gate 3 reviewer knows some styles will fall
        # back to placeholder copy — instead of silently shipping it.
        out["failed_styles"] = failed_styles
        print(f"  ⚠ {len(failed_styles)} style(s) produced NO copy "
              f"(placeholder fallback): {', '.join(failed_styles)}")
    return out


def _review_and_rank_copy(copy_outputs, order, context, api_key, sprint_id=None):
    """Self-review: Claude scores all 6 concepts per style, ranks, picks top 3.

    Groups are reviewed CONCURRENTLY (one Claude call per style, ~I/O-bound).
    A serial loop was the slow leg on wide sprints; bounded by COPY_CONCURRENCY
    (default 5), mirroring copy generation. Each reviewed concept gains:
    rank (1-6), selected (top 3), score, review_notes.
    """
    import httpx
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    concepts = copy_outputs.get("concepts", [])
    if not concepts:
        return copy_outputs

    # Group concepts by batch_index + visual_style
    groups = {}
    for c in concepts:
        key = f"{c.get('batch_index')}_{c.get('visual_style', '')}"
        if key not in groups:
            groups[key] = []
        groups[key].append(c)

    brand_voice = context.get("brand_voice", "")
    compliance = context.get("compliance", "")
    claims = context.get("approved_claims", "")
    copy_style_rules = context.get("copy_style_rules", "")

    def _review_one_group(group_key, group_concepts):
        """Review + rank one style's concepts (one Claude call)."""
        reviewed = []
        style = group_concepts[0].get("visual_style", "unknown")

        # Build the concepts as a numbered list for review
        concepts_text = ""
        for idx, c in enumerate(group_concepts, 1):
            concepts_text += f"""
Concept {idx}:
  headline: {c.get('headline', '')}
  body_short: {c.get('body_short', '')}
  body_long: {c.get('body_long', '')}
  description: {c.get('description', '')}
  cta: {c.get('cta', '')}
  concept_tag: {c.get('concept_tag', '')}
"""

        review_prompt = f"""You are a senior creative director reviewing ad copy concepts for Upwork paid acquisition.

===== BRAND VOICE RULES =====
{brand_voice[:2000]}

===== COMPLIANCE RULES =====
{compliance[:2000]}

===== APPROVED CLAIMS =====
Only these stats and claims are verified. Concepts using unverified numbers should be ranked lower.
{claims[:1500]}

===== COPY RULES FOR {style.upper()} STYLE =====
{copy_style_rules[:2000]}

===== CONCEPTS TO REVIEW =====
Visual Style: {style}
Platform: Meta
Targeting: {order.get('targeting', 'Prospecting')}

{concepts_text}

===== YOUR TASK =====
Score each concept 1-10 on these criteria:
- Brand voice alignment (does it sound like Upwork?)
- Headline impact (punchy, specific, not generic?)
- Compliance (only uses approved claims? no legal issues?)
- Style fit (does the copy work for {style} format specifically?)
- CTA strength (actionable, specific, not generic "Learn more"?)

Then rank all {len(group_concepts)} concepts from best to worst.
Select the TOP 3 as your recommended picks.

Return as JSON array with one object per concept in ranked order (best first):
[
  {{
    "original_index": 1,
    "rank": 1,
    "selected": true,
    "score": 8.5,
    "review_notes": "Strong headline, good use of approved stat, CTA is specific and actionable"
  }},
  ...
]

Return ONLY the JSON array. No other text."""

        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": review_prompt}]
                },
                timeout=120
            )

            if response.status_code == 200:
                _rj = response.json()
                text = _rj["content"][0]["text"].strip()
                _u = _rj.get("usage", {})
                _add_token_usage(sprint_id, "claude-sonnet-4-6",
                                 _u.get("input_tokens"), _u.get("output_tokens"))
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]

                rankings = json.loads(text.strip())

                # Apply rankings back to the concepts
                for ranking in rankings:
                    orig_idx = ranking.get("original_index", 1) - 1  # Convert to 0-based
                    if 0 <= orig_idx < len(group_concepts):
                        concept = group_concepts[orig_idx].copy()
                        concept["rank"] = ranking.get("rank", 99)
                        concept["selected"] = ranking.get("selected", False)
                        concept["score"] = ranking.get("score", 0)
                        concept["review_notes"] = ranking.get("review_notes", "")
                        reviewed.append(concept)

                selected_count = sum(1 for r in rankings if r.get("selected"))
                print(f"    Reviewed {style}: top {selected_count} selected")

            else:
                print(f"API error {response.status_code}, keeping all unranked")
                for c in group_concepts:
                    c["rank"] = 0
                    c["selected"] = True
                    c["score"] = 0
                    c["review_notes"] = "Review failed — kept as unranked"
                    reviewed.append(c)

        except Exception as e:
            print(f"error ({str(e)[:40]}), keeping all unranked")
            for c in group_concepts:
                c["rank"] = 0
                c["selected"] = True
                c["score"] = 0
                c["review_notes"] = f"Review error: {str(e)[:60]}"
                reviewed.append(c)
        return reviewed

    group_items = list(groups.items())
    total = len(group_items)
    try:
        workers = int(os.environ.get("COPY_CONCURRENCY", "5") or "5")
    except ValueError:
        workers = 5
    workers = max(1, min(workers, total))

    reviewed_concepts = []
    done = 0
    lock = threading.Lock()

    def _run(group_key, group_concepts):
        nonlocal done
        res = _review_one_group(group_key, group_concepts)
        with lock:
            done += 1
            _save_progress(sprint_id, "stage_02_copy_review", done, total,
                           f"Review: {group_concepts[0].get('visual_style', '')}")
        return res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run, gk, gc) for gk, gc in group_items]
        for fut in as_completed(futures):
            try:
                reviewed_concepts.extend(fut.result())
            except Exception as e:
                print(f"    review task error: {str(e)[:60]}")

    # Sort by style then rank
    reviewed_concepts.sort(key=lambda x: (x.get("visual_style", ""), x.get("rank", 99)))

    total_c = len(reviewed_concepts)
    selected = sum(1 for c in reviewed_concepts if c.get("selected"))
    print(f"  Review complete: {total_c} concepts scored, {selected} selected as top picks")

    return {
        "concepts": reviewed_concepts,
        "generated_at": copy_outputs.get("generated_at"),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "total_generated": total_c,
        "total_selected": selected,
    }


# =============================================================================
# IMAGE PROMPT BUILDER — per-style differentiation
# =============================================================================

def _build_style_prompt(style, headline, platform):
    """Build a genuinely different image prompt for each visual style."""

    base = f"No text, no logos, no watermarks. Warm natural light. Magazine quality."

    prompts = {
        "Lifestyle Photo": (
            # BRANDON UPDATE: Brian doesn't want AI-generated photography.
            # Pipeline should pull from the approved brand photo library in Figma instead.
            # This prompt is a FALLBACK only — used when no library photo is available.
            f"A confident professional person sitting at a modern desk, looking directly at the camera "
            f"with a warm, genuine smile. Shot from waist up. The person is the clear focal point, "
            f"large and prominent in the center of the frame. Person's face must be in the upper 60% "
            f"of the image — copy covers the bottom 40%. Bright, airy modern office with large "
            f"windows and natural light. Shallow depth of field keeps the background soft. "
            f"{base}"
        ),
        "Photo with Text": (
            f"A professional person at a desk, looking up from their laptop toward the camera with "
            f"a confident, approachable expression. Medium shot from chest up. The person is centered "
            f"in the frame and is clearly the subject. Clean, modern office background with warm "
            f"natural lighting. The person takes up most of the frame. Sharp focus on the face, "
            f"soft bokeh on the background. This should look like a professional headshot in context, "
            f"not a stock photo of an empty office. "
            f"{base}"
        ),
        "Testimonial": (
            f"Professional headshot portrait of a confident, friendly person. Shoulders up, centered "
            f"in the frame. The face is large, sharp, and the clear focal point. Warm, natural smile "
            f"with direct eye contact at the camera. Soft, even lighting from the front. Clean solid "
            f"background in warm cream or light grey. This should look like a real person's professional "
            f"headshot, not an AI-generated face. High resolution, sharp focus on the eyes. "
            f"{base}"
        ),
        "Graphic with Text": (
            f"Abstract illustrated graphic with geometric shapes and flowing lines in Upwork green "
            f"(#14a800) and warm amber tones on a dark charcoal background. "
            f"40% of frame occupied by the graphic, 60% clean space for text. "
            f"Modern, tech-forward, slightly three-dimensional feel. Not a photograph. "
            f"No text, no logos."
        ),
        "Split Screen": (
            f"Two contrasting scenes side by side with a clear vertical division in the center. "
            f"LEFT HALF: a stressed person with their head in their hands at a messy desk piled "
            f"with papers, crumpled notes, and coffee cups. Dim, harsh fluorescent lighting. "
            f"RIGHT HALF: a relaxed, smiling professional working on a clean laptop at a tidy desk "
            f"with bright natural window light and a plant. Both people are large and clearly visible "
            f"as the focal points of their respective halves. Shot from chest up. "
            f"{base}"
        ),
        "Us vs Them": (
            f"Two contrasting scenes side by side with a clear vertical division. "
            f"LEFT: a person looking frustrated at a cluttered desk with stacks of printed resumes, "
            f"dim overhead lighting, old monitor. RIGHT: a person smiling confidently at a clean "
            f"modern laptop, bright natural light, minimal desk. Both people are prominent, shot "
            f"from chest up, clearly the focal points. The contrast should be immediately obvious. "
            f"{base}"
        ),
        "Hybrid": (
            f"A professional person working on a laptop in a bright modern coworking space, "
            f"looking at the screen with a focused, positive expression. Medium shot from waist up. "
            f"The person is prominent and clearly the subject, positioned slightly left of center. "
            f"Clean wall or open space visible to the right of the person. Warm natural lighting. "
            f"The person takes up at least 50% of the frame. Sharp focus on the person, "
            f"soft background. "
            f"{base}"
        ),
        "Device UI": (
            f"A person's hands typing on a modern silver laptop keyboard, shot from slightly above "
            f"at a clean desk. The laptop screen is visible and blank/dark. A coffee cup and small "
            f"plant sit nearby. Warm natural side lighting. The laptop and hands are the clear "
            f"focal point, filling most of the frame. Clean, modern, aspirational. "
            f"{base}"
        ),
        "Social Media Profile": (
            f"Professional headshot portrait of a confident, friendly person. Shoulders up, "
            f"centered in the frame. Large face filling most of the frame. Warm, natural smile "
            f"with direct eye contact. Soft, even lighting. Clean solid background. "
            f"This should look like a real LinkedIn profile photo. High resolution, sharp focus. "
            f"{base}"
        ),
        "Talent Profile": (
            f"Professional headshot portrait of a skilled specialist. Shoulders up, centered "
            f"in the frame. Confident expression, direct eye contact, natural smile. "
            f"The face fills most of the frame. Clean solid background. Professional studio "
            f"lighting. Sharp focus on the eyes. "
            f"{base}"
        ),
        "Meme": (
            f"Expressive reaction photo of a relatable office moment — a person looking "
            f"overwhelmed at a laptop, or surprised by something on screen, or giving a "
            f"knowing look to camera. Candid feel, not posed. Clear top and bottom bands "
            f"for meme text overlay. "
            f"{base}"
        ),
        "Sticky Note": (
            f"Clean desk surface shot from directly above. Light wood or white desk with "
            f"minimal items — a pen, the edge of a keyboard, maybe a coffee ring stain. "
            f"Large empty center area where a sticky note graphic will be placed. "
            f"Natural overhead lighting. Warm tones. "
            f"{base}"
        ),
        "Illustration": (
            f"Professional editorial photograph of a diverse team collaborating around a "
            f"conference table with laptops and notebooks. Bright, modern office. "
            f"Clean composition with negative space at edges for text overlay. "
            f"{base}"
        ),
    }

    prompt = prompts.get(style, (
        f"Professional photo for a {platform} {style} ad about: {headline}. "
        f"Clean composition, adequate negative space for text overlay. "
        f"{base}"
    ))

    return prompt


# =============================================================================
# STAGE 03: IMAGE PROMPTS (local version)
# =============================================================================

def stage_03_image_prompts(sprint_id, order, copy_outputs):
    """Build image prompts CSV based on visual style routing."""
    print("\n" + "="*60)
    print("  STAGE 03: IMAGE PROMPTS")
    print("="*60)

    if not order.get("includes_images", True):
        print("  Skipped (copy-only order)")
        return None

    run_dir = RUNS_DIR / sprint_id
    rows = []

    # Load image style rules
    image_rules_path = BASE_DIR / "refs" / "visual_style_image_rules.txt"
    image_rules = ""
    if image_rules_path.exists():
        with open(image_rules_path) as f:
            image_rules = f.read()

    # Parse per-style rules into a lookup
    style_image_guidance = {}
    current_style = None
    current_text = []
    for line in image_rules.split("\n"):
        if line.strip() and line.strip()[0].isdigit() and ". " in line:
            if current_style:
                style_image_guidance[current_style] = "\n".join(current_text)
            current_style = line.split(". ", 1)[1].strip().upper()
            current_text = [line]
        elif current_style:
            current_text.append(line)
    if current_style:
        style_image_guidance[current_style] = "\n".join(current_text)

    concepts = (copy_outputs or {}).get("concepts", [])

    # Photo-based styles — pull from the Figma brand library, not Gemini.
    # Per Brian's rule: no AI-generated photography; people photos come from
    # Brandon's curated 2026 library.
    PHOTO_LIBRARY_STYLES = {
        "Lifestyle Photo", "Photo with Text", "Testimonial",
        "Notification",  # template has a small portrait slot we fill from library
        "Image Library",  # legacy name — same routing
        # Split Screen pulls TWO library photos — one per placeholder. The dual
        # pick is handled below by branching on DUAL_PHOTO_LIBRARY_STYLES.
        "Split Screen",
        # Hybrid (2026-06-22): dashboard mock with a real image_placeholder — fed
        # a library photo like Photo with Text.
        "Hybrid",
    }

    # Styles that only need a background (no scene generation)
    BACKGROUND_ONLY = {
        "Pie Chart", "Search Results", "Search Bar with Talent Badge",
        "Text Only", "Chat Bubble", "Reminder",
        "Poll", "Tweet / Post Mockup",
        "Text with Button", "Text with Button and Cursor",  # latter is legacy
    }

    # Styles that need no image at all. Meme templates ship with the meme
    # image baked into the template (e.g. "this-is-fine 1"); pipeline supplies
    # caption only. Adding a new meme requires a new template family from
    # Brandon, not a new pipeline-generated image.
    SKIP_IMAGE = {"Platform UI", "Meme",
                  # New graphic/UI-only styles (2026-06-22) — no photo slot; the
                  # plugin keeps their built imagery (STYLES_THAT_SKIP_IMAGE).
                  "Us vs Them", "Device UI", "Pie Chart",
                  # Profile mocks: avatar/UI baked in, no library photo slot.
                  "Social Media Profile", "Talent Profile"}

    # Pre-fetch the Figma library once if any photo-based style is in the order.
    # Cached for the duration of this stage.
    library_cache = None
    needs_library = any(
        style in PHOTO_LIBRARY_STYLES
        for batch in order.get("batches", [])
        for style in batch.get("visual_styles", [])
    )
    if needs_library:
        try:
            from figma_library import fetch_library_components
            print("  Fetching Figma photo library...")
            library_cache = fetch_library_components()
            print(f"  Library: {len(library_cache)} tagged components available")
        except Exception as e:
            print(f"  WARNING: could not fetch Figma library ({e}). Photo-based styles will fall back to Gemini.")
            library_cache = None

    for i, batch in enumerate(order.get("batches", [])):
        platform = batch.get("platform", "Meta")
        fmt = batch.get("format", "Static Feed")
        styles = batch.get("visual_styles", ["Illustration"])
        resolutions = batch.get("resolutions", [])

        for style in styles:
            # Find matching concepts — only generate images for selected (top 3) concepts
            all_matching = [c for c in concepts if c.get("batch_index") == i and c.get("visual_style") == style]
            matching = [c for c in all_matching if c.get("selected", True)]
            if not matching:
                matching = all_matching[:3] if all_matching else [{"headline": "Find talent fast", "concept_tag": "default-v1"}]

            for concept in matching:
                for res in resolutions:
                    size = res.get("size", "1080x1080")
                    ratio = res.get("ratio", "1:1")
                    # Filesystem-safe slug: styles like "Tweet / Post Mockup"
                    # contain "/", which becomes a path separator in the image
                    # filename and crashes generation. Collapse any run of
                    # non-alphanumerics to a single hyphen.
                    style_slug = re.sub(r"[^a-z0-9]+", "-", style.lower()).strip("-")
                    # Drop spaces from size too ("1440 x 1800" -> "1440x1800") so
                    # the image filename has no spaces for the Figma plugin / CSV.
                    size_slug = re.sub(r"\s+", "", str(size))
                    asset_id = f"{sprint_id}_{style_slug}_{size_slug}_{uuid.uuid4().hex[:4]}"

                    # Get style-specific image guidance
                    guidance = style_image_guidance.get(style.upper(), "")

                    figma_node_id = ""
                    figma_asset_name = ""
                    match_strength = ""
                    # Dual-image placeholders (currently used by Split Screen).
                    # Empty strings for every other style.
                    figma_node_id_left = ""
                    figma_asset_name_left = ""
                    figma_node_id_right = ""
                    figma_asset_name_right = ""

                    if style in DUAL_PHOTO_LIBRARY_STYLES and library_cache:
                        # Style needs TWO distinct library photos (one per
                        # placeholder). Pick the second with exclude_ids so it
                        # cannot collide with the first.
                        try:
                            from figma_library import pick_photo_for_asset
                            picked_left = pick_photo_for_asset(
                                visual_style=style,
                                order=order,
                                sprint_id=sprint_id,
                                components=library_cache,
                            )
                            picked_right = pick_photo_for_asset(
                                visual_style=style,
                                order=order,
                                sprint_id=sprint_id,
                                components=library_cache,
                                exclude_ids=[picked_left.get("figma_asset_id", "")] if picked_left.get("figma_asset_id") else None,
                            )
                            left_ok = picked_left.get("is_photo_based") and not picked_left.get("needs_human_selection")
                            right_ok = picked_right.get("is_photo_based") and not picked_right.get("needs_human_selection")
                            if left_ok and right_ok:
                                method = "figma_library_dual"
                                prompt = ""
                                figma_node_id_left = picked_left.get("figma_asset_id", "")
                                figma_asset_name_left = picked_left.get("figma_asset_name", "")
                                figma_node_id_right = picked_right.get("figma_asset_id", "")
                                figma_asset_name_right = picked_right.get("figma_asset_name", "")
                                # Mirror the left pick into the legacy single-photo
                                # fields so older readers/plugins still resolve to a photo.
                                figma_node_id = figma_node_id_left
                                figma_asset_name = figma_asset_name_left
                                match_strength = picked_left.get("match_strength", "")
                                print(f"    {style} — picked LEFT: {figma_asset_name_left} ({figma_node_id_left}), RIGHT: {figma_asset_name_right} ({figma_node_id_right})")
                            else:
                                method = "needs_human_selection"
                                prompt = ""
                                print(f"    {style} — NO DUAL LIBRARY MATCH — flagged for human selection (left_ok={left_ok}, right_ok={right_ok})")
                        except Exception as e:
                            method = "needs_human_selection"
                            prompt = ""
                            print(f"    {style} — dual library lookup failed: {e}")
                    elif style in PHOTO_LIBRARY_STYLES and library_cache:
                        # Pull a photo from Brandon's tagged library
                        try:
                            from figma_library import pick_photo_for_asset
                            picked = pick_photo_for_asset(
                                visual_style=style,
                                order=order,
                                sprint_id=sprint_id,
                                components=library_cache,
                            )
                            if picked.get("is_photo_based") and not picked.get("needs_human_selection"):
                                method = "figma_library"
                                prompt = ""
                                figma_node_id = picked.get("figma_asset_id", "")
                                figma_asset_name = picked.get("figma_asset_name", "")
                                match_strength = picked.get("match_strength", "")
                                print(f"    {style} — picked: {figma_asset_name} ({figma_node_id}, match={match_strength})")
                            else:
                                # No match in library — flag for human, no Gemini fallback for photo styles
                                method = "needs_human_selection"
                                prompt = ""
                                print(f"    {style} — NO LIBRARY MATCH — flagged for human selection")
                        except Exception as e:
                            method = "needs_human_selection"
                            prompt = ""
                            print(f"    {style} — library lookup failed: {e}")
                    elif style in SKIP_IMAGE:
                        method = "skip"
                        prompt = ""
                    elif style in BACKGROUND_ONLY or style == "Text Based":
                        method = "text_background"
                        prompt = (
                            f"Abstract gradient background for a {style} ad. "
                            f"Upwork green (#14a800) to dark, clean, modern. "
                            f"No text, no objects, no people. Pure background texture."
                        )
                    else:
                        method = "gemini_generate"
                        headline = concept.get("headline", "")
                        prompt = _build_style_prompt(style, headline, platform)

                    # Variant expansion: styles in MULTI_VARIANT_STYLES emit one
                    # row per registered variant. Brandon wants every variant as
                    # a separate deliverable so he can compare side-by-side.
                    variant_names = MULTI_VARIANT_STYLES.get(style, [""])
                    for variant_name in variant_names:
                        # Look up the matching template_name from the registry's
                        # style_to_template_mapping so multi-variant styles carry
                        # the right frame ID through to the plugin.
                        template_frame_id = ""
                        if variant_name:
                            reg = load_template_registry()
                            tmpl_name = (reg.get("style_to_template_mapping", {}).get(style, {}) or {}).get("template", "")
                            template_frame_id = _variant_frame_id(tmpl_name, variant_name) if tmpl_name else ""
                            # Per-variant asset_id so deliverables don't collide
                            row_asset_id = f"{asset_id}_{variant_name}"
                        else:
                            row_asset_id = asset_id

                        rows.append({
                            "asset_id": row_asset_id,
                            "sprint_id": sprint_id,
                            "batch_index": i,
                            "platform": platform,
                            "format": fmt,
                            "visual_style": style,
                            "resolution": size,
                            "ratio": ratio,
                            "generation_method": method,
                            "prompt": prompt,
                            "figma_node_id": figma_node_id,
                            "figma_asset_name": figma_asset_name,
                            "match_strength": match_strength,
                            # Dual-image fields — populated only for DUAL_PHOTO_LIBRARY_STYLES;
                            # empty strings for every other style (CSV stays uniform).
                            "figma_node_id_left": figma_node_id_left,
                            "figma_asset_name_left": figma_asset_name_left,
                            "figma_node_id_right": figma_node_id_right,
                            "figma_asset_name_right": figma_asset_name_right,
                            # Variant fields — non-empty only for MULTI_VARIANT_STYLES.
                            "variant_name": variant_name,
                            "template_frame_id": template_frame_id,
                            "concept_tag": concept.get("concept_tag", ""),
                            "headline": concept.get("headline", ""),
                        })

    csv_path = run_dir / "image_prompts.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"  Total assets: {len(rows)}")
    methods = {}
    for r in rows:
        m = r["generation_method"]
        methods[m] = methods.get(m, 0) + 1
    for m, c in methods.items():
        print(f"    {m}: {c}")
    print(f"  Saved: {csv_path}")

    return rows


# =============================================================================
# STAGE 04: IMAGE GENERATION (local version)
# =============================================================================

def stage_04_generate_images(sprint_id, image_rows):
    """Generate images using Gemini, save to local runs folder."""
    print("\n" + "="*60)
    print("  STAGE 04: IMAGE GENERATION")
    print("="*60)

    if not image_rows:
        print("  No image rows to process")
        return {}

    # Skip Gemini entirely when every row is library-fed or otherwise non-Gemini.
    # Importing google.genai eagerly here used to crash library-only sprints when
    # the package wasn't installed.
    NON_GEMINI_METHODS = {"figma_library", "needs_human_selection", "skip"}
    needs_gemini = any(r.get("generation_method") not in NON_GEMINI_METHODS for r in image_rows)
    if not needs_gemini:
        print(f"  All {len(image_rows)} rows are library-fed — no Gemini calls needed.")
        return {}

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        print("  No GEMINI_API_KEY set. Skipping image generation.")
        return {}

    run_dir = RUNS_DIR / sprint_id
    images_dir = run_dir / "images"
    images_dir.mkdir(exist_ok=True)

    try:
        from google import genai
        from google.genai import types
        from PIL import Image
        from io import BytesIO
    except ImportError as exc:
        print(f"  google-genai or Pillow not installed: {exc}")
        print("  Skipping image generation. Install with: pip install google-genai pillow")
        return {}

    client = genai.Client(api_key=gemini_key)
    results = {}
    generated = 0
    skipped = 0
    failed = 0

    # Group by prompt to avoid generating the same image multiple times
    # Then resize for each resolution.
    prompt_groups = {}
    for row in image_rows:
        if row["generation_method"] in NON_GEMINI_METHODS:
            skipped += 1
            continue
        prompt = row["prompt"]
        if prompt not in prompt_groups:
            prompt_groups[prompt] = []
        prompt_groups[prompt].append(row)

    # Review criteria per style category
    REVIEW_CRITERIA = {
        "people_focused": [
            "Lifestyle Photo", "Photo with Text", "Hybrid", "Split Screen",
            "Us vs Them", "Meme", "Illustration"
        ],
        "portrait": [
            "Testimonial", "Social Media Profile", "Talent Profile"
        ],
        "environment": [
            "Device UI", "Sticky Note"
        ],
    }

    def _get_style_category(style):
        for cat, styles in REVIEW_CRITERIA.items():
            if style in styles:
                return cat
        return "people_focused"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    img_total = len(prompt_groups)
    img_idx = 0
    for prompt, rows in prompt_groups.items():
        style = rows[0]["visual_style"]
        headline = rows[0].get("headline", "")
        category = _get_style_category(style)
        max_attempts = 3

        img_idx += 1
        _save_progress(sprint_id, "stage_04_generate_images", img_idx, img_total,
                       f"Image: {style}")

        print(f"\n  Generating: {style} — \"{headline[:40]}\"")

        master_image = None
        attempt = 0
        current_prompt = prompt

        while attempt < max_attempts:
            attempt += 1
            print(f"    Attempt {attempt}/{max_attempts}...", end=" ", flush=True)

            try:
                response = client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=current_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"]
                    )
                )

                candidate_image = None
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        candidate_image = Image.open(BytesIO(part.inline_data.data))
                        break

                if not candidate_image:
                    print("no image returned, retrying")
                    time.sleep(2)
                    continue

                # Save temp image for review
                temp_path = images_dir / f"_temp_review.png"
                candidate_image.save(str(temp_path), "PNG", quality=95)

                # Self-review: Claude looks at the image
                if api_key:
                    review = _review_image(temp_path, style, category, headline, api_key)
                    score = review.get("score", 7)
                    passed = review.get("passed", True)
                    notes = review.get("notes", "")

                    if passed:
                        print(f"approved (score: {score}/10)")
                        if notes:
                            print(f"      Review: {notes[:80]}")
                        master_image = candidate_image
                        break
                    else:
                        print(f"rejected (score: {score}/10)")
                        print(f"      Issue: {notes[:80]}")
                        # Adjust prompt based on feedback
                        fix = review.get("fix", "")
                        if fix and attempt < max_attempts:
                            current_prompt = prompt + f" IMPORTANT: {fix}"
                            print(f"      Adjusting prompt and retrying...")
                        time.sleep(2)
                        continue
                else:
                    # No API key for review, accept the image
                    print("generated (no review)")
                    master_image = candidate_image
                    break

            except Exception as e:
                print(f"error: {str(e)[:60]}")
                time.sleep(2)

        # Clean up temp
        temp_path = images_dir / f"_temp_review.png"
        if temp_path.exists():
            temp_path.unlink()

        if not master_image:
            print(f"    Failed after {max_attempts} attempts")
            failed += len(rows)
            continue

        # Resize and crop for each resolution
        for row in rows:
            size = row["resolution"]
            # Parse a WxH pixel size defensively. A ratio ("1:1") or malformed
            # value used to unpack-crash and abort the whole stage; skip the row
            # and count it failed instead.
            m = re.search(r"(\d+)\s*[x×]\s*(\d+)", str(size))
            if not m:
                print(f"    Skipping {row.get('asset_id', '?')}: bad resolution {size!r}")
                failed += 1
                continue
            w, h = int(m.group(1)), int(m.group(2))
            resized = _resize_and_crop(master_image, w, h)

            img_path = images_dir / f"{row['asset_id']}.png"
            resized.save(str(img_path), "PNG", quality=95)
            results[row["asset_id"]] = str(img_path)
            generated += 1

        time.sleep(2)

    print(f"\n  Generated: {generated} | Skipped (library): {skipped} | Failed: {failed}")

    # Save generation log
    log_path = run_dir / "generation_log.json"
    with open(log_path, "w") as f:
        json.dump({
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
            "results": {k: str(v) for k, v in results.items()}
        }, f, indent=2)

    return results


def _review_image(image_path, style, category, headline, api_key):
    """Claude reviews a generated image for quality and style fit.

    Returns: {"score": 1-10, "passed": bool, "notes": str, "fix": str}
    """
    import httpx, base64

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    criteria_by_category = {
        "people_focused": (
            "1. Is there a person clearly visible as the main subject? They should be large and prominent, not tiny or far away.\n"
            "2. Is the person's face clearly visible and not cut off at the top of the frame?\n"
            "3. Does the person look natural and professional, not distorted or AI-generated looking?\n"
            "4. Is the lighting warm and natural, not flat or harsh?\n"
            "5. Is the overall composition clean and professional, like a magazine ad photo?"
        ),
        "portrait": (
            "1. Is there a clear headshot of one person's face filling most of the frame?\n"
            "2. Is the face centered, sharp, and not cut off?\n"
            "3. Does the person look natural, friendly, and professional?\n"
            "4. Is the background clean and undistracting?\n"
            "5. Would this work as a professional profile photo?"
        ),
        "environment": (
            "1. Is the scene clean, modern, and professional looking?\n"
            "2. Is there a clear focal point (desk, laptop, workspace)?\n"
            "3. Is the lighting warm and natural?\n"
            "4. Does it look like a real photograph, not AI-generated?\n"
            "5. Is the composition balanced and intentional?"
        ),
    }

    criteria = criteria_by_category.get(category, criteria_by_category["people_focused"])

    review_prompt = f"""You are a creative director reviewing an AI-generated image for a paid acquisition ad.

Visual Style: {style}
Ad Headline: {headline}
Image Category: {category}

Review this image against these criteria:
{criteria}

Score the image 1-10 where:
- 8-10: Good to go, looks professional and matches the style
- 5-7: Acceptable but has issues
- 1-4: Reject, has major problems

Respond with ONLY a JSON object:
{{
  "score": <number 1-10>,
  "passed": <true if score >= 7, false otherwise>,
  "notes": "<one sentence explaining the score>",
  "fix": "<if rejected, one sentence telling the image generator what to fix. empty string if passed>"
}}"""

    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                        {"type": "text", "text": review_prompt}
                    ]
                }]
            },
            timeout=30
        )

        if response.status_code == 200:
            text = response.json()["content"][0]["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        else:
            return {"score": 7, "passed": True, "notes": "Review API error, accepting", "fix": ""}

    except Exception as e:
        return {"score": 7, "passed": True, "notes": f"Review error: {str(e)[:40]}", "fix": ""}


def _resize_and_crop(image, width, height):
    """Resize and center-crop to exact dimensions."""
    from PIL import Image as PILImage

    img_ratio = image.width / image.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(height * img_ratio)
    else:
        new_w = width
        new_h = int(width / img_ratio)

    image = image.resize((new_w, new_h), PILImage.Resampling.LANCZOS)

    left = (new_w - width) // 2
    top = (new_h - height) // 2

    return image.crop((left, top, left + width, top + height))


# =============================================================================
# STAGE 05: FIGMA ASSEMBLY (local version - placeholder)
# =============================================================================

def stage_05_figma_assembly(sprint_id, image_rows, image_results):
    """Prepare assets for Figma plugin assembly.

    The Figma REST API cannot fill image layers — that requires the Figma Plugin API.
    This stage prepares the asset_manifest.csv that the Figma plugin reads,
    copies raw images to exports/ as fallback, and prints instructions for
    running the plugin in Figma.

    Workflow:
    1. Pipeline generates images (Stage 04) and saves to images/
    2. This stage copies them to exports/ and builds the manifest
    3. User opens Figma, runs the Upwork Pipeline Assembly plugin
    4. Plugin reads manifest + images, fills templates, exports final PNGs
    """
    print("\n" + "="*60)
    print("  STAGE 05: FIGMA ASSEMBLY")
    print("="*60)

    import shutil

    run_dir = RUNS_DIR / sprint_id
    exports_dir = run_dir / "exports"
    exports_dir.mkdir(exist_ok=True)

    # Mirror raw images into exports/ as pre-assembly versions. Use hardlinks
    # (not copies): a full-res sprint is ~66 PNGs at 2–3 MB each, and copying
    # each twice tripled on-disk size and overran the volume ([Errno 28]).
    # Hardlinks share the same inode/bytes — nothing rewrites these files in
    # place after creation, so it's safe. Fall back to copy if link fails
    # (e.g., cross-device).
    copied = 0
    for asset_id, img_path in image_results.items():
        src = Path(img_path)
        if src.exists():
            for suffix in ("", "_final"):
                dst = exports_dir / f"{asset_id}{suffix}.png"
                try:
                    if dst.exists():
                        dst.unlink()
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
            copied += 1

    # Check if Figma plugin is available
    plugin_dir = BASE_DIR / "plugin"
    has_plugin = (plugin_dir / "code.js").exists()

    print(f"  Images copied to exports/: {copied}")

    if has_plugin:
        print(f"\n  Figma Plugin Assembly available.")
        print(f"  To assemble with branded templates:")
        print(f"    1. Open Figma > Paid Acquisition 2026")
        print(f"    2. Plugins > Development > Upwork Pipeline Assembly")
        print(f"    3. Load: {run_dir / 'asset_manifest.csv'}")
        print(f"    4. Select images from: {exports_dir}")
        print(f"    5. Click 'Assemble All Assets'")
    else:
        print(f"  Figma plugin not found at plugin/")
        print(f"  Raw images available at: {exports_dir}")

    print(f"\n  Note: Raw images are usable without Figma assembly.")
    print(f"  The plugin adds branded template frames with logo, CTA, and text.")


# =============================================================================
# STAGE 06: DELIVER (local version)
# =============================================================================

def stage_06_deliver(sprint_id, order, copy_outputs, image_rows, image_results):
    """Package everything into a manifest CSV and summary."""
    print("\n" + "="*60)
    print("  STAGE 06: DELIVER")
    print("="*60)

    run_dir = RUNS_DIR / sprint_id
    exports_dir = run_dir / "exports"

    # Build manifest CSV in Deliverables Grid format
    manifest_rows = []
    concepts = (copy_outputs or {}).get("concepts", [])

    for row in (image_rows or []):
        asset_id = row["asset_id"]
        img_path = image_results.get(asset_id, "")
        export_path = exports_dir / f"{asset_id}_final.png" if exports_dir.exists() else ""
        has_export = Path(export_path).exists() if export_path else False

        # Find matching concept. Normalize batch_index to string for comparison —
        # row may come from a CSV reload where the value is a string, but the
        # concept dict from copy_outputs.json has it as int.
        row_bi = str(row.get("batch_index", ""))
        row_style = row.get("visual_style", "")
        row_concept_tag = row.get("concept_tag", "")

        # Prefer exact concept_tag match (so each image row gets the right
        # one of the 3 selected concepts for its style). Fall back to first
        # by visual_style if concept_tag isn't set.
        concept = next(
            (c for c in concepts
             if str(c.get("batch_index", "")) == row_bi
             and c.get("visual_style", "") == row_style
             and c.get("concept_tag", "") == row_concept_tag),
            None
        )
        if concept is None:
            concept = next(
                (c for c in concepts
                 if str(c.get("batch_index", "")) == row_bi
                 and c.get("visual_style", "") == row_style),
                {}
            )

        manifest_rows.append({
            # Order form fields
            "Delivery_Date": order.get("delivery_date", ""),
            "Driver": order.get("driver", ""),
            "Targeting": order.get("targeting", ""),
            "Deliverable_Type": order.get("deliverable", ""),
            "Platform": row.get("platform", ""),
            "Format": row.get("format", ""),
            "Resolutions": row.get("resolution", ""),
            "Visual_Style": row.get("visual_style", ""),
            "Additional_Info": order.get("brief", ""),
            "Ads_Base_Count": 1,
            # Copy fields — map to Figma layer names
            "Primary_Text_Short": concept.get("body_short", concept.get("body", "")),
            "Primary_Text_Long": concept.get("body_long", ""),
            "Headline_On_Creative": concept.get("headline", row.get("headline", "")),
            "Headline": concept.get("headline", row.get("headline", "")),
            "Description": concept.get("description", ""),
            "CTA": concept.get("cta", ""),
            # Pie Chart data value (0-100) parsed from the copy — drives the slice
            # angle + center callout in the plugin. Empty for non-chart styles.
            "Chart_Pct": _extract_chart_pct(concept, row)
                if str(row.get("visual_style", "")).strip().lower().replace(" ", "") == "piechart" else "",
            # Multi-field copy (Us vs Them / Sticky Note). Empty for other styles;
            # bullet lists flattened with "|" (plugin splits them).
            "Us_Headline": concept.get("us_headline", ""),
            "Them_Headline": concept.get("them_headline", ""),
            "Us_Bullets": _join_bullets(concept.get("us_bullets")),
            "Them_Bullets": _join_bullets(concept.get("them_bullets")),
            "Left_Headline": concept.get("left_headline", ""),
            "Right_Headline": concept.get("right_headline", ""),
            "Left_Bullets": _join_bullets(concept.get("left_bullets")),
            "Right_Bullets": _join_bullets(concept.get("right_bullets")),
            # Review fields
            "rank": concept.get("rank", ""),
            "selected": concept.get("selected", ""),
            "score": concept.get("score", ""),
            "review_notes": concept.get("review_notes", ""),
            # Pipeline tracking fields
            "asset_id": asset_id,
            "concept_tag": concept.get("concept_tag", row.get("concept_tag", "")),
            # Image source fields — figma_node_id signals to the assembly plugin
            # to pull the photo from the Figma library instead of using a PNG.
            "generation_method": row.get("generation_method", ""),
            "figma_node_id": row.get("figma_node_id", ""),
            "figma_asset_name": row.get("figma_asset_name", ""),
            "match_strength": row.get("match_strength", ""),
            # Dual-image fields — populated for Split Screen and any future
            # DUAL_PHOTO_LIBRARY_STYLES. Plugin fills left_image_placeholder
            # and right_image_placeholder from these when present.
            "figma_node_id_left": row.get("figma_node_id_left", ""),
            "figma_asset_name_left": row.get("figma_asset_name_left", ""),
            "figma_node_id_right": row.get("figma_node_id_right", ""),
            "figma_asset_name_right": row.get("figma_asset_name_right", ""),
            # Variant fields — non-empty only for MULTI_VARIANT_STYLES (Text Only).
            # template_frame_id lets the plugin clone the exact variant frame
            # instead of grabbing the first name-matched template.
            "variant_name": row.get("variant_name", ""),
            "template_frame_id": row.get("template_frame_id", ""),
            "image_file": str(img_path) if img_path else "",
            "export_file": str(export_path) if has_export else "",
            "status": "delivered" if has_export else "pending_assembly"
        })

    # Write manifest CSV (selected assets only — the deliverables grid)
    manifest_path = run_dir / "asset_manifest.csv"
    if manifest_rows:
        fieldnames = list(manifest_rows[0].keys())
        with open(manifest_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(manifest_rows)

    # Write FULL copy review CSV — ALL concepts including rejected
    # This is for human review: see everything Claude generated, what was selected, and why
    review_path = run_dir / "copy_review.csv"
    review_rows = []
    for c in concepts:
        review_rows.append({
            "Visual_Style": c.get("visual_style", ""),
            "rank": c.get("rank", ""),
            "selected": "YES" if c.get("selected") else "NO",
            "score": c.get("score", ""),
            "Headline_On_Creative": c.get("headline", ""),
            "Primary_Text_Short": c.get("body_short", c.get("body", "")),
            "Primary_Text_Long": c.get("body_long", ""),
            "Description": c.get("description", ""),
            "CTA": c.get("cta", ""),
            "concept_tag": c.get("concept_tag", ""),
            "review_notes": c.get("review_notes", ""),
        })

    if review_rows:
        review_fieldnames = list(review_rows[0].keys())
        with open(review_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=review_fieldnames)
            writer.writeheader()
            writer.writerows(review_rows)

    # Write run summary
    total_concepts = len(concepts)
    selected_concepts = sum(1 for c in concepts if c.get("selected"))
    summary = {
        "sprint_id": sprint_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "driver": order.get("driver", ""),
        "platform": order.get("platform", ""),
        "total_assets": len(manifest_rows),
        "delivered": sum(1 for r in manifest_rows if r["status"] == "delivered"),
        "pending_assembly": sum(1 for r in manifest_rows if r["status"] == "pending_assembly"),
        "total_concepts_generated": total_concepts,
        "concepts_selected": selected_concepts,
        "concepts_rejected": total_concepts - selected_concepts,
    }

    summary_path = run_dir / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"  Copy concepts: {total_concepts} generated, {selected_concepts} selected, {total_concepts - selected_concepts} rejected")
    print(f"  Total assets: {summary['total_assets']} (images for selected concepts only)")
    print(f"  Delivered: {summary['delivered']}")
    print(f"  Pending assembly: {summary['pending_assembly']}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Copy review: {review_path}")
    print(f"  Summary: {summary_path}")

    return summary


# =============================================================================
# CSV ORDER PARSER
# =============================================================================

def parse_csv_order(csv_path):
    """Parse the CSV from the order form into a pipeline payload."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Empty CSV")
        return None

    first = rows[0]

    # Group rows by platform+format to build batches
    batches_map = {}
    style_quantities = {}  # track qty per style

    # Normalize style names
    STYLE_NAME_MAP = {
        "Lifestyle Photo (full bleed)": "Lifestyle Photo",
        "Photo with Text (Upwork shell)": "Photo with Text",
    }

    for row in rows:
        key = f"{row.get('platform', '')}|{row.get('format', '')}"
        if key not in batches_map:
            batches_map[key] = {
                "platform": row.get("platform", ""),
                "format": row.get("format", ""),
                "visual_styles": [],
                "style_quantities": {},
                "resolutions": [],
                "quantity": 0,
            }
        batch = batches_map[key]

        style = row.get("visual_style", "")
        style = STYLE_NAME_MAP.get(style, style)
        # Normalize resolution: "1440 x 1800" -> "1440x1800"
        res = row.get("resolution", "").replace(" x ", "x").replace(" × ", "x").strip()
        ratio = row.get("ratio", "")
        qty = int(row.get("quantity", 1))

        if style and style not in batch["visual_styles"]:
            batch["visual_styles"].append(style)
        if style:
            batch["style_quantities"][style] = qty

        if res:
            res_entry = {"size": res, "ratio": ratio}
            if res_entry not in batch["resolutions"]:
                batch["resolutions"].append(res_entry)

        # Total quantity = sum of all style quantities
        batch["quantity"] = sum(batch["style_quantities"].values())

    payload = {
        "delivery_date": first.get("delivery_date", datetime.now().strftime("%Y-%m-%d")),
        "driver": first.get("driver", "Local Test"),
        "targeting": first.get("targeting", "Prospecting"),
        "deliverable": first.get("deliverable", "images-copy"),
        "brief": first.get("brief", ""),
        "batches": list(batches_map.values()),
    }

    return payload


# =============================================================================
# TEST ORDER
# =============================================================================

def get_test_order():
    """Built-in test order for quick testing."""
    return {
        "delivery_date": datetime.now().strftime("%Y-%m-%d"),
        "driver": "Local Test",
        "targeting": "Prospecting",
        "deliverable": "images-copy",
        "brief": "Showcase how Upwork helps businesses find freelancers fast.",
        "batches": [
            {
                "platform": "Meta",
                "format": "Static Feed",
                "quantity": 1,
                "visual_styles": ["Illustration"],
                "resolutions": [
                    {"size": "1080x1080", "ratio": "1:1"},
                ],
            }
        ],
    }


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_full_pipeline(payload):
    """Run all stages in sequence."""

    print("\n" + "#"*60)
    print("  UPWORK CREATIVE PIPELINE - LOCAL RUN")
    print("#"*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Driver: {payload.get('driver', 'unknown')}")
    print(f"  Platform: {payload.get('batches', [{}])[0].get('platform', 'unknown')}")
    print("#"*60)

    # Gate 1 is the order form itself — the human already approved by clicking Submit.
    # The pipeline starts at Gate 2.

    # Stage 00: Intake
    result = stage_00_intake(payload)
    if not result:
        print("\nPipeline stopped: intake validation failed")
        return
    sprint_id, order = result

    # Stage 01: Load Refs
    context = stage_01_load_refs(sprint_id, order)

    # ── GATE 2: ORDER + REFS CONFIRMATION ──────────────────────
    _save_pipeline_state(sprint_id, "awaiting_gate_2")

    # Build order summary for display
    batch = order.get("batches", [{}])[0]
    styles = batch.get("visual_styles", [])
    style_qtys = batch.get("style_quantities", {})
    resolutions = [r["size"] for r in batch.get("resolutions", [])]
    brief = order.get("brief", "")

    refs_path = BASE_DIR / "configs" / "refs_context.json"
    refs_loaded = 0
    if refs_path.exists():
        import os
        refs_size = os.path.getsize(refs_path) / 1024
        with open(refs_path) as f:
            refs_data = json.load(f)
        refs_loaded = sum(1 for k, v in refs_data.items()
                         if isinstance(v, str) and len(v) > 100)

    review_items = [
        f"",
        f"  ORDER SUMMARY",
        f"  Sprint: {sprint_id}",
        f"  Driver: {order.get('driver', '')}",
        f"  Platform: {order.get('platform', '')} / {batch.get('format', '')}",
        f"  Targeting: {order.get('targeting', '')}",
        f"  Delivery: {order.get('delivery_date', '')}",
        f"  Styles: {', '.join(f'{s} x{style_qtys.get(s, 1)}' for s in styles)}",
        f"  Resolutions: {', '.join(resolutions)}",
        f"  Brief: {brief[:80]}{'...' if len(brief) > 80 else '' if brief else '(none)'}",
        f"",
        f"  REFERENCE DOCUMENTS",
        f"  Loaded: {refs_loaded} documents from refs_context.json ({refs_size:.0f} KB)" if refs_loaded else "  refs_context.json not found — run: python3 pipeline/build_refs.py",
        f"  Priority: order brief overrides standing reference docs" if brief else "  No brief — using reference docs only",
        f"",
        f"  Confirm this order and these references are correct.",
        f"  No API credits spent yet — this is the last free checkpoint.",
    ]

    _print_gate(2, "ORDER + REFS CONFIRMATION", sprint_id, review_items)
    return sprint_id


def run_pipeline_auto(payload):
    """Run all stages end-to-end without gate pauses.

    Designed for web-triggered runs (POST /submit). All human-in-the-loop
    gates are skipped; the pipeline runs straight through to delivery.
    State is written to pipeline_state.json after each stage so the caller
    can poll /sprints/{sprint_id} for progress.
    """
    print("\n" + "#"*60)
    print("  UPWORK CREATIVE PIPELINE - AUTO RUN (no gates)")
    print("#"*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Driver: {payload.get('driver', 'unknown')}")
    print(f"  Platform: {payload.get('batches', [{}])[0].get('platform', 'unknown')}")
    print("#"*60)

    # Stage 00: Intake
    result = stage_00_intake(payload)
    if not result:
        print("\nPipeline stopped: intake validation failed")
        return None
    sprint_id, order = result
    _save_pipeline_state(sprint_id, "stage_01_load_refs")

    # Stage 01: Load Refs
    context = stage_01_load_refs(sprint_id, order)
    _save_pipeline_state(sprint_id, "stage_02_copy_gen")

    # Stage 02: Copy Generation
    copy_outputs = stage_02_copy_gen(sprint_id, order, context)
    _save_pipeline_state(sprint_id, "stage_03_image_prompts")

    # Stage 03: Image Prompts (uses copy_review.csv if present, else copy_outputs)
    run_dir = RUNS_DIR / sprint_id
    _apply_copy_overrides(run_dir, copy_outputs or {})
    image_rows = stage_03_image_prompts(sprint_id, order, copy_outputs)
    _save_pipeline_state(sprint_id, "stage_04_generate_images")

    # Stage 04: Image Generation
    image_results = stage_04_generate_images(sprint_id, image_rows or [])
    _save_pipeline_state(sprint_id, "stage_05_figma_assembly")

    # Stage 05: Figma Assembly
    stage_05_figma_assembly(sprint_id, image_rows or [], image_results or {})
    _save_pipeline_state(sprint_id, "stage_06_deliver")

    # Stage 06: Deliver
    summary = stage_06_deliver(sprint_id, order, copy_outputs, image_rows, image_results or {})
    _save_pipeline_state(sprint_id, "complete")

    print("\n" + "#"*60)
    print(f"  AUTO RUN COMPLETE — Sprint {sprint_id}")
    print(f"  Assets: {summary.get('total_assets', 0)} | Delivered: {summary.get('delivered', 0)}")
    print("#"*60 + "\n")

    return sprint_id


def resume_gate_2(sprint_id):
    """Gate 2 approved: Order + refs confirmed. Run copy gen, then pause at Gate 3."""
    run_dir = RUNS_DIR / sprint_id
    order = _load_json(run_dir / "order.json")
    context = _load_json(run_dir / "context.json")

    _print_resume(sprint_id, 2, "Order + refs confirmed")

    # Stage 02: Copy Generation (6x + self-review)
    copy_outputs = stage_02_copy_gen(sprint_id, order, context)

    # ── GATE 3: COPY APPROVAL ──────────────────────────────────
    _save_pipeline_state(sprint_id, "awaiting_gate_3")
    total = len(copy_outputs.get("concepts", []))
    selected = sum(1 for c in copy_outputs.get("concepts", []) if c.get("selected"))
    _print_gate(3, "COPY APPROVAL", sprint_id, [
        f"Review: {run_dir / 'copy_review.csv'}",
        f"All {total} concepts with scores, rankings, and review notes",
        f"Claude selected top {selected} — edit 'selected' column to YES/NO to override",
        f"No images generated yet — this is the last stop before spending image credits",
    ])
    return sprint_id


def resume_gate_3(sprint_id):
    """Gate 3 approved: Copy approved. Build image prompts, then pause at Gate 4."""
    run_dir = RUNS_DIR / sprint_id
    order = _load_json(run_dir / "order.json")
    copy_outputs = _load_json(run_dir / "copy_outputs.json")

    _print_resume(sprint_id, 3, "Copy approved")

    # Apply human overrides from copy_review.csv
    _apply_copy_overrides(run_dir, copy_outputs)

    selected_count = sum(1 for c in copy_outputs.get("concepts", []) if c.get("selected"))
    print(f"  Selected concepts: {selected_count}")

    # Stage 03: Image Prompts (only for selected concepts)
    image_rows = stage_03_image_prompts(sprint_id, order, copy_outputs)

    # ── GATE 4: IMAGE PROMPT SCAN ──────────────────────────────
    _save_pipeline_state(sprint_id, "awaiting_gate_4")
    _print_gate(4, "IMAGE PROMPT SCAN", sprint_id, [
        f"Review: {run_dir / 'image_prompts.csv'}",
        f"{len(image_rows or [])} image prompts ready for generation",
        f"Check: prompts are on-brand, compositions match templates, no weird subjects",
        f"Edit the 'prompt' column to fix any issues before generation",
        f"This is the last stop before spending Gemini image credits",
    ])
    return sprint_id


def resume_gate_4(sprint_id):
    """Gate 4 approved: Prompts approved. Generate images, then pause at Gate 5."""
    run_dir = RUNS_DIR / sprint_id

    _print_resume(sprint_id, 4, "Image prompts approved")

    # Re-read image prompts (human may have edited them)
    image_rows = _load_csv(run_dir / "image_prompts.csv")
    print(f"  Image prompts: {len(image_rows)}")

    # Stage 04: Image Generation
    image_results = stage_04_generate_images(sprint_id, image_rows)

    # Stage 05: Figma Assembly
    stage_05_figma_assembly(sprint_id, image_rows, image_results)

    # ── GATE 5: ASSEMBLY REVIEW ────────────────────────────────
    _save_pipeline_state(sprint_id, "awaiting_gate_5")
    _print_gate(5, "ASSEMBLY REVIEW", sprint_id, [
        f"Review images: {run_dir / 'images'}",
        f"Review exports: {run_dir / 'exports'}",
        f"{len(image_results)} images generated",
        f"Delete any images you don't want in the final delivery",
        f"Run the Figma plugin if you haven't already",
    ])
    return sprint_id


def resume_gate_5(sprint_id):
    """Gate 5 approved: Assembly approved. Deliver, then pause at Gate 6."""
    run_dir = RUNS_DIR / sprint_id
    order = _load_json(run_dir / "order.json")
    copy_outputs = _load_json(run_dir / "copy_outputs.json")

    _print_resume(sprint_id, 5, "Assembly approved")

    # Re-read what's on disk (human may have deleted images)
    image_rows = _load_csv(run_dir / "image_prompts.csv")
    image_results = _scan_images(run_dir / "images")
    print(f"  Images approved: {len(image_results)}")

    # Stage 06: Deliver
    summary = stage_06_deliver(sprint_id, order, copy_outputs, image_rows, image_results)

    # ── GATE 6: FINAL QA ──────────────────────────────────────
    _save_pipeline_state(sprint_id, "awaiting_gate_6")
    _print_gate(6, "FINAL QA", sprint_id, [
        f"Review the complete deliverables package:",
        f"  Manifest: {run_dir / 'asset_manifest.csv'}",
        f"  Copy review: {run_dir / 'copy_review.csv'}",
        f"  Exports: {run_dir / 'exports'}",
        f"  Summary: {run_dir / 'run_summary.json'}",
        f"Assets: {summary.get('total_assets', 0)} | Delivered: {summary.get('delivered', 0)}",
        f"Approve to mark this sprint as COMPLETE",
    ])
    return sprint_id


def resume_gate_6(sprint_id):
    """Gate 6 approved: Final QA passed. Mark sprint complete."""
    run_dir = RUNS_DIR / sprint_id

    _print_resume(sprint_id, 6, "Final QA approved")
    _save_pipeline_state(sprint_id, "complete")

    summary = _load_json(run_dir / "run_summary.json")

    print("\n" + "#"*60)
    print("  PIPELINE COMPLETE — SPRINT APPROVED")
    print("#"*60)
    print(f"  Sprint: {sprint_id}")
    print(f"  Output: {run_dir}")
    print(f"  Assets: {summary.get('total_assets', 0)}")
    print(f"  Delivered: {summary.get('delivered', 0)}")
    print(f"\n  Files:")
    print(f"    order.json         - validated order")
    print(f"    context.json       - brand references")
    print(f"    copy_outputs.json  - generated ad copy")
    print(f"    copy_review.csv    - ALL concepts with rank, score, and review notes")
    print(f"    image_prompts.csv  - prompt routing table")
    print(f"    images/            - generated PNGs")
    print(f"    exports/           - assembled finals")
    print(f"    asset_manifest.csv - deliverables grid (selected concepts + images)")
    print(f"    run_summary.json   - run stats")
    print(f"\n  Sprint {sprint_id} is APPROVED and COMPLETE.")
    print("#"*60 + "\n")


# =============================================================================
# GATE HELPERS
# =============================================================================


# ---- Burn-rate counter -------------------------------------------------------
# Rough $/1M-token pricing for the estimate. Update when models/prices change.
_TOKEN_PRICING = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8":   (5.0, 25.0),
    "claude-haiku-4-5":  (1.0, 5.0),
}
_TOKEN_LOCK = threading.Lock()


def _estimate_cost(by_model):
    total = 0.0
    for model, u in by_model.items():
        pin, pout = _TOKEN_PRICING.get(model, (0.0, 0.0))
        total += (u.get("input_tokens", 0) / 1_000_000) * pin
        total += (u.get("output_tokens", 0) / 1_000_000) * pout
    return total


def _add_token_usage(sprint_id, model, input_tokens, output_tokens):
    """Accumulate LLM token usage for the burn-rate counter. Thread-safe
    (copy-gen runs concurrently) and best-effort — never breaks the pipeline."""
    if not sprint_id:
        return
    try:
        with _TOKEN_LOCK:
            path = RUNS_DIR / sprint_id / "token_usage.json"
            try:
                data = json.loads(path.read_text())
            except Exception:
                data = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "by_model": {}}
            it, ot = int(input_tokens or 0), int(output_tokens or 0)
            data["input_tokens"] += it
            data["output_tokens"] += ot
            data["calls"] = data.get("calls", 0) + 1
            bm = data.setdefault("by_model", {}).setdefault(
                model, {"input_tokens": 0, "output_tokens": 0, "calls": 0})
            bm["input_tokens"] += it
            bm["output_tokens"] += ot
            bm["calls"] += 1
            data["estimated_cost_usd"] = round(_estimate_cost(data["by_model"]), 4)
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2))
            os.replace(tmp, path)
    except Exception:
        pass


def _save_pipeline_state(sprint_id, state):
    """Save current pipeline state so we know where to resume. Atomic write
    (temp + os.replace) so a concurrent SSE/status reader never sees a torn
    file — consistent with token_usage.json / progress.json."""
    state_path = RUNS_DIR / sprint_id / "pipeline_state.json"
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }, indent=2))
    os.replace(tmp, state_path)


def _save_progress(sprint_id, stage, item_index, item_total, item_label):
    """Write sub-stage progress (N/total + heartbeat) for the live progress bar.

    Best-effort: a slow style shouldn't be invisible for minutes, but progress
    reporting must never break the pipeline. Written to a sibling progress.json
    so it can't clobber the coarse awaiting_gate_* transitions in
    pipeline_state.json. The SSE endpoint (main.py) reads both."""
    if not sprint_id:
        return
    try:
        progress_path = RUNS_DIR / sprint_id / "progress.json"
        tmp = progress_path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump({
                "sprint_id": sprint_id,
                "current_stage": stage,
                "item_index": item_index,
                "item_total": item_total,
                "item_label": item_label,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f)
        os.replace(tmp, progress_path)  # atomic — reader never sees a half-write
    except Exception:
        pass


def _print_gate(gate_num, title, sprint_id, review_items):
    """Print a standardized gate pause message."""
    print("\n" + "!"*60)
    print(f"  GATE {gate_num}: {title}")
    print("!"*60)
    for item in review_items:
        print(f"  {item}")
    print(f"\n  Resume when ready:")
    print(f"    python3 pipeline/run_pipeline.py --resume {sprint_id} --gate {gate_num}")
    print(f"\n  Pipeline paused at Gate {gate_num}.")
    print("!"*60 + "\n")


def _print_resume(sprint_id, gate_num, message):
    """Print a standardized resume header."""
    print("\n" + "#"*60)
    print(f"  RESUMING — Sprint {sprint_id}")
    print(f"  Gate {gate_num}: {message}")
    print("#"*60)


def _load_json(path):
    """Load a JSON file."""
    with open(path) as f:
        return json.load(f)


def _load_csv(path):
    """Load a CSV file as list of dicts."""
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _scan_images(images_dir):
    """Scan a directory for PNGs and return asset_id -> path map."""
    results = {}
    if images_dir.exists():
        for img_file in images_dir.glob("*.png"):
            results[img_file.stem] = str(img_file)
    return results


def _apply_copy_overrides(run_dir, copy_outputs):
    """Re-read copy_review.csv and apply human YES/NO overrides."""
    review_path = run_dir / "copy_review.csv"
    if not review_path.exists():
        return

    human_selections = {}
    with open(review_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            tag = row.get("concept_tag", "")
            selected = row.get("selected", "").strip().upper() == "YES"
            human_selections[tag] = selected

    changed = 0
    for concept in copy_outputs.get("concepts", []):
        tag = concept.get("concept_tag", "")
        if tag in human_selections:
            old_selected = concept.get("selected", False)
            new_selected = human_selections[tag]
            if old_selected != new_selected:
                concept["selected"] = new_selected
                changed += 1

    if changed:
        print(f"  Applied {changed} human override(s) from copy_review.csv")
        with open(run_dir / "copy_outputs.json", "w") as f:
            json.dump(copy_outputs, f, indent=2)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upwork Creative Pipeline - Local Runner")
    parser.add_argument("--csv", type=str, help="Path to order CSV from the form")
    parser.add_argument("--json", type=str, help="Path to order JSON payload")
    parser.add_argument("--test", action="store_true", help="Run with built-in test order")
    parser.add_argument("--resume", type=str, metavar="SPRINT_ID", help="Resume a paused pipeline run")
    parser.add_argument("--gate", type=int, default=2, help="Which gate to resume from (2=order confirmed, 3=copy approved, 4=prompts approved, 5=images approved, 6=final QA)")

    args = parser.parse_args()

    # Handle resume
    if args.resume:
        sprint_id = args.resume
        gate = args.gate

        gate_handlers = {
            2: resume_gate_2,
            3: resume_gate_3,
            4: resume_gate_4,
            5: resume_gate_5,
            6: resume_gate_6,
        }

        handler = gate_handlers.get(gate)
        if not handler:
            print(f"Unknown gate: {gate}. Valid gates: 1-6")
            sys.exit(1)

        handler(sprint_id)
        sys.exit(0)

    # Handle new runs
    if args.csv:
        payload = parse_csv_order(args.csv)
        if not payload:
            print("Failed to parse CSV")
            sys.exit(1)
    elif args.json:
        with open(args.json) as f:
            payload = json.load(f)
    elif args.test:
        payload = get_test_order()
    else:
        print("Usage:")
        print("  Start new run:")
        print("    python3 pipeline/run_pipeline.py --csv path/to/order.csv")
        print("    python3 pipeline/run_pipeline.py --json path/to/order.json")
        print("    python3 pipeline/run_pipeline.py --test")
        print("")
        print("  Resume after approval:")
        print("    python3 pipeline/run_pipeline.py --resume SPRINT_ID --gate 2  (order + refs confirmed)")
        print("    python3 pipeline/run_pipeline.py --resume SPRINT_ID --gate 3  (copy approved)")
        print("    python3 pipeline/run_pipeline.py --resume SPRINT_ID --gate 4  (prompts approved)")
        print("    python3 pipeline/run_pipeline.py --resume SPRINT_ID --gate 5  (images approved)")
        print("    python3 pipeline/run_pipeline.py --resume SPRINT_ID --gate 6  (final QA approved)")
        sys.exit(1)

    run_full_pipeline(payload)
