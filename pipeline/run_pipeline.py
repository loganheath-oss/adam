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

# Copy-generation model. Centralized + env-overridable so it can be swapped without a
# code change (set ADAM_COPY_MODEL on the service). Default is Sonnet 5 (Logan 2026-07-27).
_COPY_MODEL = os.environ.get("ADAM_COPY_MODEL", "claude-sonnet-5")
# Sonnet 5 auto-thinks, but testing showed thinking adds ~3x cost with NO copy-quality
# gain once the craft prompt is in place (Logan 2026-07-27), so default it OFF. Set
# ADAM_COPY_THINKING=on to re-enable. Only affects models that support thinking.
_COPY_THINKING = os.environ.get("ADAM_COPY_THINKING", "off")


def _thinking_params():
    return {} if _COPY_THINKING != "off" else {"thinking": {"type": "disabled"}}


# Fields whose values are LISTS of strings (bullets/labels); everything else is a string.
_LIST_FIELDS = {"us_bullets", "them_bullets", "left_bullets", "right_bullets",
                "single_bullets", "search_results", "pie_labels", "labels", "tags"}
# Base feed fields every concept carries.
_BASE_FIELDS = ("concept_tag", "creative_headline", "headline", "headline_short",
                "body_short", "body_long", "description", "cta")


def _concept_schema(style, is_both, qty):
    """Per-style JSON schema for structured copy output (output_config.format).

    The API guarantees the response matches this shape, which makes the whole class
    of shape bugs impossible at the source: nested {feed:{…}} audiences, missing
    headline fields, truncated JSON, empty-string-vs-missing drift, thinking-block
    parses. additionalProperties=false everywhere is the teeth."""
    def _prop(f):
        if f in _LIST_FIELDS:
            return {"type": "array", "items": {"type": "string"}}
        return {"type": "string"}

    props = {f: _prop(f) for f in _BASE_FIELDS}
    required = list(_BASE_FIELDS)
    if _style_uses_subhead(style):
        props["creative_subhead"] = {"type": "string"}
    # Style extras from the guide entry (poll_question, left_bullets, …).
    _k, entry = _guide_entry_for_style(style)
    for f in ((entry or {}).get("char_limits") or {}):
        if f not in props and f not in ("creative_headline", "creative_subhead", "cta"):
            props[f] = _prop(f)
    if is_both:
        aud_fields = ["creative_headline", "headline", "headline_short",
                      "body_short", "body_long", "description"]
        aud_props = {f: {"type": "string"} for f in aud_fields}
        if _style_uses_subhead(style):
            aud_props["creative_subhead"] = {"type": "string"}
        aud = {"type": "object", "properties": aud_props,
               "required": aud_fields, "additionalProperties": False}
        props["targeting_copy"] = {"type": "object",
                                   "properties": {"Prospecting": aud, "Retargeting": aud},
                                   "required": ["Prospecting", "Retargeting"],
                                   "additionalProperties": False}
        required.append("targeting_copy")
    concept = {"type": "object", "properties": props,
               "required": required, "additionalProperties": False}
    # NOTE: the API rejects minItems/maxItems > 1 on arrays — the concept COUNT stays
    # prompt-enforced (as it always was); the schema enforces the SHAPE of each concept.
    return {"type": "object",
            "properties": {"concepts": {"type": "array", "items": concept}},
            "required": ["concepts"], "additionalProperties": False}


# Craft directive — placed FIRST in the copy prompt (before the 20k-char compliance wall)
# so the model reads "write something compelling" before it reads "obey these 40 rules."
# Fixes flat, literal, brief-echoing headlines like "Hire in 48h" (Logan 2026-07-27).
_CRAFT_BAR = """===== THE CRAFT BAR (READ FIRST — this is what separates a shippable ad from filler) =====
You are a senior paid-social copywriter, not a form-filler. The headline and the on-image line
ARE the ad. If they are flat, the ad fails no matter how correct everything else is. Correct,
on-brief, and within the caps is the FLOOR, not the goal.

RULE 1 — Interpret the brief, do not restate it. The brief is the idea; your job is to make
someone STOP scrolling and feel something. A headline that just repeats what the brief said
(brief: "hire AI talent in 48 hours" -> headline: "Hire in 48h") is a failure. Say the thing
the brief implies but does not say.

RULE 2 — Every headline must earn attention with a HOOK: tension, a sharp specific, curiosity,
a reframe, social proof, or a vivid outcome. Never a bare instruction or a category label.

RULE 3 — Distinct angles. Across the concepts you generate, no two headlines may lean on the
same idea. Rotate deliberately: pain, aspiration, curiosity, contrast, proof, specificity. If
two of your headlines could swap places and no one would notice, rewrite one.

RULE 4 — Write it like an ad, not a text message. No abbreviations in a headline ("48 hours",
never "48h"). No filler. Cut every word that is not pulling weight. Sentence case, but proper
nouns STAY capitalized — "Monday"/"Friday"/"Upwork", never "monday"/"friday".

RULE 5 — Ban the transactional formula. "Post a job, hire by Friday" / "Post today, hire
tomorrow" is the DEFAULT construction every lazy speed-themed ad reaches for — when a whole
campaign leads with "Post X, hire Y" it reads as one ad photocopied (real operator complaint,
2026-07-28). At most ONE concept in your set may use a "Post…/hire…" imperative construction;
the rest must open differently: a question, a sharp stat, a reframe, social proof, a
consequence, a customer's voice. Vary the SENTENCE SHAPE, not just the words.

FLAT — never write like this (literal, generic, interchangeable):
  "Hire in 48h" | "Hire AI-skilled talent fast" | "Hired in 48 hours" | "Find talent today" | "AI talent, fast"
SHARP — this is the bar (hook-driven, specific, each a different angle):
  "The specialist you need is already on Upwork"
  "Skip the three-month hiring slog"
  "Your competitor already hired theirs"
  "From job post to shipped by Friday"
  "Stop scrolling profiles. Start shipping work."
  "One specialist beats a stack of maybes"

All of this operates WITHIN the Legal blocklist below, which still wins over everything.
VOCAB TRAP — when writing "one expert beats many candidates" copy, do NOT reach for
"resume/resumes" (restricted term — it costs the concept its shipping slot every time).
Say "profiles", "proposals", "past work", or "maybes" instead. Same for "vetted"
(say "rated", "reviewed", "proven") and "salary" (say "cost", "budget", "overhead")."""


def _response_text(rj):
    """Extract the assistant's text from an Anthropic /v1/messages response, skipping
    any non-text blocks. Sonnet 5 (and other thinking models) prepend a 'thinking' block,
    so content[0] is NOT the text — reading content[0]['text'] blindly KeyErrors. Iterate
    and return the first 'text' block. Safe for older models that return only a text block."""
    for _b in (rj.get("content") or []):
        if _b.get("type") == "text":
            return _b.get("text", "")
    return ""


_DAY_RE = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", re.IGNORECASE)


# NOTE: "it" is deliberately absent — uppercasing the pronoun "it" everywhere is far
# worse than leaving the rare standalone "IT" (industry) lowercase.
_ACRONYM_RE = re.compile(r"\b(cfo|cmo|coo|ceo|cto|cio|chro|roi|seo|ppc|kpi|smb|ai|ml)\b",
                         re.IGNORECASE)


def _fix_proper_nouns(text):
    """Deterministic backstop: capitalize days of the week, 'Upwork', and common acronyms
    (CFO/CMO/ROI/AI…), which the model lowercases under the sentence-case rule (prompting
    only gets ~70% there; Adrie's guardrails: 'No ALL CAPS except acronyms like AI, ROI').
    Days and Upwork are unambiguous; months are skipped (May/March collide with words)."""
    if not isinstance(text, str) or not text:
        return text
    text = _DAY_RE.sub(lambda m: m.group(0).capitalize(), text)
    text = re.sub(r"\bupwork\b", "Upwork", text)
    text = _ACRONYM_RE.sub(lambda m: m.group(0).upper(), text)
    return text


_PN_TEXT_FIELDS = ("creative_headline", "creative_subhead", "headline", "headline_short",
                   "body_short", "body", "body_long", "description", "cta", "us_headline",
                   "them_headline", "left_headline", "right_headline", "single_headline",
                   "poll_question", "testimonial_quote", "chat_message", "chat_label",
                   "button_text", "profile_left", "profile_right", "pie_center")
_PN_LIST_FIELDS = ("left_bullets", "right_bullets", "single_bullets", "us_bullets",
                   "them_bullets", "search_results", "pie_labels")


def _fix_concept_proper_nouns(concept):
    """Apply _fix_proper_nouns across a concept's copy fields (incl. nested targeting_copy)."""
    for _f in _PN_TEXT_FIELDS:
        if isinstance(concept.get(_f), str):
            concept[_f] = _fix_proper_nouns(concept[_f])
    for _f in _PN_LIST_FIELDS:
        if isinstance(concept.get(_f), list):
            concept[_f] = [_fix_proper_nouns(x) if isinstance(x, str) else x for x in concept[_f]]
    _tc = concept.get("targeting_copy")
    if isinstance(_tc, dict):
        for _aud in _tc.values():
            if not isinstance(_aud, dict):
                continue
            for _k, _v in _aud.items():
                if isinstance(_v, str):
                    _aud[_k] = _fix_proper_nouns(_v)
                elif isinstance(_v, dict):
                    for _k2, _v2 in _v.items():
                        if isinstance(_v2, str):
                            _v[_k2] = _fix_proper_nouns(_v2)


# Near-duplicate headline detection for the diverse top-N selection (module-level so
# the regression suite can unit-test it directly).
_HL_STOP = {"your", "the", "a", "an", "is", "are", "was", "be", "being",
            "could", "can", "will", "by", "to", "of", "in", "on", "for",
            "with", "and", "or", "it", "its", "you", "we", "our", "at",
            "this", "that", "not", "no", "now", "get", "just"}


def _headline_tokens(text):
    return set(re.findall(r"[a-z0-9']+", str(text or "").lower())) - _HL_STOP


def _headlines_near_dup(a, b):
    """True when two headlines are effectively the same idea: content-word Jaccard
    >= 0.6 OR one's content words contained in the other's ("Hired by Friday" vs
    "Hired by Friday, not next quarter"). Tiny titles (<2 content words) never match."""
    ta, tb = _headline_tokens(a), _headline_tokens(b)
    if len(ta) < 2 or len(tb) < 2:
        return False
    return (len(ta & tb) / max(1, len(ta | tb))) >= 0.6 or ta <= tb or tb <= ta


def _enforce_conditional_caps(concepts, style):
    """Style Guide caps that depend on the CTA decision (Split Screen: with-CTA headline
    max 49 / without 65; Lifestyle: 80/100). The with/without split is only known after
    _apply_cta_mix runs, so this enforces AFTER it: pick the applicable cap per concept
    and smart-trim overflow. Deterministic backstop (flagged 2026-07-23, green-lit 7/28)."""
    _k, entry = _guide_entry_for_style(style)
    cc = (entry or {}).get("conditional_caps")
    if not isinstance(cc, dict):
        return
    field = cc.get("field", "creative_headline")
    for c in concepts:
        cap = cc.get("without_cta") if c.get("no_cta") else cc.get("with_cta")
        v = c.get(field)
        if isinstance(cap, int) and isinstance(v, str) and len(v) > cap:
            c[field] = _smart_trim(v, cap)
            print(f"    conditional-cap fit: {style} {field} "
                  f"{'no-CTA' if c.get('no_cta') else 'with-CTA'} {len(v)}>{cap} — trimmed")


def _flatten_audience(aud):
    """A P&R ('both') audience block from targeting_copy may put the Meta-feed fields
    (headline, body_short, …) FLAT, or nest them under a 'feed' object — the model is
    inconsistent, and when it nests, the flat body/headline fields come out EMPTY
    (Adrie's "empty body copy" bug, found 2026-07-27). Return a flat view: promote any
    nested 'feed' fields up, keeping existing flat fields. Robust to either structure."""
    if not isinstance(aud, dict):
        return {}
    flat = dict(aud)
    feed = aud.get("feed")
    if isinstance(feed, dict):
        for _k, _v in feed.items():
            if not flat.get(_k):
                flat[_k] = _v
    return flat
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
        # Raise (rather than return None) so the real reasons reach the user.
        # main.py's task runner writes str(exc) into pipeline_state.json, which
        # the Sprint tab + chat surface — instead of the opaque generic
        # "check order payload for validation errors" the user saw before.
        raise ValueError(
            "Order form couldn't be accepted:\n" + "\n".join(f"  • {e}" for e in errors)
        )

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

    # CROSS-STYLE diversity: each style's call can't see the others, so a whole batch can
    # converge on one construction ("Post today, hire Friday" x7 — Adrie, 2026-07-28).
    # Walk selected concepts across styles; when one near-dups an already-accepted headline
    # from ANOTHER style, swap it for that style's best non-dup, legal-clean alternate.
    _cs_all = copy_outputs.get("concepts", [])
    if _cs_all:
        _accepted = []   # (style, headline) accepted so far across the batch
        _swaps = 0
        _by_style_all = {}
        for c in _cs_all:
            _by_style_all.setdefault(c.get("visual_style"), []).append(c)
        for _style, _pool in _by_style_all.items():
            for c in [x for x in _pool if x.get("selected")]:
                _hl = c.get("creative_headline") or c.get("headline") or ""
                _clash = any(_headlines_near_dup(_hl, h) for st, h in _accepted if st != _style)
                if _clash:
                    _alt = next((a for a in _pool
                                 if not a.get("selected") and not a.get("legal_flags")
                                 and not any(_headlines_near_dup(
                                     a.get("creative_headline") or a.get("headline") or "", h)
                                     for _st2, h in _accepted)), None)
                    if _alt is not None:
                        c["selected"] = False
                        _alt["selected"] = True
                        _alt["review_notes"] = ("↔ swapped in for cross-style variety — prior pick "
                                                f"echoed another style's headline. " + str(_alt.get("review_notes", "")))
                        _apply_cta_mix(_pool, _style)
                        c = _alt
                        _hl = c.get("creative_headline") or c.get("headline") or ""
                        _swaps += 1
                        print(f"    cross-style variety: {_style} pick swapped ({_hl[:40]!r})")
                _accepted.append((_style, _hl))
        if _swaps:
            print(f"  Cross-style variety: {_swaps} pick(s) swapped for batch-level diversity")

    # Per-run copy-quality telemetry (regressions surface without anyone running tests):
    # legal-flag rate, selection counts, bullet/paragraph split, near-dup pair rate.
    _cs = copy_outputs.get("concepts", [])
    if _cs:
        _sel = [c for c in _cs if c.get("selected")]
        _bl = [c.get("body_long") for c in _cs if c.get("body_long")]
        _nb = sum(1 for t in _bl if re.search(r"\n\s*([^\w\s]|[-•*])", str(t)))
        _dups = 0
        _by_style = {}
        for c in _sel:
            _by_style.setdefault(c.get("visual_style"), []).append(
                c.get("creative_headline") or c.get("headline") or "")
        for _hls in _by_style.values():
            _dups += sum(1 for i in range(len(_hls)) for j in range(i + 1, len(_hls))
                         if _headlines_near_dup(_hls[i], _hls[j]))
        copy_outputs["quality"] = {
            "concepts": len(_cs), "selected": len(_sel),
            "legal_flagged": sum(1 for c in _cs if c.get("legal_flags")),
            "legal_flagged_selected": sum(1 for c in _sel if c.get("legal_flags")),
            "bulleted_long": _nb, "paragraph_long": len(_bl) - _nb,
            "near_dup_selected_pairs": _dups,
            "cross_style_dup_pairs": sum(
                1 for i in range(len(_sel)) for j in range(i + 1, len(_sel))
                if _sel[i].get("visual_style") != _sel[j].get("visual_style")
                and _headlines_near_dup(
                    _sel[i].get("creative_headline") or _sel[i].get("headline") or "",
                    _sel[j].get("creative_headline") or _sel[j].get("headline") or "")),
        }
        print(f"  Quality: {copy_outputs['quality']}")

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


_TEMPLATE_REGISTRY = None
# Order-form style names that differ from the Figma Adtype key.
_STYLE_REGISTRY_ALIASES = {
    "lifestyle-photo": "Lifestyle-Photo-Full-Bleed",
    "tweet-post-mockup": "Mockup",
    "graphic-with-text": "Illustration",   # shares Illustration's caps (Headline 38 / CTA 16)
}


def _load_template_registry():
    """Elise's Figma-derived template rules (configs/figma_template_registry.json).
    Source of truth for per-style on-creative character limits + template naming.
    Best-effort: absent/malformed registry just means no template limits applied."""
    global _TEMPLATE_REGISTRY
    if _TEMPLATE_REGISTRY is None:
        try:
            p = BASE_DIR / "configs" / "figma_template_registry.json"
            _TEMPLATE_REGISTRY = json.loads(p.read_text()).get("adtypes", {})
        except Exception:
            _TEMPLATE_REGISTRY = {}
    return _TEMPLATE_REGISTRY


def _norm_style(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def _limits_for_style(style):
    """Per-style on-creative char limits from the registry ({} if none/no match)."""
    reg = _load_template_registry()
    if not reg:
        return {}
    norm = _norm_style(style)
    for k, v in reg.items():
        if _norm_style(k) == norm:
            return v.get("limits", {}) or {}
    alias = _STYLE_REGISTRY_ALIASES.get(norm)
    if alias and alias in reg:
        return reg[alias].get("limits", {}) or {}
    for k, v in reg.items():
        kn = _norm_style(k)
        if kn.startswith(norm) or norm.startswith(kn):
            return v.get("limits", {}) or {}
    return {}


def _limits_raw_for_style(style):
    """Verbatim per-slot caps read from the Figma 'Rules' layer for this style
    ({label: max}, or {} if none). Same lookup order as _limits_for_style."""
    reg = _load_template_registry()
    if not reg:
        return {}
    norm = _norm_style(style)
    def raw(v):
        return v.get("limits_raw", {}) or {}
    for k, v in reg.items():
        if _norm_style(k) == norm:
            return raw(v)
    alias = _STYLE_REGISTRY_ALIASES.get(norm)
    if alias and alias in reg:
        return raw(reg[alias])
    for k, v in reg.items():
        kn = _norm_style(k)
        if kn.startswith(norm) or norm.startswith(kn):
            return raw(v)
    return {}


def _template_limit_block(style):
    """Prompt block listing this template's on-creative text slots and their HARD
    caps, read verbatim from the well-named Figma 'Rules' layer (source of truth,
    synced by scripts/harvest_figma_rules.py). Empty string if the style has none."""
    raw = _limits_raw_for_style(style)
    if not raw:
        return ""
    lines = []
    for label, n in raw.items():
        clean = " ".join(str(label).split())          # collapse newlines/dbl-spaces
        lines.append(f"- {clean}: MAX {n} characters")
    if not lines:
        return ""
    return (
        "\n===== TEMPLATE CHARACTER LIMITS (from Elise's Figma 'Rules' layer — HARD CAPS) =====\n"
        "Below are the EXACT text slots on THIS ad's template and their hard character\n"
        "caps. These OVERRIDE the generic field maxes below. Every piece of text that\n"
        "appears ON the image must fit its slot — count characters INCLUDING spaces and\n"
        "rewrite shorter if a concept would exceed a cap. Never overflow the template.\n"
        "Map the slots to your output fields: a 'Headline' slot is creative_headline; a\n"
        "'Subhead'/'Stat'/'Copy' slot is creative_subhead; a 'CTA'/'Button' slot is cta;\n"
        "any other named slot (Testimonial Copy, Chat Bubble, Column, Quadrant, Talent\n"
        "Tag, Credit, etc.) is the primary on-creative text for that slot — keep the\n"
        "creative_headline/creative_subhead you emit within the tightest applicable cap.\n"
        + "\n".join(lines) + "\n"
    )


# Adrie's bullet spec: emoji-led bullets, never plain glyphs. The model complies
# intermittently, so any plain bullet glyph left over gets an emoji deterministically.
# Dashes are deliberately excluded — "— Name, Title" attribution lines are legitimate.
_PLAIN_BULLET_RE = re.compile(r"(?m)^([ \t]*)[•▪‣·]\s+")

# When a plain bullet slips through, give it a CONTENT-APT, varied emoji — never a stack of
# flat ✅ or the same three every time (Logan: the copy must feel picture-rich, drawing from
# the whole library). We match the bullet's OWN words to a fitting emoji; if nothing matches
# (or it's already used in this list) we take the next unused one from a punchy rotation, so
# a list never repeats. The model is instructed to pick these itself — this is the safety net.
_FALLBACK_BULLET_EMOJI = ["🚀", "⚡", "💡", "🔥", "⭐", "📈", "💪", "✨", "🔑", "📊",
                          "🌱", "🏆", "💬", "🔒", "💻", "🙌", "🎯", "⏱️", "🎨", "🧠"]
# (emoji, keyword-substrings) — first match wins; ordered most- to least-specific.
_BULLET_EMOJI_KEYWORDS = [
    ("⏱️", ("week", "hour", "month", "deadline", "schedule", "wait", "delay", "slow", "timeline", "minute", "same week", "overnight", "days")),
    ("🚀", ("fast", "quick", "rapid", "instant", "today", "tomorrow", "hit the ground", "ready to start", "move fast", "launch", "ship", "momentum", "speed")),
    ("👩‍💻", ("hire", "talent", "specialist", "expert", "freelanc", "developer", "designer", "engineer", "professional", "candidate", "team")),
    ("📩", ("proposal", "apply", "bid", "shortlist", "reach out", "inbox")),
    ("🎯", ("right fit", "exact", "specific", "precise", "targeted", "perfect match", "niche", "the right")),
    ("📈", ("result", "grow", "scale", " win", "outcome", "impact", "success", "roi", "performance", "compound", "revenue")),
    ("⭐", ("quality", "top-tier", "top tier", "best", "rated", "review", "star", "proven", "trusted", "reputation", "portfolio")),
    ("🔒", ("secure", "protect", "payment", "safe", "escrow", "contract", "peace of mind", "guarantee")),
    ("💰", ("cost", "budget", "price", "save", "afford", "money", "spend", "dollar", "value", "overhead", "free")),
    ("💻", ("ai", "chatbot", "automat", "code", "develop", "integrat", "software", "app", "data", "workflow", "tool", "tech")),
    ("💡", ("idea", "test", "experiment", "learn", "insight", "discover", "strategy", "creative")),
    ("🌍", ("anywhere", "remote", "global", "worldwide", "time zone", "flexib")),
    ("💬", ("message", "chat", "talk", "communic", "conversation", "respond", "feedback", "gatekeeper")),
]


def _pick_bullet_emoji(line, used):
    low = line.lower()
    for emo, kws in _BULLET_EMOJI_KEYWORDS:
        if emo not in used and any(k in low for k in kws):
            return emo
    for emo in _FALLBACK_BULLET_EMOJI:
        if emo not in used:
            return emo
    return _FALLBACK_BULLET_EMOJI[0]


def _emojify_plain_bullets(text):
    """Replace each leftover plain bullet with a content-apt, non-repeating emoji so a list
    reads picture-rich and varied (never a stack of ✅). No plain bullets → unchanged."""
    if not text or not _PLAIN_BULLET_RE.search(text):
        return text
    used = set()
    def _repl(m):
        line = m.string[m.end():].split("\n", 1)[0]
        emo = _pick_bullet_emoji(line, used)
        used.add(emo)
        return f"{m.group(1)}{emo} "
    return _PLAIN_BULLET_RE.sub(_repl, text)


# ── AD TYPE STYLE GUIDE (structured: configs/ad_type_style_guide.json) ─────────
# Single source of truth for per-ad-type copy rules. We resolve exactly ONE entry
# per style and (a) render it into the copy prompt as prose, (b) enforce its
# char_limits deterministically. Previously the guide was a prose blob injected
# truncated (copy_style_rules[:5000]) — so entries ~#11+ (Chat Bubble, Tweet, ...)
# were silently cut off and never enforced. Now nothing is truncated, and the caps
# are checkable data, not just prompt prose. Edit the JSON, not this code.
_STYLE_GUIDE = None


def _load_style_guide():
    """Load configs/ad_type_style_guide.json once. {} if absent/malformed."""
    global _STYLE_GUIDE
    if _STYLE_GUIDE is None:
        try:
            p = BASE_DIR / "configs" / "ad_type_style_guide.json"
            _STYLE_GUIDE = json.loads(p.read_text())
        except Exception as e:
            print(f"[guide] load failed ({e}); style-guide enforcement disabled.")
            _STYLE_GUIDE = {}
    return _STYLE_GUIDE


def _guide_entry_for_style(style):
    """(key, entry_dict) for this style, or (None, None). Lookup order matches the
    registry: exact norm → alias → bidirectional prefix."""
    g = _load_style_guide()
    entries = g.get("entries", {})
    if not entries:
        return None, None
    norm = _norm_style(style)
    if norm in entries:
        return norm, entries[norm]
    alias = (g.get("aliases") or {}).get(norm)
    if alias and alias in entries:
        return alias, entries[alias]
    for k, v in entries.items():
        if k.startswith(norm) or norm.startswith(k):
            return k, v
    return None, None


def _render_guide_entry(entry):
    """Render a structured entry into the prose block the copy prompt reads."""
    lines = [f"Entry {entry.get('entry', '')} — {entry.get('name', '')}".strip()]
    if entry.get("layout"):
        lines.append(f"Layout: {entry['layout']}")
    if entry.get("density"):
        lines.append(f"Density: {entry['density']}")
    if entry.get("rules"):
        lines.append("Rules:")
        lines += [f"- {r}" for r in entry["rules"]]
    cl = entry.get("char_limits") or {}
    if cl:
        lines.append("Character limits (HARD — count spaces, rewrite shorter if over): "
                     + " · ".join(f"{k} max {v}" for k, v in cl.items()))
    if entry.get("punctuation"):
        lines.append(f"Punctuation: {entry['punctuation']}")
    if entry.get("tone"):
        lines.append(f"Tone: {entry['tone']}")
    if entry.get("cta"):
        lines.append(f"CTA: {entry['cta']}")
    return "\n".join(lines)


def _style_guide_block(style, guide_text=None):
    """(entry_prose, matched_name) for the prompt, or (None, None) if no match.
    guide_text is ignored (kept for call-site compatibility) — JSON is the source."""
    key, entry = _guide_entry_for_style(style)
    if not entry:
        return None, None
    return _render_guide_entry(entry), key


# ── CHAR-LIMIT ENFORCEMENT ────────────────────────────────────────────────────
# Deterministic backstop for the guide's char_limits (the prompt asks; a model is
# probabilistic, so we ALSO check every field). Mirrors the legal guardrail:
#   HARD overflow (on-image field over its must-fit cap) → length_flags → de-selected
#     in ranking, backfilled with a clean concept (never mangle copy by clipping).
#   SOFT overflow (editorial on-image-core or Meta-feed field) → length_warnings →
#     recorded + demoted, but still shippable so yield never craters.
_REG_SLOT_TO_FIELD = {"headline": "creative_headline",
                      "subhead": "creative_subhead", "cta": "cta"}


def _style_caps(style):
    """Resolve (hard, soft) per-field char caps for a style — {adam_field: max}."""
    g = _load_style_guide()
    multi = set((g.get("_meta", {}) or {}).get("multi_image_fields", []))
    feed = dict(g.get("field_caps_meta_feed", {}) or {})
    core_def = dict(g.get("onimage_core_defaults", {}) or {})
    _, entry = _guide_entry_for_style(style)
    cl = dict((entry or {}).get("char_limits", {}) or {})

    hard, soft = {}, {}
    # Figma template physical caps (registry limits: headline/subhead/cta) — hard.
    for slot, cap in _limits_for_style(style).items():
        f = _REG_SLOT_TO_FIELD.get(slot)
        if f and isinstance(cap, int):
            hard[f] = min(cap, hard.get(f, cap))
    # Guide caps: multi-image fields → hard (no template equivalent); core → soft.
    for f, cap in cl.items():
        if not isinstance(cap, int):
            continue
        if f in multi:
            hard[f] = min(cap, hard.get(f, cap))
        else:
            soft[f] = min(cap, soft.get(f, cap))
    for f, cap in feed.items():            # Meta-feed fields (universal) — soft.
        soft[f] = cap
    for f, cap in core_def.items():        # on-image core fallback if nothing tighter.
        if f not in hard:
            soft.setdefault(f, cap)
    return hard, soft


def _field_overflows(concept, field, cap):
    """Overflow markers ('field:len>cap') for a concept field vs cap. Handles str
    and list (bullets/labels/tags) fields; [] if within cap or absent."""
    v = concept.get(field)
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [f"{field}[{i}]:{len(str(x))}>{cap}"
                for i, x in enumerate(v) if len(str(x)) > cap]
    s = str(v)
    return [f"{field}:{len(s)}>{cap}"] if len(s) > cap else []


def _style_uses_subhead(style):
    """True if this style's guide entry declares a creative_subhead cap — i.e. the ad
    type actually uses an on-image subhead. Headline-only types (Graphic with Text,
    Split Screen, Device UI, …) declare no such cap, so a generated subhead is off-spec.
    Bespoke (no caps at all) is left alone."""
    _, entry = _guide_entry_for_style(style)
    cl = (entry or {}).get("char_limits") or {}
    return (not cl) or ("creative_subhead" in cl)


def _enforce_combined_caps(concept, style):
    """Some ad types cap the COMBINED on-image text, not just each field (Style Guide:
    Social Media columns combined ≤65; Sticky Note double-column columns combined ≤136).
    Per-field caps alone let the sum overrun the design's fixed space, so sum the fields and,
    if over, deterministically trim each proportional to its share — guaranteed ≤ the cap."""
    _, entry = _guide_entry_for_style(style)
    for cc in ((entry or {}).get("combined_caps") or []):
        fields = cc.get("fields") or []
        cap = cc.get("cap")
        if not fields or not isinstance(cap, int):
            continue
        def _flen(f):
            v = concept.get(f)
            return sum(len(str(x)) for x in v) if isinstance(v, list) else len(str(v or ""))
        total = sum(_flen(f) for f in fields)
        if total <= cap or total == 0:
            continue
        for f in fields:
            v = concept.get(f)
            share = _flen(f)
            if not share:
                continue
            budget = max(1, cap * share // total)
            if isinstance(v, list):
                per = max(1, budget // max(1, len(v)))
                concept[f] = [_smart_trim(str(x), per) for x in v]
            elif isinstance(v, str):
                concept[f] = _smart_trim(v, budget)
        print(f"    combined-cap fit: {style} {'+'.join(fields)} {total}>{cap} — trimmed to fit")


def _enforce_lengths(concept, style):
    """Set concept['length_flags'] (HARD) + ['length_warnings'] (SOFT). Returns the
    hard-flag list (empty = fits)."""
    hard, soft = _style_caps(style)
    hard_flags, soft_flags = [], []
    for f, cap in hard.items():
        hard_flags += _field_overflows(concept, f, cap)
    for f, cap in soft.items():
        soft_flags += _field_overflows(concept, f, cap)
    # "Both" concepts: also check each audience's feed copy under targeting_copy
    # against the Meta-feed caps (soft — feed overflow is recorded, not de-selected).
    tc = concept.get("targeting_copy")
    if isinstance(tc, dict):
        feed = (_load_style_guide().get("field_caps_meta_feed", {}) or {})
        for aud, obj in tc.items():
            if isinstance(obj, dict):
                for f, cap in feed.items():
                    soft_flags += [f"{aud}.{m}" for m in _field_overflows(obj, f, cap)]
    if hard_flags:
        concept["length_flags"] = hard_flags
    if soft_flags:
        concept["length_warnings"] = soft_flags
    return hard_flags


def _apply_cta_mix(reviewed, style):
    """Deterministically apply the matched entry's CTA distribution to the SELECTED
    concepts (Style Guide: e.g. 'one variant must include a CTA; remaining without').
    Every concept is generated WITH its best CTA; here we blank it on the variants
    that shouldn't display one and set no_cta=True so the manifest/plugin pick the
    no-CTA template variant. Modes (entry.cta_mix): all/default = keep every CTA;
    none = blank all; one/two = keep on the top-1/top-2 ranked selected concepts."""
    _, entry = _guide_entry_for_style(style)
    mix = (entry or {}).get("cta_mix", "default")
    if mix in ("all", "default"):
        return
    keep = {"none": 0, "one": 1, "two": 2}.get(mix, 1)
    subhead_rule = bool((entry or {}).get("subhead_only_without_cta"))
    selected = sorted([c for c in reviewed if c.get("selected")],
                      key=lambda c: c.get("rank", 99))
    for pos, c in enumerate(selected):
        if pos < keep:
            # This variant carries the CTA. Entry-3-style rule: the subhead only
            # appears on no-CTA versions, so drop it from the CTA-bearing one.
            if subhead_rule and c.get("creative_subhead"):
                c["creative_subhead"] = ""
            continue
        c["cta"] = ""
        c["no_cta"] = True
    if keep < len(selected):
        print(f"    CTA mix '{mix}' applied to {style}: "
              f"{min(keep, len(selected))} with CTA, {len(selected) - keep} without")


def _salvage_json_array(text):
    """Recover as many COMPLETE objects as possible from a truncated JSON array
    (e.g. the model's output hit the token cap mid-array). Scans for balanced
    top-level {...} blocks and json.loads each. Returns a list (possibly empty)."""
    objs, depth, start, in_str, esc = [], 0, None, False, False
    for idx, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        objs.append(json.loads(text[start:idx + 1]))
                    except Exception:
                        pass
                    start = None
    return objs



def _load_approved_quotes():
    """Adrie's live quote library (approved_quotes.md — volume-backed, edited in the
    app's Quotes page). Lines shaped:  - "Quote text." — First L., Title, Company
    Returns [(quote, attribution)]. Empty list if the file is absent/template-only."""
    path = Path(os.environ.get("QUOTES_PATH", str(RUNS_DIR.parent / "approved_quotes.md")))
    try:
        text = path.read_text()
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        m = re.match(r'\s*[-*]\s*["\u201c](.+?)["\u201d]\s*[\u2014\u2013-]{1,2}\s*(.+?)\s*$', line)
        if not m:
            continue
        q, a = m.group(1).strip(), m.group(2).strip()
        if len(q) < 15 or q.lower().startswith("quote text exactly"):
            continue  # too short or the template's example line
        out.append((q, a))
    return out


_QUOTE_STOP = {"the", "and", "to", "a", "of", "in", "on", "for", "with", "that", "is",
               "it", "i", "we", "our", "you", "your", "my", "are", "was", "have", "has",
               "at", "as", "so", "but", "not", "this", "they", "their", "them"}


def _quote_from_library(quote, approved_texts):
    """True if `quote` is one of the approved/library quotes. The Style Guide lets the model
    SHORTEN a real quote, so an exact-substring check false-flagged shortened real quotes as
    fictional (Adrie 2026-07-23). Match on substring OR high content-word overlap: ≥4 shared
    content words AND ≥75% of the quote's content words present in a library entry."""
    def _norm(s):
        return " ".join(str(s or "").split()).lower().strip(" .\"“”'")
    def _cw(s):
        return {w for w in _norm(s).split() if len(w) >= 3 and w not in _QUOTE_STOP}
    qn = _norm(quote)
    if not qn:
        return False
    q_cw = _cw(quote)
    for bq in approved_texts:
        bn = _norm(bq)
        if not bn:
            continue
        if qn in bn or bn in qn:
            return True
        if q_cw and len(q_cw & _cw(bq)) >= max(4, int(0.75 * len(q_cw))):
            return True
    return False


# A clean-sentence cut is used when it retains at least this share of the cap; below
# that we'd be throwing away too much of the field, so we word-cut and mark it with an
# ellipsis instead (see _smart_trim).
_TRIM_KEEP_MIN = 0.5


def _smart_trim(text, cap):
    """Last-resort shortening to <= cap chars that NEVER leaves a dangling half-sentence
    (Adrie's rule: a feed body must not end on a raw mid-sentence fragment). Order of
    preference:
      1. End on a COMPLETE sentence or bullet/line that keeps >= _TRIM_KEEP_MIN of the
         cap — a clean, terminal stop (no ellipsis; it's a whole thought).
      2. Otherwise cut at a word boundary and append an ellipsis (…), so the break reads
         as an intentional "more follows", not an accidental truncation mid-word/-clause.
    The earlier version fell straight to a bare word cut whenever the last sentence ended
    before the halfway mark — which is exactly the mid-sentence stub Adrie flagged."""
    text = str(text or "").rstrip()
    if len(text) <= cap:
        return text
    cut = text[:cap]

    # Latest sentence terminator (. ! ?), incl. one closing quote/paren, or a bullet /
    # line break within the allowed span.
    best = -1
    for m in re.finditer(r'[.!?]["”’)]*(?=\s|$)|\n', cut):
        best = max(best, m.end())
    if best >= max(1, int(cap * _TRIM_KEEP_MIN)):
        trimmed = cut[:best].rstrip()
        if trimmed.endswith(":"):
            # A "…who:" intro whose list got trimmed off — mark it as continued
            # rather than leaving a bare colon dangling.
            trimmed = trimmed[:-1].rstrip() + "…"
        if trimmed:
            return trimmed

    # No usable sentence boundary → word-boundary cut, marked as truncated so it never
    # looks like a broken sentence. Reserve one char for the ellipsis and don't end on a
    # dangling connector/punctuation.
    room = cut[: max(1, cap - 1)]
    idx = room.rfind(" ")
    base = (room[:idx] if idx > 0 else room).rstrip()
    base = base.rstrip(",;:—–-").rstrip()
    return (base + "…") if base else cut[:cap]


def _fit_feed_fields(concepts, style, api_key, sprint_id=None):
    """Meta feed fields (headline/body/description + per-audience targeting_copy)
    must FIT their caps — Meta hard-truncates overflow mid-sentence. The model
    chronically overshoots body_long (found 2026-07-16: 334-501 chars vs 300), so:
    one compact rewrite call shortens every overlong field properly (drop whole
    bullets/sentences, keep tone + format); anything still over falls back to a
    sentence-boundary trim. Deterministic result: feed fields <= caps."""
    import httpx

    caps = dict(_load_style_guide().get("field_caps_meta_feed", {}) or {})
    # SELF-HEAL (Adrie's "flag but don't fix"): also rewrite the HARD on-image fields
    # (creative_headline/subhead, multi-image fields) to fit. They break the design when
    # they overflow, yet were previously only length-flagged — now the same rewrite-to-fit
    # (drop/shorten, sentence-boundary trim only as last resort) repairs them to spec.
    _hard, _ = _style_caps(style)
    for _f, _c in _hard.items():
        caps[_f] = min(caps.get(_f, _c), _c)
    if not caps:
        return

    jobs = []  # {"id", "ci", "path", "cap", "text"}
    def _check(ci, obj, path_prefix):
        for f, cap in caps.items():
            v = obj.get(f)
            if isinstance(v, str) and len(v) > cap:
                jobs.append({"id": len(jobs), "ci": ci, "path": path_prefix + (f,),
                             "cap": cap, "text": v})
    for ci, c in enumerate(concepts):
        _check(ci, c, ())
        tc = c.get("targeting_copy")
        if isinstance(tc, dict):
            for aud, obj in tc.items():
                if isinstance(obj, dict):
                    _check(ci, obj, ("targeting_copy", aud))
    if not jobs:
        return

    def _apply(ci, path, value):
        tgt = concepts[ci]
        for p in path[:-1]:
            tgt = tgt.get(p, {})
        if isinstance(tgt, dict):
            tgt[path[-1]] = value

    rewritten = {}
    payload = [{"id": j["id"], "max_chars": j["cap"], "text": j["text"]} for j in jobs]
    prompt = (
        "You wrote Meta ad copy for Upwork; some fields exceed their platform caps and "
        "must be SHORTENED to fit. For each item, rewrite the text to AT MOST max_chars "
        "characters (count spaces). Preserve the meaning, Upwork's clear/supportive tone, "
        "and the formatting convention. If it uses emoji-led bullets, KEEP each surviving "
        "bullet's exact leading emoji (never swap it for a plain •/-/generic ✅) — drop whole "
        "bullets rather than squeezing; if prose, drop whole sentences. Never "
        "end mid-sentence, never add new claims or banned terms (guarantee, vet, staffing, "
        "employee).\n\nITEMS:\n" + json.dumps(payload, ensure_ascii=False)
        + "\n\nReturn ONLY a JSON array: [{\"id\": <int>, \"text\": \"<shortened>\"}]."
    )
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": _COPY_MODEL, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}], **_thinking_params()},
            timeout=90,
        )
        if resp.status_code == 200:
            _rj = resp.json()
            _add_token_usage(sprint_id, _COPY_MODEL,
                             _rj.get("usage", {}).get("input_tokens"),
                             _rj.get("usage", {}).get("output_tokens"))
            text = _response_text(_rj).strip()
            if "```" in text:
                text = text.split("```json")[-1].split("```")[0] if "```json" in text                     else text.split("```")[1]
            try:
                out = json.loads(text.strip())
            except json.JSONDecodeError:
                out = _salvage_json_array(text)
            for item in out if isinstance(out, list) else []:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    rewritten[item.get("id")] = item["text"]
    except Exception as e:
        print(f"    feed-fit rewrite call failed ({str(e)[:60]}); trimming instead")

    n_rewrite = n_trim = 0
    for j in jobs:
        new = rewritten.get(j["id"], j["text"])
        if len(new) > j["cap"]:
            new = _smart_trim(new, j["cap"])
            n_trim += 1
        elif j["id"] in rewritten:
            n_rewrite += 1
        _apply(j["ci"], j["path"], new)

    # Recompute guardrails on the fitted copy.
    touched = {j["ci"] for j in jobs}
    for ci in touched:
        c = concepts[ci]
        c.pop("length_flags", None)
        c.pop("length_warnings", None)
        _enforce_lengths(c, style)
        flags = _scan_banned_terms(c)
        if flags:
            c["legal_flags"] = flags
        else:
            c.pop("legal_flags", None)
    print(f"    feed-fit {style}: {len(jobs)} overlong field(s) -> "
          f"{n_rewrite} rewritten, {n_trim} trimmed")


# ── LEGAL BANNED-TERMS GUARDRAIL ──────────────────────────────────────────────
# Deterministic backstop for legal compliance. The prompt now surfaces Upwork
# Legal's full "Terms to Avoid" list (previously truncated off the prompt), but a
# model is probabilistic — so we ALSO scan every generated field. Only unambiguous,
# low-false-positive terms live here; borderline/context-dependent ones stay
# prompt-only to avoid mangling good copy. Flagged concepts are de-selected in the
# ranking pass so clean copy is what ships.
_LEGAL_BANNED = [
    r"vet(?:ted|ting|s)?", r"pre-?screen(?:ed|ing|s)?",
    r"screen(?:ed|ing)?\s+(?:talent|freelancers|candidates|pros)",
    r"background\s+check", r"employ(?:ee|ees|er|ers|ment)?", r"staffing", r"payroll",
    r"guarantee(?:d|s)?", r"salary", r"salaries", r"wages", r"paycheck",
    r"resum[eé]s?", r"\bCVs?\b",
    r"upwork'?s\s+(?:freelancers|talent|pros|professionals)", r"our\s+freelancers",
]
_LEGAL_BANNED_RE = [re.compile(p, re.IGNORECASE) for p in _LEGAL_BANNED]
_LEGAL_SCAN_FIELDS = ["text_on_visual", "creative_headline", "creative_subhead",
                      "headline", "headline_long", "headline_short",
                      "body_short", "body_long", "description", "cta"]


def _scan_banned_terms(concept):
    """Return banned terms found in a concept's copy fields (empty list = clean)."""
    hits = []
    for f in _LEGAL_SCAN_FIELDS:
        val = concept.get(f)
        if not val:
            continue
        for rx in _LEGAL_BANNED_RE:
            m = rx.search(str(val))
            if m:
                hits.append(f"{f}:'{m.group(0)}'")
    return hits


# Adrie's copy rule (refs/meta_copy_instructions.txt): headlines + CTAs are SENTENCE
# CASE — capitalize the first word and proper nouns only, keep acronyms (AI, ROI),
# no trailing period unless the line is two distinct sentences. The model still
# emits title case despite the prompt, so we enforce it deterministically.
_CASE_MAP = {
    "ai": "AI", "roi": "ROI", "seo": "SEO", "ml": "ML", "ui": "UI", "ux": "UX",
    "api": "API", "crm": "CRM", "ceo": "CEO", "cto": "CTO", "b2b": "B2B",
    "saas": "SaaS", "smb": "SMB", "upwork": "Upwork",
}


def _to_sentence_case(text):
    """Convert a headline/CTA to Adrie's sentence-case rules. Lowercases everything
    except sentence starts, the pronoun 'I', and known acronyms/brand names; strips a
    lone trailing period (keeps periods when the line is genuinely two sentences)."""
    if not text or not isinstance(text, str):
        return text

    def fix_word(m):
        low = m.group(0).lower()
        return _CASE_MAP.get(low, low)

    s = re.sub(r"[A-Za-z][A-Za-z']*", fix_word, text)          # baseline lowercase (acronyms kept)
    s = re.sub(r"(^|[.?!]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s)  # cap sentence starts
    s = re.sub(r"\bi\b", "I", s)                                # pronoun I
    s = re.sub(r"\bi'", "I'", s)                                # I'll / I'm / I've
    s = s.strip()
    if s.endswith(".") and s.count(".") == 1:                   # lone trailing period -> drop
        s = s[:-1].rstrip()
    return s


# Copy fields that appear ON the creative or as the headline/CTA — these follow the
# sentence-case rule. NOT applied to names/titles (testimonial_author, profile_*),
# which are proper nouns and keep their own casing.
_SENTENCE_CASE_FIELDS = ("creative_headline", "creative_subhead", "headline",
                         "headline_short", "cta")


# Total copy concepts generated per style (then reviewed down to top 3). Generated in
# small sub-batches (COPY_BATCH_SIZE) rather than one big call: a single call for all 6
# hit the max_tokens output ceiling on rich Prospecting+Retargeting concepts, truncating
# the JSON so later concepts came back scrawny or empty — the "fatigue" Adrie saw
# (2026-07-23). Small batches each get the full output budget → no starvation.
_CONCEPTS_PER_STYLE = 6
try:
    _COPY_BATCH_SIZE = max(1, int(os.environ.get("COPY_BATCH_SIZE", "2") or "2"))
except ValueError:
    _COPY_BATCH_SIZE = 2

# Distinct creative angles, one seeded per sub-batch so concepts diverge instead of
# repeating ("3 ads in a row saying faster than your competitors" — Adrie). Rotated by seq.
_COPY_ANGLES = [
    "Lead with the concrete OUTCOME the client gets.",
    "Lead with SPEED — time from posting to a hire or a result.",
    "Lead with VALUE — cost efficiency, budget, or avoiding a bad hire.",
    "Lead with PROOF — quality, ratings, expertise, or trust signals.",
    "Lead with a SPECIFIC use-case, role, or niche.",
    "Contrast the PAIN of the old way against how Upwork works.",
]


def _generate_copy_for_style(i, batch, style, order, context, api_key, sprint_id=None,
                             count=None, angle=None, seq=0):
    """Generate a small batch of copy concepts for one visual style (one Claude call).

    `count` concepts per call (default _CONCEPTS_PER_STYLE); `angle` seeds a distinct
    creative direction; `seq` disambiguates concept_ids across a style's sub-batches.
    Styles/sub-batches run concurrently — each call is independent and ~120s I/O-bound."""
    import httpx

    concepts = []
    qty = count or _CONCEPTS_PER_STYLE
    _angle_line = f"\nCREATIVE ANGLE FOR THIS SET (make these concepts distinct): {angle}\n" if angle else ""

    # LONG-BODY FORMAT — deterministic 50/50 bullet-vs-paragraph across a style's concepts
    # (Logan 2026-07-24: the model defaulted to 100% bulleted). Assign each concept a format
    # by GLOBAL index parity (seq*batch_size + position), so even indices → bulleted, odd →
    # paragraph. Across the style's full set that lands ~half bulleted / half flowing prose;
    # the human then picks from a balanced pool. Feed-fit trim already preserves each format.
    _fmt_lines = []
    for _j in range(qty):
        _gidx = seq * _COPY_BATCH_SIZE + _j
        if _gidx % 2 == 0:
            _fmt_lines.append(f"  Concept {_j+1}: body_long / Primary_Text_Long = EMOJI-BULLETED list "
                              "(3-4 short bullets, each led by a DISTINCT relevant emoji — vary them, not all the same).")
        else:
            _fmt_lines.append(f"  Concept {_j+1}: body_long / Primary_Text_Long = FLOWING PARAGRAPH prose "
                              "(2-3 sentences, NO bullets, NO emoji-led lines).")
    _body_format_line = (
        "\nLONG-BODY FORMAT — ASSIGNED per concept, follow EXACTLY. This bullet-vs-paragraph split "
        "is REQUIRED (do NOT make them all the same format):\n" + "\n".join(_fmt_lines) + "\n"
    )

    # Build rich prompt with all reference context
    brand_voice = context.get("brand_voice", "Professional, clear, human")
    writing_style = context.get("writing_style", "")
    compliance = context.get("compliance", "")
    playbook = context.get("copy_playbook", "")
    claims = context.get("approved_claims", "")
    copy_bank = context.get("smb_copy_bank", "")
    copy_style_rules = context.get("copy_style_rules", "")

    # Pick examples + rules based on targeting. "Prospecting and Retargeting" is
    # BOTH: load both example sets and (below) ask for both feed-copy versions per ad.
    # Per-concept audience (from the batch form) wins over the order-level dropdown.
    # The per-concept row is only shown when the order is Prospecting AND Retargeting,
    # and it defaults to "Both" — so honor it only for P&R orders (otherwise the stale
    # "Both" default would wrongly force both-audience on a single-audience order).
    # Fix 2026-07-21 (Adrie's segmentation bug): batch orders sent audience="Both",
    # which the old check ("prospecting" AND "retargeting" in the string) never matched,
    # so every batch concept silently fell to the single-audience path → one copy set.
    _order_t = order.get("targeting", "Prospecting") or "Prospecting"
    _order_both = ("prospecting" in _order_t.lower() and "retargeting" in _order_t.lower())
    _batch_aud = (batch.get("audience") or "").strip()
    if _order_both and _batch_aud:
        targeting_type = "Prospecting and Retargeting" if _batch_aud.lower() == "both" else _batch_aud
    else:
        targeting_type = _order_t
    _tl = targeting_type.lower()
    _is_both = (_tl == "both") or ("prospecting" in _tl and "retargeting" in _tl)
    _prosp_ex = context.get("prospecting_examples", "")
    _retarget_ex = context.get("retargeting_examples", "")
    if _is_both:
        examples = (f"--- PROSPECTING EXAMPLES ---\n{_prosp_ex[:1900]}\n\n"
                    f"--- RETARGETING EXAMPLES ---\n{_retarget_ex[:1900]}")
        targeting_rules = (
            "This order is BOTH Prospecting AND Retargeting. Provide the feed copy TWICE per\n"
            "concept — one version per audience (see targeting_copy below). The two must be\n"
            "genuinely different in angle, not reworded:\n"
            "- PROSPECTING = a COLD audience seeing Upwork for the first time. Build awareness,\n"
            "  introduce the value, lead with the problem/outcome. No assumed familiarity.\n"
            "- RETARGETING = a WARM audience that already knows Upwork. Keep it SUBTLE (Adrie,\n"
            "  2026-07-15): just a light hint of coming back, revisiting, or getting started —\n"
            "  NEVER 'we know you've been here' / 'we saw you looking' creeping language.\n"
            "  A gentle nudge toward the next step is the whole move. Acknowledge familiarity\n"
            "  (e.g. \"still hiring for that role?\", \"ready to post that job?\") and drive the conversion."
        )
    elif "retargeting" in _tl:
        examples = _retarget_ex or _prosp_ex
        targeting_rules = (
            "This is a RETARGETING order — a WARM audience that already knows Upwork.\n"
            "Keep it SUBTLE (Adrie, 2026-07-15): a light hint of coming back, revisiting, or\n"
            "getting started (\"ready to post that job?\", \"pick up where you left off\") — the\n"
            "platform handles who sees it, so NEVER use 'we know you've been here' /\n"
            "'we saw you looking' creeping language. Gentle nudge toward the next step;\n"
            "do NOT re-introduce Upwork from scratch."
        )
    else:
        examples = _prosp_ex or _retarget_ex
        targeting_rules = (
            "This is a PROSPECTING order — a COLD audience seeing Upwork for the first time.\n"
            "Build awareness, introduce the value, and lead with the problem/outcome.\n"
            "Do NOT assume any prior familiarity with Upwork."
        )

    # Feed-copy field spec + JSON key list branch on single-vs-both targeting.
    if _is_both:
        ad_platform_block = (
            "This order is BOTH audiences, and EACH AUDIENCE GETS ITS OWN CREATIVE. The visual\n"
            "STYLE is the same for both, but the on-image copy (Text_On_Visual) AND the feed copy\n"
            "must be UNIQUE per audience — provide EVERYTHING twice under a \"targeting_copy\" object.\n"
            "Do NOT give both audiences identical on-image copy.\n"
            "- targeting_copy: an object with EXACTLY two keys, \"Prospecting\" and \"Retargeting\".\n"
            "  Each maps to an object with BOTH the on-image and the feed copy for that audience:\n"
            "    ON-IMAGE (Text_On_Visual): creative_headline (follow the matched Style Guide caps),\n"
            "      creative_subhead (ONLY if the Style Guide entry allows a subhead — else omit),\n"
            "    FEED (around the image, never printed on it): headline (max 50), headline_short\n"
            "      (max 30), body_short (max 125), body_long (max 300 — Primary Text; keep the\n"
            "      ~half-bulleted rule), description (max 25).\n"
            "  Apply the Prospecting (cold) vs Retargeting (warm) rules above to BOTH the on-image\n"
            "  and the feed copy — the two audiences must read distinctly.\n"
            "- cta (one shared CTA label), concept_tag (short slug like \"talent-speed-v1\")"
        )
        json_keys_full = "cta, targeting_copy, concept_tag"
    else:
        ad_platform_block = (
            "AD-PLATFORM copy — the Meta feed fields shown AROUND the image (caption + headline).\n"
            "NEVER printed on the image itself; distinct wording from the on-creative copy:\n"
            "- headline (max 50 characters — the LONG Meta headline field)\n"
            "- headline_short (max 30 characters — the SHORT Meta headline, same message condensed)\n"
            "- body_short (max 125 characters — Primary Text SHORT variant)\n"
            "- body_long (max 300 characters — Primary Text LONG variant with more detail)\n"
            "- description (max 25 characters — Meta description field)\n"
            "- concept_tag (short slug like \"talent-speed-v1\")"
        )
        json_keys_full = ("creative_headline, creative_subhead, headline, headline_short, "
                          "body_short, body_long, description, cta, concept_tag")

    # On-image (Text_On_Visual) field spec. For a BOTH-audience order the on-image copy is
    # UNIQUE per audience (inside targeting_copy), so only the cta stays top-level here.
    if _is_both:
        _on_creative_block = (
            "- cta (the CTA button label on the image; fallback max 20 characters)\n"
            "- ALWAYS provide your best cta for EVERY concept — the pipeline applies the Style\n"
            "  Guide's CTA distribution deterministically after selection, so never return empty.\n"
            "- NOTE: the on-image copy (creative_headline, creative_subhead) is provided PER\n"
            "  AUDIENCE inside targeting_copy below, NOT as top-level fields — this both-audience\n"
            "  order needs UNIQUE Text_On_Visual for Prospecting vs Retargeting."
        )
    else:
        _on_creative_block = (
            "- creative_headline (the main hook shown ON the ad image; fallback max 30 characters)\n"
            "- creative_subhead (ONE short supporting line ON the image, must NOT repeat the primary text below; fallback max 55 characters)\n"
            "- cta (the CTA button label on the image; fallback max 20 characters)\n"
            "- ALWAYS provide your best cta for EVERY concept, even if the matched Style Guide\n"
            "  entry says only some variants (or none) display one — the pipeline applies that\n"
            "  CTA distribution deterministically after selection, so never return an empty cta."
        )

    # Get order brief for priority override
    order_brief = context.get("order_brief", order.get("brief", ""))
    # Bound the brief like every other context block. It was the ONE unbounded
    # input — a very long brief (e.g. a full Key-Messaging block pasted into
    # Additional_Info) bloated the prompt and pushed the model's JSON past the
    # output-token cap → truncated JSON → 0 concepts → no manifest at gate 5.
    _MAX_BRIEF = 6000
    if len(order_brief) > _MAX_BRIEF:
        _orig_len = len(order_brief)
        order_brief = (order_brief[:_MAX_BRIEF]
                       + f"\n\n[Brief truncated for copy generation: {_orig_len} → {_MAX_BRIEF} chars. "
                       + "Lead with the most important direction at the top of the brief.]")
        print(f"    ⚠ BRIEF: {style} brief {_orig_len} chars > {_MAX_BRIEF} cap — truncated for the prompt")
    priority_note = context.get("_priority_note", "")

    # Operator's brief, broken down into routed directives at intake. When present, inject the
    # theme + must-apply copy directives with PREFERENTIAL WEIGHT. This steers content only — the
    # scaffold (# concepts, field structure, Prospecting+Retargeting) is fixed and unaffected.
    _bd = context.get("_brief_breakdown") or None
    if _bd and (_bd.get("theme") or _bd.get("copy_directives")):
        _dirs = "\n".join(f"  - {d}" for d in _bd.get("copy_directives", [])) or \
            "  (none — the theme sets the direction; write with the standard rules)"
        _res = ", ".join(_bd.get("resources", []))
        brief_block = (
            "The operator gave this direction for THIS sprint — treat it as the HIGHEST-priority "
            "creative steer (below only the Legal blocklist). Every concept must clearly reflect it. "
            "It steers ANGLE, MESSAGE, and EMPHASIS only — it does NOT change the number of concepts, "
            "the field structure, or the Prospecting/Retargeting requirement (those are fixed).\n\n"
            f"THEME TO LEAD WITH:\n{_bd.get('theme') or order_brief}\n\n"
            f"MUST APPLY IN THE COPY:\n{_dirs}\n"
            + (f"\nRESOURCES / IDEAS: {_res}\n" if _res else "")
        )
    elif order_brief:
        brief_block = (
            "This brief is the most current creative instruction; follow it for angle, message, and "
            "emphasis. The ONE exception: it can never override the Legal blocklist above — reword any "
            "banned term into its approved alternative.\n\n" + order_brief
        )
    else:
        brief_block = ("No specific brief provided.\n\n"
                       "General: Showcase how Upwork helps businesses find freelancers fast.")

    # Multi-field styles need extra structured copy beyond headline/body/cta.
    _sl = style.strip().lower().replace(" ", "")
    _approved_quotes_lib = _load_approved_quotes() if _sl == "testimonial" else []
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
            "Sticky Note ships BOTH layouts per concept (per the Style Guide): a two-column\n"
            "version AND a single-column version. Provide BOTH sets of fields — the\n"
            "single-column version is NOT a merge of the two columns; it re-expresses the\n"
            "concept as one focused list:\n"
            "Two-column version:\n"
            "- left_headline (max 12 chars — left column title)\n"
            "- right_headline (max 12 chars — right column title)\n"
            "- left_bullets (array of EXACTLY 2 strings, max 30 chars each)\n"
            "- right_bullets (array of EXACTLY 2 strings, max 30 chars each)\n"
            "Single-column version:\n"
            "- single_headline (max 26 chars — the note's title)\n"
            "- single_bullets (array of EXACTLY 3 strings, max 34 chars each — one focused list, parallel structure)\n"
        )
        multi_field_keys = (", left_headline, right_headline, left_bullets, right_bullets"
                            ", single_headline, single_bullets")
    elif _sl == "poll":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Poll\" =====\n"
            "This is a poll ad: a QUESTION above TWO horizontal bars. Each bar shows an ANSWER\n"
            "LABEL and its percentage (e.g. 'Yes  81%' / 'No  19%'), so the poll actually means\n"
            "something. Provide:\n"
            "- poll_question (max 75 chars — the question shown above the bars)\n"
            "- poll_option_a (max 14 chars — the FIRST answer label, e.g. 'Yes', 'Agree', or a short choice)\n"
            "- poll_pct_a (integer 5-95 — the percentage who chose option A)\n"
            "- poll_option_b (max 14 chars — the SECOND answer label, e.g. 'No', 'Disagree', the other choice)\n"
            "- poll_pct_b (integer 5-95 — the percentage who chose option B; poll_pct_a + poll_pct_b should = 100)\n"
            "The question + the two labeled percentages must read as one clear, sensible story\n"
            "(a striking, on-brand stat that supports the ad's message).\n"
        )
        multi_field_keys = ", poll_question, poll_option_a, poll_pct_a, poll_option_b, poll_pct_b"
    elif _sl == "testimonial":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Testimonial\" =====\n"
            "A customer-quote card with a headshot. The on-image quote fills the "
            "Copy_Testimonial slot and MUST fit its cap — do NOT reuse body_long here. "
            "QUOTE SOURCING: if the ORDER BRIEF above contains a real customer quote, use "
            "it in EXACTLY ONE concept — your strongest — shortened only without changing "
            "its meaning. EVERY OTHER concept must invent its own clearly FICTIONAL quote "
            "with a DISTINCT invented person, company, and specific result — no two "
            "concepts may share a quote, name, or company (each board shows a different "
            "customer; identical quotes under different faces is a brand error). NEVER "
            "attribute an invented quote to a real person or real company. Fictional "
            "testimonials are auto-flagged for review. "
            "ALSO provide:\n"
            "- testimonial_quote (max 100 chars — the customer's own first-person quote as "
            "PLAIN text with NO surrounding quotation marks and NO double-quote (\") "
            "characters anywhere (the template adds the quotation marks); a specific, "
            "believable SMB result, e.g. We hired an AI analyst and cut reporting time in half.)\n"
            "- testimonial_author (max 51 chars — 'Firstname Lastname, Title, Company'; "
            "invented person + company unless the brief supplied the real attribution)\n"
        )
        if _approved_quotes_lib:
            _lib_lines = "\n".join(
                '{}. "{}" — {}'.format(i + 1, q, a)
                for i, (q, a) in enumerate(_approved_quotes_lib))
            multi_field_instructions += (
                "APPROVED QUOTE LIBRARY — real, approved quotes. ALWAYS prefer these over "
                "inventing: assign a DIFFERENT library quote (with its attribution EXACTLY "
                "as given) to each concept, best fit first. Shorten only without changing "
                "meaning. Invent a fictional quote ONLY for concepts beyond the library "
                "size.\n" + _lib_lines + "\n"
            )
        multi_field_keys = ", testimonial_quote, testimonial_author"
    elif _sl == "searchresults":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Search Results\" =====\n"
            "A talent search-results UI. ALSO provide:\n"
            "- search_results (array of EXACTLY 3 strings, max 22 chars each — in-demand talent role titles, e.g. 'AI Developer', 'UX Designer')\n"
        )
        multi_field_keys = ", search_results"
    elif _sl == "socialmediaprofile":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Social Media Profile\" =====\n"
            "A freelancer profile card. ALSO provide:\n"
            "- profile_name (max 18 chars — 'Firstname L.')\n"
            "- profile_title (max 28 chars — their role, e.g. 'Chatbot Developer')\n"
            "- profile_left (max 60 chars — short profile blurb, left column)\n"
            "- profile_right (max 60 chars — short profile blurb, right column)\n"
        )
        multi_field_keys = ", profile_name, profile_title, profile_left, profile_right"
    elif _sl == "chatbubble":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Chat Bubble\" =====\n"
            "This ad is TWO chat bubbles simulating a real text CONVERSATION between two\n"
            "people. Bubble 1 opens; bubble 2 replies. It must read as one natural\n"
            "exchange — NOT a headline + subtext, NOT a category label + tagline. Write\n"
            "the way people actually text: casual, human, direct. The exchange should\n"
            "prove a point, answer a question, or surface a compelling stat about using\n"
            "freelancers or Upwork. ALSO provide:\n"
            "- chat_label (bubble 1 — the OPENER — max 18 chars — a short, natural first\n"
            "  message, e.g. 'need a designer' or 'swamped again')\n"
            "- chat_message (bubble 2 — the REPLY — max 90 chars — a natural response that\n"
            "  lands the point, e.g. 'found one on Upwork this morning, proposals already\n"
            "  coming in')\n"
        )
        multi_field_keys = ", chat_label, chat_message"
    elif _sl == "textwithbutton":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Text with Button\" =====\n"
            "The entire ad is a single button label — make it punchy. ALSO provide:\n"
            "- button_text (max 15 chars — the button label, e.g. 'Hire faster now')\n"
        )
        multi_field_keys = ", button_text"
    elif _sl == "piechart":
        multi_field_instructions = (
            "\n===== EXTRA FIELDS FOR \"Pie Chart\" =====\n"
            "A four-quadrant graphic. ALSO provide:\n"
            "- pie_labels (array of EXACTLY 4 strings, max 24 chars each — the four quadrant labels)\n"
            "- pie_center (max 24 chars — the short center callout)\n"
        )
        multi_field_keys = ", pie_labels, pie_center"

    copy_instructions = context.get("copy_instructions", "")

    # Quoted spans in the brief (e.g. an approved testimonial quote) — used below to
    # flag leakage into non-Testimonial concepts' feed copy.
    _brief_quotes = [q.strip() for q in re.findall(r'"([^"]{25,300})"', order_brief or "")]

    # Resolve the ONE matching Ad Type Style Guide entry (untruncated) instead of
    # dumping the whole guide truncated — see _style_guide_block.
    _entry, _entry_name = _style_guide_block(style, copy_style_rules)
    if _entry:
        style_rules_block = (
            "===== AD TYPE STYLE GUIDE — MATCHED ENTRY (BINDING) =====\n"
            f'Ad type resolved to "{style}" — apply this entry EXACTLY. These per-type\n'
            "rules OVERRIDE the generic Text_On_Visual defaults: follow the exact\n"
            "structure, character limits, punctuation, layout density, and CTA guidance.\n\n"
            f"{_entry}"
        )
    else:
        style_rules_block = (
            "===== AD TYPE STYLE GUIDE (no exact entry matched) =====\n"
            f'No Style Guide entry cleanly matched "{style}". Apply the closest-matching\n'
            "ad type below and note the mismatch — do NOT default to a generic\n"
            "single-headline spec.\n\n"
            f"{copy_style_rules[:8000]}"
        )

    prompt = f"""You are writing paid acquisition ad copy for Upwork. Follow every brand rule below exactly.

{_CRAFT_BAR}

===== AUTHORITATIVE COPY INSTRUCTIONS (BINDING — Adrie's spec) =====
These govern voice, field limits, formatting, legal, and QA. Apply them to every
field. The LEGAL "Terms to Avoid" blocklist is ABSOLUTE — it overrides the order
brief itself. If the brief asks for a banned idea (e.g. "vetted", "pre-screened",
"guaranteed"), express it with the approved alternative; NEVER output a banned term,
no matter what the brief says.
{copy_instructions[:6000]}

===== ORDER BRIEF / OPERATOR DIRECTION (HIGH PRIORITY — but never above Legal) =====
{brief_block}

===== BRAND VOICE =====
{brand_voice[:3000]}

===== WRITING STYLE =====
{writing_style[:4000]}

===== COMPLIANCE AND LEGAL RULES =====
{compliance[:20000]}

===== COPY PLAYBOOK =====
{playbook[:2000]}

===== APPROVED CLAIMS AND STATS =====
Use only these verified claims. Do not invent statistics.
{claims[:2000]}

===== COPY BANK (approved headlines and copy) =====
Reference these for tone and structure. Match this quality.
{copy_bank[:3000]}

===== TARGETING RULES ({targeting_type}) =====
{targeting_rules}

===== REAL AD EXAMPLES ({targeting_type}) =====
Study these examples closely. Your output should match this quality and style.
{examples[:4000]}

===== PERFORMANCE DATA — WHAT ACTUALLY WORKS =====
The following shows real ad performance ranked by cost per job post.
Use this to inform your creative decisions. Lean into patterns that perform well.
Black backgrounds dominate the top performers. Quote-driven messaging outperforms
other approaches. Specific freelancer categories outperform generic talent messaging.
{context.get('performance_data', '')[:3000]}

{style_rules_block}

===== YOUR ASSIGNMENT =====
Generate {qty} ad copy concepts. Each concept must be COMPLETE — never truncate or
abbreviate later concepts to save space; every field must be fully written for all {qty}.{_angle_line}{_body_format_line}

Platform: {batch.get('platform', 'Meta')}
Format: {batch.get('format', 'Static Feed')}
Visual Style: {style}
Targeting: {targeting_type}
Brief: {order.get('brief', 'Showcase how Upwork helps businesses find freelancers fast')}
{_template_limit_block(style)}
For each concept provide these exact fields. There are TWO separate buckets of
copy and they must NOT reuse each other's text:

ON-CREATIVE copy — the words BAKED INTO the ad image. Punchy and short so it
fits the design. This is the ONLY copy that appears on the image itself. LENGTH
IS GOVERNED BY THE MATCHED STYLE GUIDE ENTRY ABOVE (and any TEMPLATE CHARACTER
LIMITS) — follow those caps; the numbers below are only fallbacks when the entry
is silent on a field:
{_on_creative_block}

{ad_platform_block}
{multi_field_instructions}
RULES:
- Match the brand voice exactly — clear, concise, supportive, professional
- Use only approved claims and statistics from the section above
- Follow all compliance and legal rules
- Study the real ad examples and match their quality
- No generic marketing speak — be specific about what Upwork offers
- Headlines should follow the 95/5 rule: 95% informative, 5% personality

Return as JSON array of objects with exactly these keys: {json_keys_full}{multi_field_keys}. No other text."""

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
                    "model": _COPY_MODEL,
                    # 6 concepts × many fields (incl. 300-char body_long + per-style
                    # extras like testimonial_quote) can exceed a tight cap and get
                    # truncated mid-JSON ("Unterminated string" → 0 concepts). Give
                    # ample headroom; billing is by tokens actually produced. Paired
                    # with _salvage_json_array below so a truncated array still yields
                    # its complete concepts instead of zero.
                    "max_tokens": 8000,
                    "messages": [{"role": "user", "content": prompt}],
                    # STRUCTURED OUTPUT: the API enforces the per-style schema, so the
                    # response is guaranteed-valid JSON in the declared shape (2026-07-28).
                    "output_config": {"format": {"type": "json_schema",
                                                 "schema": _concept_schema(style, _is_both, qty)}},
                    **_thinking_params(),
                },
                timeout=120
            )

            if response.status_code == 200:
                _rj = response.json()
                text = _response_text(_rj).strip()
                _u = _rj.get("usage", {})
                _add_token_usage(sprint_id, _COPY_MODEL,
                                 _u.get("input_tokens"), _u.get("output_tokens"))
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]

                try:
                    parsed = json.loads(text.strip())
                except json.JSONDecodeError as je:
                    # Should be unreachable with structured output; kept as belt-and-
                    # suspenders for older models / gateway paths without output_config.
                    parsed = _salvage_json_array(text)
                    if not parsed:
                        raise je
                    print(f"    {style}: recovered {len(parsed)} concept(s) from truncated JSON")
                # Structured output wraps the array: {"concepts": [...]}
                if isinstance(parsed, dict) and isinstance(parsed.get("concepts"), list):
                    parsed = parsed["concepts"]
                if isinstance(parsed, list):
                    for j, concept in enumerate(parsed):
                        concept["concept_id"] = f"concept_{i}_{style.lower().replace(' ', '_')}_{seq}_{j}"
                        concept["batch_index"] = i
                        concept["visual_style"] = style
                        # Interim policy (Logan 2026-07-15): no real-quote library exists,
                        # so testimonial quotes are fictional unless the brief supplied one.
                        # Tag every testimonial concept so reviewers always see it.
                        if _sl == "testimonial":
                            concept["testimonial_fictional"] = True
                            # Pin marker: an APPROVED quote (brief or live library) is
                            # privileged — NOT fictional. Match on substring OR content-word
                            # overlap so a legitimately SHORTENED real quote isn't false-
                            # flagged fictional (Adrie 2026-07-23).
                            _approved_texts = list(_brief_quotes) + [q for q, _a in _approved_quotes_lib]
                            if _quote_from_library(concept.get("testimonial_quote", ""), _approved_texts):
                                concept["brief_quote_used"] = True
                                concept.pop("testimonial_fictional", None)
                        # Brief-quote leakage: the brief's testimonial quote showing up in a
                        # NON-Testimonial concept's copy (found 2026-07-16 on Photo with Text
                        # — ADAM's own reviewer called it a compliance risk).
                        elif _brief_quotes:
                            _blob = " ".join(str(concept.get(_f, "")) for _f in
                                             ("body_short", "body_long", "creative_headline",
                                              "creative_subhead", "headline"))
                            _blob += " " + json.dumps(concept.get("targeting_copy") or {})
                            if any(_bq in _blob for _bq in _brief_quotes):
                                concept["brief_quote_leak"] = True
                        # "Both" concepts carry feed copy under targeting_copy; mirror
                        # the Prospecting set into the flat fields so the rest of the
                        # pipeline (review, image prompts) still reads them. The manifest
                        # expands targeting_copy into a Prospecting + a Retargeting row.
                        _tc = concept.get("targeting_copy")
                        if isinstance(_tc, dict) and _tc:
                            _p = _flatten_audience(_tc.get("Prospecting") or _tc.get("prospecting") or {})
                            # Includes the on-image creative now that P&R generates it per
                            # audience — base mirrors Prospecting so single-audience readers work.
                            for _ff in ("creative_headline", "creative_subhead", "headline",
                                        "headline_short", "body_short", "body_long", "description"):
                                if not concept.get(_ff) and isinstance(_p, dict):
                                    concept[_ff] = _p.get(_ff, "")
                            # Reciprocal backfill: the model sometimes emits an EMPTY audience
                            # feed field ("body_short": ""). Fill it from the base concept so
                            # every audience block is complete for review + manifest (found on
                            # Notification, rerun v2 2026-07-27).
                            for _aud_k, _aud_v in _tc.items():
                                if not isinstance(_aud_v, dict):
                                    continue
                                for _ff in ("headline", "headline_short", "body_short",
                                            "body_long", "description"):
                                    if not _flatten_audience(_aud_v).get(_ff) and concept.get(_ff):
                                        _aud_v[_ff] = concept[_ff]
                        # Emoji-bullet backstop (Adrie: bullets are emoji-led, never a
                        # plain "•"). Any leftover plain bullet gets a VARIED emoji from the
                        # rotating palette — not a stack of flat ✅ (Logan, 2026-07-23).
                        for _bf in ("body_long", "body_short"):
                            if concept.get(_bf):
                                concept[_bf] = _emojify_plain_bullets(concept[_bf])
                        _tcb = concept.get("targeting_copy")
                        if isinstance(_tcb, dict):
                            for _aud in _tcb.values():
                                if isinstance(_aud, dict):
                                    for _bf in ("body_long", "body_short"):
                                        if _aud.get(_bf):
                                            _aud[_bf] = _emojify_plain_bullets(_aud[_bf])
                        # Style-guide adherence: a HEADLINE-ONLY ad type must not carry
                        # an on-image subhead (Adrie 2026-07-23: Graphic with Text was
                        # emitting a subhead the guide doesn't allow). Strip it.
                        if concept.get("creative_subhead") and not _style_uses_subhead(style):
                            concept["creative_subhead"] = ""
                        # Enforce Adrie's sentence-case rule on headlines/CTAs.
                        for _cf in _SENTENCE_CASE_FIELDS:
                            if concept.get(_cf):
                                concept[_cf] = _to_sentence_case(concept[_cf])
                        # Same on-image enforcement for EACH audience's creative (P&R): strip an
                        # off-spec subhead on headline-only styles, then sentence-case its fields.
                        if isinstance(_tcb, dict):
                            for _aud in _tcb.values():
                                if isinstance(_aud, dict):
                                    if _aud.get("creative_subhead") and not _style_uses_subhead(style):
                                        _aud["creative_subhead"] = ""
                                    for _cf in _SENTENCE_CASE_FIELDS:
                                        if _aud.get(_cf):
                                            _aud[_cf] = _to_sentence_case(_aud[_cf])
                        # Re-capitalize proper nouns (days of the week, Upwork) that
                        # _to_sentence_case just lowercased. Deterministic, runs LAST so it
                        # wins over sentence-casing. Fixes "friday" -> "Friday" (2026-07-27).
                        _fix_concept_proper_nouns(concept)
                        _flags = _scan_banned_terms(concept)
                        if _flags:
                            concept["legal_flags"] = _flags
                            print(f"    ⚠ LEGAL: {style} concept {j} uses banned term(s): {', '.join(_flags)}")
                        _lf = _enforce_lengths(concept, style)
                        if _lf:
                            print(f"    ⚠ LENGTH: {style} concept {j} over hard cap: {', '.join(_lf)}")
                        # Segmentation backstop (2026-07-21): a Prospecting+Retargeting concept
                        # MUST carry targeting_copy with a populated Prospecting AND Retargeting
                        # set. If the model returned one flat set instead (Adrie's bug), flag it
                        # loudly + on the concept so it never ships one-set-only silently.
                        if _is_both:
                            _tcc = concept.get("targeting_copy")
                            _have_both = (isinstance(_tcc, dict)
                                          and (_tcc.get("Prospecting") or _tcc.get("prospecting"))
                                          and (_tcc.get("Retargeting") or _tcc.get("retargeting")))
                            if not _have_both:
                                concept["targeting_incomplete"] = True
                                print(f"    ⚠ SEGMENTATION: {style} concept {j} is Prospecting+Retargeting "
                                      f"but returned only one copy set (missing targeting_copy).")
                        concepts.append(concept)
                # Fit Meta feed fields to their caps (rewrite-or-trim) BEFORE
                # review, so selection compares cap-clean copy.
                try:
                    _fit_feed_fields(concepts, style, api_key, sprint_id)
                except Exception as _fe:
                    print(f"    feed-fit skipped: {str(_fe)[:60]}")
                # Combined on-image caps (Social Media 65, Sticky Note double 136) — final
                # deterministic fit AFTER per-field, so the SUM respects the design's space.
                for _c in concepts:
                    _enforce_combined_caps(_c, style)
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


def _breakdown_brief(brief, order, api_key, sprint_id=None):
    """Parse the operator's Additional-Info / brief ONCE into structured, routed
    directives (Ravi/Adrie, 2026-07-22). The scaffold — number of ads, number of copy
    variations the operator chooses from, and the Prospecting+Retargeting split — is
    FIXED and NEVER changes based on the brief. The brief only steers CONTENT, and gets
    preferential weight where it applies. Breaking it down up front lets each stage read
    just its slice instead of re-reading the whole brief at every gate.

    Returns a dict (also saved as brief_breakdown.json) or None if there's no brief:
      {theme, copy_directives[], design_directives[], resources[], has_high_touch}
    """
    brief = (brief or "").strip()
    if not brief:
        return None
    # Drop unfilled brief-template placeholder lines — a line that is ONLY a parenthetical
    # hint (e.g. "(One or two sentences …)" or "- (A required phrase …)") from the Insert-
    # brief-template scaffold — so an un-edited section isn't parsed as real direction and
    # doesn't trip the "placeholder sections unfilled" flag (Adrie 2026-07-23).
    brief = "\n".join(ln for ln in brief.splitlines()
                      if not re.match(r"^\s*[-*]?\s*\(.*\)\s*$", ln)).strip()
    if not brief:
        return None
    prompt = (
        "You are the intake analyst for an ad-production pipeline. Break the operator's "
        "ADDITIONAL-INFO / brief below into structured direction the later stages will follow.\n\n"
        "HARD RULE — you do NOT control structure. The number of ads, the number of copy "
        "variations the operator chooses from, and the Prospecting + Retargeting split are FIXED "
        "by the order and must NEVER change based on this brief. Only extract CONTENT direction. "
        "Never infer a quantity or an audience decision, and never invent a directive that isn't "
        "in the brief.\n\n"
        "Classify into:\n"
        "- theme: the single core message/angle to lead with (1-2 sentences). If the brief is only "
        "key messaging, this IS the theme — the standard rules still write the ads around it.\n"
        "- copy_directives: array of specific, must-apply COPY instructions the operator explicitly "
        "asked for (required phrases, claims to feature, tone, do/don't). [] if none.\n"
        "- design_directives: array of visual/style/performance/ad-style instructions that apply at "
        "the IMAGE/design stage, not copy. [] if none.\n"
        "- resources: array of reference ideas, URLs, or assets mentioned. [] if none.\n"
        "- has_high_touch: true only if the brief has specific must-apply directives beyond a general "
        "theme; false if it's only theme/messaging.\n\n"
        f'BRIEF:\n"""\n{brief[:6000]}\n"""\n\n'
        "Return ONLY a JSON object with keys theme, copy_directives, design_directives, resources, "
        "has_high_touch. No prose."
    )
    try:
        import httpx
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": _COPY_MODEL, "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}], **_thinking_params(),
                  # Schema-enforced brief breakdown.
                  "output_config": {"format": {"type": "json_schema", "schema": {
                      "type": "object", "properties": {
                          "theme": {"type": "string"},
                          "copy_directives": {"type": "array", "items": {"type": "string"}},
                          "design_directives": {"type": "array", "items": {"type": "string"}},
                          "resources": {"type": "array", "items": {"type": "string"}},
                          "has_high_touch": {"type": "boolean"}},
                      "required": ["theme", "copy_directives", "design_directives",
                                   "resources", "has_high_touch"],
                      "additionalProperties": False}}}},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"    brief-breakdown: API {r.status_code} — falling back to raw brief")
            return None
        _rj = r.json()
        text = _response_text(_rj).strip()
        _u = _rj.get("usage", {})
        _add_token_usage(sprint_id, _COPY_MODEL, _u.get("input_tokens"), _u.get("output_tokens"))
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        raw = json.loads(text.strip())
        bd = {
            "theme": str(raw.get("theme", "")).strip(),
            "copy_directives": [str(x).strip() for x in (raw.get("copy_directives") or []) if str(x).strip()],
            "design_directives": [str(x).strip() for x in (raw.get("design_directives") or []) if str(x).strip()],
            "resources": [str(x).strip() for x in (raw.get("resources") or []) if str(x).strip()],
            "has_high_touch": bool(raw.get("has_high_touch")),
        }
        if sprint_id:
            try:
                (RUNS_DIR / sprint_id / "brief_breakdown.json").write_text(json.dumps(bd, indent=2))
            except Exception:
                pass
        print(f"    brief-breakdown: theme + {len(bd['copy_directives'])} copy / "
              f"{len(bd['design_directives'])} design directive(s)"
              f"{' [high-touch]' if bd['has_high_touch'] else ' [theme-only]'}")
        return bd
    except Exception as e:
        print(f"    brief-breakdown skipped ({str(e)[:50]}) — falling back to raw brief")
        return None


def _generate_real_copy(order, context, api_key, sprint_id=None):
    """Generate copy concepts, fanning out one call per style concurrently.

    Per-style calls are independent + I/O-bound (~120s each); a serial loop
    stacked minutes on wide orders. Bounded by COPY_CONCURRENCY (default 5)
    to respect API rate limits."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Sub-batch each style into small angle-seeded calls: _CONCEPTS_PER_STYLE concepts split
    # into groups of _COPY_BATCH_SIZE, each its own call with a distinct creative angle. Keeps
    # every call well under the output ceiling (no truncation/"fatigue") and diversifies output.
    tasks = []  # each: (i, batch, style, count, angle, seq)
    for i, batch in enumerate(order.get("batches", [])):
        for style in batch.get("visual_styles", ["default"]):
            pos = seq = 0
            while pos < _CONCEPTS_PER_STYLE:
                cnt = min(_COPY_BATCH_SIZE, _CONCEPTS_PER_STYLE - pos)
                tasks.append((i, batch, style, cnt, _COPY_ANGLES[seq % len(_COPY_ANGLES)], seq))
                pos += cnt
                seq += 1
    total = len(tasks)
    if total == 0:
        return {"concepts": [], "generated_at": datetime.now(timezone.utc).isoformat()}

    # Parse the operator's brief ONCE into routed directives (preferential weight in copy;
    # design directives handed to stage 03 via brief_breakdown.json). Stored on context so
    # every per-style call reads the same breakdown. Structure stays fixed regardless.
    if context.get("_brief_breakdown") is None:
        context["_brief_breakdown"] = _breakdown_brief(order.get("brief", ""), order, api_key, sprint_id)

    try:
        workers = int(os.environ.get("COPY_CONCURRENCY", "5") or "5")
    except ValueError:
        workers = 5
    workers = max(1, min(workers, total))

    results = {}
    done = 0
    lock = threading.Lock()

    def _run(idx, i, batch, style, cnt, angle, seq):
        nonlocal done
        res = _generate_copy_for_style(i, batch, style, order, context, api_key, sprint_id,
                                       count=cnt, angle=angle, seq=seq)
        with lock:
            done += 1
            _save_progress(sprint_id, "stage_02_copy_gen", done, total, f"Copy: {style}")
        return idx, res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run, idx, *t) for idx, t in enumerate(tasks)]
        for fut in as_completed(futures):
            try:
                idx, res = fut.result()
                results[idx] = res
            except Exception as e:
                print(f"    copy task error: {str(e)[:60]}")

    concepts = []
    # A style "failed" only if EVERY one of its sub-batches produced nothing.
    style_got = {}
    for idx in range(total):
        res = results.get(idx, [])
        concepts.extend(res)
        _st = tasks[idx][2]
        style_got[_st] = style_got.get(_st, False) or bool(res)
    failed_styles = [s for s, got in style_got.items() if not got]
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

    # Per-style ship targets from the ORDER (style_quantities) — "one style needs
    # 5, one needs 3, one needs 1" (Logan, 2026-07-16). Previously captured but
    # only displayed; selection was hardcoded top-3. Default stays 3; capped at
    # the overgenerate count (6). The gate-3 picker can still override by hand.
    _targets = {}
    for _b in (order or {}).get("batches", []):
        for _s, _q in (_b.get("style_quantities") or {}).items():
            try:
                _targets[_norm_style(_s)] = max(1, min(int(_q), 6))
            except (TypeError, ValueError):
                pass

    def _review_one_group(group_key, group_concepts):
        """Review + rank one style's concepts (one Claude call)."""
        reviewed = []
        style = group_concepts[0].get("visual_style", "unknown")
        # Adrie's expected-output spec (7/27): every run must return the TOP 2 copy
        # choices per ad style — so a P&R run yields 2 Prospecting + 2 Retargeting
        # choices after the manifest doubling. Orders of qty 1 previously selected
        # just 1 concept (= 1 choice per audience). Floor the selection at 2
        # (env-tunable via ADAM_MIN_CHOICES); larger ordered quantities still win.
        try:
            _min_choices = int(os.environ.get("ADAM_MIN_CHOICES", "2") or "2")
        except ValueError:
            _min_choices = 2
        target = max(_min_choices, _targets.get(_norm_style(style), 3))

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
                    "model": _COPY_MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": review_prompt}], **_thinking_params(),
                    # Schema-enforced review response (same guarantee as generation).
                    "output_config": {"format": {"type": "json_schema", "schema": {
                        "type": "object", "properties": {"rankings": {"type": "array", "items": {
                            "type": "object", "properties": {
                                "original_index": {"type": "integer"},
                                "rank": {"type": "integer"},
                                "selected": {"type": "boolean"},
                                "score": {"type": "number"},
                                "review_notes": {"type": "string"}},
                            "required": ["original_index", "rank", "selected", "score", "review_notes"],
                            "additionalProperties": False}}},
                        "required": ["rankings"], "additionalProperties": False}}},
                },
                timeout=120
            )

            if response.status_code == 200:
                _rj = response.json()
                text = _response_text(_rj).strip()
                _u = _rj.get("usage", {})
                _add_token_usage(sprint_id, _COPY_MODEL,
                                 _u.get("input_tokens"), _u.get("output_tokens"))
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]

                rankings = json.loads(text.strip())
                # Structured output wraps the array: {"rankings": [...]}
                if isinstance(rankings, dict) and isinstance(rankings.get("rankings"), list):
                    rankings = rankings["rankings"]

                # Apply rankings back to the concepts
                for ranking in rankings:
                    orig_idx = ranking.get("original_index", 1) - 1  # Convert to 0-based
                    if 0 <= orig_idx < len(group_concepts):
                        concept = group_concepts[orig_idx].copy()
                        concept["rank"] = ranking.get("rank", 99)
                        concept["selected"] = ranking.get("selected", False)
                        concept["score"] = ranking.get("score", 0)
                        concept["review_notes"] = ranking.get("review_notes", "")
                        # Backstop: a concept that tripped the banned-terms scan
                        # (legal) or overflowed a HARD on-image char cap (length) is
                        # never shipped as-is — de-select it and push it to the bottom
                        # so a clean concept takes its place.
                        if concept.get("legal_flags") or concept.get("length_flags"):
                            concept["selected"] = False
                            concept["rank"] = 99
                            _notes = []
                            if concept.get("legal_flags"):
                                _notes.append("⚠ LEGAL — banned term(s): "
                                              + ", ".join(concept["legal_flags"]))
                            if concept.get("length_flags"):
                                _notes.append("⚠ LENGTH — over template cap: "
                                              + ", ".join(concept["length_flags"]))
                            concept["review_notes"] = (". ".join(_notes) + ". "
                                                       + concept.get("review_notes", ""))
                        # SOFT demotion: feed-field overflow (length_warnings = over
                        # Adrie's Meta caps, e.g. body_long>300) prefers a clean
                        # alternative but stays shippable. Keep rank (it orders the
                        # backfill); found live 2026-07-15: two Testimonial concepts
                        # shipped 30% over body_long because warnings were recorded
                        # but never consulted at selection time.
                        elif concept.get("length_warnings") and concept.get("selected"):
                            concept["selected"] = False
                            concept["review_notes"] = (
                                "⚠ FEED LENGTH — over Meta field cap(s): "
                                + ", ".join(concept["length_warnings"]) + ". "
                                + concept.get("review_notes", ""))
                        # Duplicate-quote backstop: multiple concepts sharing one
                        # testimonial quote render as different headshots with the SAME
                        # attribution on the boards (five faces, one name — found
                        # 2026-07-16). Flag every repeat after the first.
                        _q = " ".join(str(concept.get("testimonial_quote", "")).split()).lower()
                        if _q:
                            _seen_qs = [" ".join(str(x.get("testimonial_quote", "")).split()).lower()
                                        for x in reviewed]
                            if _q in _seen_qs:
                                concept["review_notes"] = (
                                    "⚠ DUPLICATE QUOTE — same testimonial as another concept; "
                                    "swap in a distinct quote before running (boards show "
                                    "different headshots with identical attribution). "
                                    + concept.get("review_notes", ""))
                        if concept.get("brief_quote_leak"):
                            concept["review_notes"] = (
                                "⚠ BRIEF-QUOTE LEAK — this non-Testimonial concept quotes the "
                                "brief's testimonial in its feed copy; confirm before running. "
                                + concept.get("review_notes", ""))
                        if concept.get("brief_quote_used"):
                            concept["review_notes"] = (
                                "📌 Uses an APPROVED quote (brief/library) — pinned into the selection. "
                                + concept.get("review_notes", ""))
                        # Fictional-testimonial notice (interim policy — see copy gen):
                        # informational, does NOT de-select; reviewers verify/swap at gate 3.
                        if concept.get("testimonial_fictional"):
                            concept["review_notes"] = (
                                "ℹ FICTIONAL testimonial — no approved quote assigned; "
                                "add quotes to the Quotes page to replace invented ones. "
                                + concept.get("review_notes", ""))
                        reviewed.append(concept)

                # Select EXACTLY `target` concepts (the style's ordered quantity;
                # default 3), cleanest-first: fully-clean by rank, then soft-warned
                # by (warning count, rank), then hard-flagged by (flag count, rank)
                # only if still short. A legal-flagged concept NEVER ships. The AI's
                # own top-3 flags are advisory — its RANK is the quality signal here.
                eligible = [c for c in reviewed if not c.get("legal_flags")]
                eligible.sort(key=lambda c: (not c.get("brief_quote_used"),
                                             bool(c.get("length_flags")),
                                             bool(c.get("length_warnings")),
                                             len(c.get("length_flags", [])),
                                             len(c.get("length_warnings", [])),
                                             c.get("rank", 99)))
                # The selected set is the operator's CHOICES (Adrie: top 2 per style) —
                # near-duplicate picks defeat the point ("...live by Friday" vs
                # "...converting by Friday"). Greedy diverse pick: take cleanest-first,
                # skipping any whose on-image headline near-duplicates an already-picked
                # one; backfill from the skipped if the diverse pool runs short.
                def _hl_of(c):
                    return c.get("creative_headline") or c.get("headline") or ""
                picked, skipped = [], []
                for c in eligible:
                    dup = any(_headlines_near_dup(_hl_of(c), _hl_of(x)) for x in picked)
                    (picked if (len(picked) < target and not dup) else skipped).append(c)
                for c in skipped:
                    if len(picked) >= target:
                        break
                    picked.append(c)
                _picked_ids = {id(c) for c in picked}
                for c in eligible:
                    c["selected"] = id(c) in _picked_ids
                got = sum(1 for c in reviewed if c.get("selected"))
                if got < target:
                    print(f"    ⚠ {style}: only {got} shippable concept(s) for a target of {target}")
                print(f"    Reviewed {style}: {got} of {len(reviewed)} selected (target {target})")

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
        # Style Guide CTA distribution (one-with/rest-without etc.) — applied to the
        # final selection regardless of which path (ranked or fallback) produced it.
        _apply_cta_mix(reviewed, style)
        _enforce_conditional_caps(reviewed, style)
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

    # Operator's design directions (from the brief breakdown at intake) — appended to
    # Gemini image prompts so the visual direction carries into the image stage. The copy
    # stage already applied its slice; this is the design slice (Additional-Info logic).
    _design_directives = []
    try:
        _bd_json = json.loads((run_dir / "brief_breakdown.json").read_text())
        _design_directives = [d for d in (_bd_json.get("design_directives") or []) if d]
        if _design_directives:
            print(f"  Brief design directions: {len(_design_directives)} — applied to Gemini prompts")
    except Exception:
        pass

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
        # Poll (2026-07-02): has a full-bleed Image-Placeholder behind the poll
        # card — feed it a library photo so polls don't repeat the template image.
        "Poll",
    }

    # Styles that only need a background (no scene generation)
    BACKGROUND_ONLY = {
        "Pie Chart", "Search Results", "Search Bar with Talent Badge",
        "Text Only", "Chat Bubble", "Reminder",
        "Tweet / Post Mockup",
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
                  # Profile mocks: avatar/UI baked in, no library photo slot. Talent
                  # Profile's headshot is overlaid in the plugin from the curated
                  # Example Profiles, so it needs no pipeline photo. (2026-07-07)
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

    # Track library photos already used in THIS sprint so each ad gets a distinct
    # image. select_photo only excludes what the caller passes, so without this
    # every photo row re-picks from the same small pool → the same photo repeats.
    used_photo_ids = []

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
                # Pin the library photo per concept: pick once on the first size and
                # reuse it for the other sizes, so all sizes of a concept show the
                # SAME photo (previously each size re-picked → different faces on the
                # same concept). Non-library styles keep regenerating per size.
                _concept_photo = None
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

                    if _concept_photo is not None:
                        # Reuse the per-concept library pick for this concept's
                        # other sizes — one photo across 1:1 / 4:5 / 9:16.
                        figma_node_id = _concept_photo["figma_node_id"]
                        figma_asset_name = _concept_photo["figma_asset_name"]
                        match_strength = _concept_photo["match_strength"]
                        figma_node_id_left = _concept_photo["figma_node_id_left"]
                        figma_asset_name_left = _concept_photo["figma_asset_name_left"]
                        figma_node_id_right = _concept_photo["figma_node_id_right"]
                        figma_asset_name_right = _concept_photo["figma_asset_name_right"]
                        method = _concept_photo["method"]
                        prompt = _concept_photo["prompt"]
                    elif style in DUAL_PHOTO_LIBRARY_STYLES and library_cache:
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
                                exclude_ids=used_photo_ids or None,
                                concept=concept,
                            )
                            _rt_excl = list(used_photo_ids)
                            if picked_left.get("figma_asset_id"):
                                _rt_excl.append(picked_left.get("figma_asset_id"))
                            picked_right = pick_photo_for_asset(
                                visual_style=style,
                                order=order,
                                sprint_id=sprint_id,
                                components=library_cache,
                                exclude_ids=_rt_excl or None,
                                concept=concept,
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
                                for _pid in (figma_node_id_left, figma_node_id_right):
                                    if _pid:
                                        used_photo_ids.append(_pid)
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
                        # Pull a photo from the tagged library, EXCLUDING photos
                        # already used this sprint so each ad gets a distinct image.
                        try:
                            from figma_library import pick_photo_for_asset
                            picked = pick_photo_for_asset(
                                visual_style=style,
                                order=order,
                                sprint_id=sprint_id,
                                components=library_cache,
                                exclude_ids=used_photo_ids or None,
                                concept=concept,
                            )
                            # If excluding used photos emptied the pool, retry
                            # allowing repeats (variety is best-effort, never fail).
                            if used_photo_ids and (not picked.get("is_photo_based") or picked.get("needs_human_selection")):
                                picked = pick_photo_for_asset(
                                    visual_style=style,
                                    order=order,
                                    sprint_id=sprint_id,
                                    components=library_cache,
                                    concept=concept,
                                )
                            if picked.get("is_photo_based") and not picked.get("needs_human_selection"):
                                method = "figma_library"
                                prompt = ""
                                figma_node_id = picked.get("figma_asset_id", "")
                                figma_asset_name = picked.get("figma_asset_name", "")
                                match_strength = picked.get("match_strength", "")
                                if figma_node_id:
                                    used_photo_ids.append(figma_node_id)
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
                        if _design_directives:
                            prompt = f"{prompt} Art direction from the operator's brief: {'; '.join(_design_directives)}."

                    # Cache this concept's library pick so its remaining sizes reuse
                    # the SAME photo (set once, on the first size). Only library-photo
                    # styles are pinned; Gemini/skip styles re-run per size as before.
                    if _concept_photo is None and library_cache and (
                        style in DUAL_PHOTO_LIBRARY_STYLES or style in PHOTO_LIBRARY_STYLES):
                        _concept_photo = {
                            "figma_node_id": figma_node_id,
                            "figma_asset_name": figma_asset_name,
                            "match_strength": match_strength,
                            "figma_node_id_left": figma_node_id_left,
                            "figma_asset_name_left": figma_asset_name_left,
                            "figma_node_id_right": figma_node_id_right,
                            "figma_asset_name_right": figma_asset_name_right,
                            "method": method,
                            "prompt": prompt,
                        }

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
            _add_image_usage(sprint_id, 1)

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
                "model": _COPY_MODEL,
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
            text = _response_text(response.json()).strip()
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

        base_row = {
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
            # AD-PLATFORM copy — shown in the board's left panels ONLY (the Meta
            # feed fields around the image). Never printed on the creative.
            "Primary_Text_Short": concept.get("body_short", concept.get("body", "")),
            "Primary_Text_Long": concept.get("body_long", ""),
            "Headline": concept.get("headline", row.get("headline", "")),        # LONG Meta headline
            "Headline_Short": concept.get("headline_short", ""),                 # SHORT Meta headline
            "Description": concept.get("description", ""),
            "CTA": concept.get("cta", ""),
            # Style Guide CTA mix: "true" marks a variant that displays NO CTA — the
            # plugin reads no_cta to pick the no-CTA template variant (wantCTA hint).
            "no_cta": "true" if concept.get("no_cta") else "",
            # ON-CREATIVE copy — the ONLY copy baked onto the ad image. Distinct
            # wording from the platform copy above so nothing is duplicated onto
            # the creative. Falls back to the platform headline for older concepts
            # that predate the split.
            "Headline_On_Creative": concept.get("creative_headline", concept.get("headline", row.get("headline", ""))),
            "Subhead_On_Creative": concept.get("creative_subhead", ""),
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
            # Sticky Note single-column layout (Style Guide entry 17 requires BOTH
            # layouts per concept; caps from the Figma 'Rules' layer: 26 / 112).
            "Single_Headline": concept.get("single_headline", ""),
            "Single_Bullets": _join_bullets(concept.get("single_bullets")),
            # Poll fields — question + two bar percentages (drive % text + bar width).
            "Poll_Question": concept.get("poll_question", ""),
            "Poll_Option_A": concept.get("poll_option_a", ""),
            "Poll_Pct_A": concept.get("poll_pct_a", ""),
            "Poll_Option_B": concept.get("poll_option_b", ""),
            "Poll_Pct_B": concept.get("poll_pct_b", ""),
            # Per-style multi-field copy for the remaining structured templates.
            "Testimonial_Quote": concept.get("testimonial_quote", ""),
            "Testimonial_Author": concept.get("testimonial_author", ""),
            "Search_Results": _join_bullets(concept.get("search_results")),
            "Profile_Name": concept.get("profile_name", ""),
            "Profile_Title": concept.get("profile_title", ""),
            "Profile_Left": concept.get("profile_left", ""),
            "Profile_Right": concept.get("profile_right", ""),
            "Chat_Label": concept.get("chat_label", ""),
            "Chat_Message": concept.get("chat_message", ""),
            "Button_Text": concept.get("button_text", ""),
            "Pie_Labels": _join_bullets(concept.get("pie_labels")),
            "Pie_Center": concept.get("pie_center", ""),
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
        }
        # "Prospecting and Retargeting": each audience gets its OWN creative now (Adrie
        # 2026-07-23) — emit a Prospecting row AND a Retargeting row, same image/style but
        # UNIQUE on-image (Text_On_Visual) AND feed copy per audience. Otherwise a single row.
        _tc = concept.get("targeting_copy")
        if isinstance(_tc, dict) and _tc:
            for _tgt in ("Prospecting", "Retargeting"):
                _v = _flatten_audience(_tc.get(_tgt))
                _r = dict(base_row)
                _r["Targeting"] = _tgt
                # ON-IMAGE (Text_On_Visual) — unique per audience
                if _v.get("creative_headline"):
                    _r["Headline_On_Creative"] = _v["creative_headline"]
                _r["Subhead_On_Creative"] = _v.get("creative_subhead") or _r.get("Subhead_On_Creative", "")
                # FEED copy — unique per audience. `or` (not .get default): the model
                # sometimes emits an EMPTY-STRING audience field, and "key exists but
                # blank" must fall back to the base copy, not overwrite it with "".
                _r["Primary_Text_Short"] = _v.get("body_short") or _r["Primary_Text_Short"]
                _r["Primary_Text_Long"] = _v.get("body_long") or _r["Primary_Text_Long"]
                _r["Headline"] = _v.get("headline") or _r["Headline"]
                _r["Headline_Short"] = _v.get("headline_short") or _r["Headline_Short"]
                _r["Description"] = _v.get("description") or _r["Description"]
                _sfx = _tgt[:4].lower()
                _r["asset_id"] = f"{base_row['asset_id']}_{_sfx}"
                _r["concept_tag"] = f"{base_row.get('concept_tag', '')}-{_sfx}"
                manifest_rows.append(_r)
        else:
            manifest_rows.append(base_row)

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
        _tc = c.get("targeting_copy") if isinstance(c.get("targeting_copy"), dict) else {}
        def _aud(_key, _field):
            # per-audience FEED field (case-insensitive keys), "" if not a Both concept.
            # Flattened so nested {feed:{…}} structures resolve too (Adrie 2026-07-27).
            _v = _flatten_audience(_tc.get(_key) or _tc.get(_key.lower()) or {})
            return _v.get(_field, "") if isinstance(_v, dict) else ""
        review_rows.append({
            "Visual_Style": c.get("visual_style", ""),
            "rank": c.get("rank", ""),
            "selected": "YES" if c.get("selected") else "NO",
            "score": c.get("score", ""),
            # On-image copy. Named Text_On_Visual to match Adrie's copy-spec docs
            # (her single on-creative field) and to disambiguate from the FEED
            # `Headline` below — reviewers cross-reference this CSV against her spec.
            # (The Figma MANIFEST keeps Headline_On_Creative/Subhead_On_Creative as
            # those are layer names the plugin fills — a machine handoff, not review.)
            "Text_On_Visual": c.get("creative_headline", c.get("headline", "")),
            "Text_On_Visual_Subhead": c.get("creative_subhead", ""),
            "Primary_Text_Short": c.get("body_short", c.get("body", "")),
            "Primary_Text_Long": c.get("body_long", ""),
            "Description": c.get("description", ""),
            "CTA": c.get("cta", ""),
            # Per-audience copy — populated only for Prospecting+Retargeting concepts so the
            # operator reviews BOTH audience versions at Gate 3. Each audience now has its OWN
            # on-visual copy (Text_On_Visual) AND feed copy (Adrie 2026-07-23).
            "Prospecting_Text_On_Visual": _aud("Prospecting", "creative_headline"),
            "Prospecting_Headline": _aud("Prospecting", "headline"),
            "Prospecting_Text_Short": _aud("Prospecting", "body_short"),
            "Prospecting_Text_Long": _aud("Prospecting", "body_long"),
            "Retargeting_Text_On_Visual": _aud("Retargeting", "creative_headline"),
            "Retargeting_Headline": _aud("Retargeting", "headline"),
            "Retargeting_Text_Short": _aud("Retargeting", "body_short"),
            "Retargeting_Text_Long": _aud("Retargeting", "body_long"),
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
    "claude-sonnet-5":   (3.0, 15.0),   # standard Sonnet tier — VERIFY vs actual Sonnet 5 pricing
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8":   (5.0, 25.0),
    "claude-haiku-4-5":  (1.0, 5.0),
}
_TOKEN_LOCK = threading.Lock()
# Per-image Gemini cost estimate. Image spend was previously INVISIBLE to the burn-rate
# counter and /admin/spend (they only priced text tokens) — runs that generated images
# under-reported real cost. Env-tunable when real Gemini pricing is confirmed.
try:
    _IMAGE_COST_USD = float(os.environ.get("ADAM_IMAGE_COST_USD", "0.13") or "0.13")
except ValueError:
    _IMAGE_COST_USD = 0.13


def _add_image_usage(sprint_id, count=1):
    """Accumulate generated-image count + estimated cost into token_usage.json so image
    runs show real spend. Thread-safe, best-effort — never breaks the pipeline."""
    if not sprint_id or count <= 0:
        return
    try:
        with _TOKEN_LOCK:
            path = RUNS_DIR / sprint_id / "token_usage.json"
            try:
                data = json.loads(path.read_text())
            except Exception:
                data = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "by_model": {}}
            data["images_generated"] = data.get("images_generated", 0) + int(count)
            data["image_cost_usd"] = round(data["images_generated"] * _IMAGE_COST_USD, 4)
            data["estimated_cost_usd"] = round(
                _estimate_cost(data.get("by_model", {}))
                + data["images_generated"] * _IMAGE_COST_USD, 4)
            path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


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
            data["estimated_cost_usd"] = round(
                _estimate_cost(data["by_model"])
                + data.get("images_generated", 0) * _IMAGE_COST_USD, 4)
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
