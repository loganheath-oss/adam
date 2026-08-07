"""ADAM's authority registry — which tasks the model may CREATE and which it
is demoted to PRESENTING.

Born 2026-07-30 (Logan): "the python can be restructured so that it's very
clear which tasks ADAM has authority to create and which tasks it is demoted
to just presenting." This file is that structure — the single source of truth
for the model's authority level on every task, at every gate and surface.

It is ENFORCED, not aspirational:
  * agent/orchestrator.py renders the AUTHORITY MAP section of the system
    prompt from this table (render_prompt_section) — a task cannot reach the
    agent unclassified.
  * docs/AUTHORITY.md is generated from this table (python3 authority.py) and
    the regression suite fails if it drifts.
  * The suite also asserts every PRESENT task names its Python source of truth
    and every CREATE/JUDGE task names its deterministic validators.

The levels (each is a CONTRACT, hardened by a real incident):

  PRESENT — zero creative authority. Python computes the fact; the model only
    formats it. A task is PRESENT-safe because the model RECEIVES the finished
    fact, not because it was told not to invent (2026-07-30: prompt rules
    alone failed live; handing the model `on_creative` + `pipeline_flags`
    fixed it on the next probe).
  EXPLAIN — authority over wording, never over facts. Every claim cites a tool
    result or flag; tool data supersedes anything said earlier in chat; "I
    need to check" is always a legal answer (2026-07-27 "by design" incident;
    2026-07-30 repeated-invented-flag incident).
  JUDGE — authority to score/rank/flag inside Python-defined criteria.
    Judgment is ADVISORY; enforcement is deterministic and fail-closed
    (2026-07-30: a failed review call was shipping legal-flagged copy until
    _deterministic_selection ran on every path).
  CREATE — real inventive authority. Schema enforces the shape, deterministic
    validators run afterward, telemetry watches drift ("prompt asks, Python
    verifies, telemetry watches").
  ACTION — no model authority at all: the tool executes a deterministic Python
    operation (state CAS, validated write). The model only decides WHEN to
    call it, and Python may refuse.

Everything not in this table is deterministic pipeline code — no model
involvement by definition.
"""
from __future__ import annotations

LEVELS: dict[str, str] = {
    "PRESENT": (
        "Zero creative authority. The fact arrives computed from the named "
        "source — quote it VERBATIM (full text, line breaks, emoji), never "
        "shorten, relabel, or recompute it. `pipeline_flags: {none: true}` is "
        "a positive fact: no violation exists and none may be mentioned."
    ),
    "EXPLAIN": (
        "Authority over wording only. Every claim must cite a tool result or "
        "flag; tool data supersedes earlier chat messages; when unsure say "
        "'I need to check' or log an issue — never assert 'by design'."
    ),
    "JUDGE": (
        "Score/rank/flag inside the given criteria. The judgment is advisory: "
        "deterministic enforcement (legal, caps, selection floor) runs after "
        "it and wins on any conflict."
    ),
    "CREATE": (
        "Invent freely INSIDE the fences: the output schema fixes the shape, "
        "deterministic validators (caps, legal blocklist, dedup, policy "
        "assertions) run on everything produced, and quality telemetry is "
        "recorded."
    ),
    "ACTION": (
        "The tool performs a deterministic, Python-validated operation. The "
        "model chooses when to invoke it; Python may refuse (state CAS, "
        "bounds checks) and the refusal is the final answer."
    ),
}

# surface, task, level, source (PRESENT/ACTION: the computing/validating Python),
# validators (CREATE/JUDGE: the deterministic fences), notes
TASKS: list[dict] = [
    # ── Gate 2 — Order + Refs Review ─────────────────────────────────────────
    {"surface": "gate_2", "task": "Show the order (driver, platform, targeting, styles, quantities, resolutions)",
     "level": "PRESENT", "source": "tool_get_sprint → order.json"},
    {"surface": "gate_2", "task": "Show the brief VERBATIM and COMPLETE",
     "level": "PRESENT", "source": "tool_get_sprint → order.json.brief"},
    {"surface": "gate_2", "task": "Show which reference docs loaded (names + sizes)",
     "level": "PRESENT", "source": "tool_get_references → context.json"},
    {"surface": "gate_2", "task": "Surface every intake warning (unfilled/placeholder brief, style with no Figma template) BEFORE asking for approval",
     "level": "PRESENT", "source": "tool_get_sprint → order.json.intake_warnings (computed by 00_intake.validate_payload)",
     "notes": "Quote each warning; never soften or omit one. An empty list means the order passed intake cleanly and no warning may be invented."},
    {"surface": "gate_2", "task": "Brief breakdown (themes, angles, constraints extracted for copy gen)",
     "level": "EXPLAIN", "validators": "json_schema on the breakdown call; raw brief always shown beside it"},
    # ── Gate 3 — Copy Review ─────────────────────────────────────────────────
    {"surface": "gate_3", "task": "Generate copy concepts (all fields, per-audience, per style)",
     "level": "CREATE",
     "validators": "_concept_schema structured output · _enforce_lengths · _scan_banned_terms (legal) "
                   "· _apply_cta_mix/_enforce_conditional_caps · near-dup + cross-sprint dedup "
                   "· _deterministic_selection · quality telemetry"},
    {"surface": "gate_3", "task": "Score and rank concepts; select top choices",
     "level": "JUDGE", "validators": "_deterministic_selection runs on EVERY path (fail-closed)"},
    {"surface": "gate_3", "task": "Campaign-level CD flags (monotony, tonal drift)",
     "level": "JUDGE", "validators": "advisory only — appended to review_notes, never auto-applied"},
    {"surface": "gate_3", "task": "Show every concept — selected AND rejected — all fields",
     "level": "PRESENT", "source": "tool_get_copy_concepts → copy_outputs + targeting_copy"},
    {"surface": "gate_3", "task": "Show the ON-CREATIVE copy (what prints on the template)",
     "level": "PRESENT", "source": "tool_get_copy_concepts → on_creative (+ on_creative_note)"},
    {"surface": "gate_3", "task": "Report legal/length violations",
     "level": "PRESENT", "source": "tool_get_copy_concepts → pipeline_flags (none:true = clean, full stop)"},
    {"surface": "gate_3", "task": "Counts: concepts generated / selected / flagged per style",
     "level": "PRESENT", "source": "tool_get_copy_concepts → style_summary"},
    {"surface": "gate_3", "task": "Narrate WHY a concept ranked where it did",
     "level": "EXPLAIN", "validators": "must quote score/rank/review_notes from the data"},
    # ── Gate 4 — Image Prompt Scan ───────────────────────────────────────────
    {"surface": "gate_4", "task": "Write Gemini image prompts (non-people styles)",
     "level": "CREATE",
     "validators": "style routing sets · no-AI-people policy assertion (blocked_ai_people_photo) "
                   "· template/size fields from registry data"},
    {"surface": "gate_4", "task": "Pick brand-library photos for people styles",
     "level": "JUDGE",
     "validators": "tag matching + in-sprint exclusion; PHOTO_LIBRARY_STYLES can NEVER emit "
                   "gemini_generate — library failure routes to human selection"},
    {"surface": "gate_4", "task": "Show every image prompt / photo pick IN FULL",
     "level": "PRESENT", "source": "tool_get_image_prompts → image_prompts.csv rows"},
    {"surface": "gate_4", "task": "Explain the visual direction reasoning",
     "level": "EXPLAIN", "validators": "cites the prompt rows and the order brief"},
    # ── Gate 5 — Assembly Review ─────────────────────────────────────────────
    {"surface": "gate_5", "task": "Show every manifest row (all copy + template + image columns)",
     "level": "PRESENT", "source": "tool_get_manifest → asset_manifest.csv"},
    {"surface": "gate_5", "task": "Show the image inventory",
     "level": "PRESENT", "source": "tool_get_sprint → recursive available_files / files_per_dir / file_total"},
    {"surface": "gate_5", "task": "Explain assembly problems the operator spots",
     "level": "EXPLAIN", "validators": "cites manifest rows/files; unknowns → log_issue"},
    # ── Gate 6 — Final QA ────────────────────────────────────────────────────
    {"surface": "gate_6", "task": "Complete deliverable inventory — every file, nothing elided",
     "level": "PRESENT", "source": "tool_get_sprint → file_total + files_per_dir + available_files"},
    {"surface": "gate_6", "task": "Delivery counts incl. Gate-5 vetoes honored",
     "level": "PRESENT", "source": "run_summary (delivered / pending_assembly / removed_at_gate_5)"},
    {"surface": "gate_6", "task": "QA narrative (what to double-check before shipping)",
     "level": "EXPLAIN", "validators": "grounded in run_summary + manifest data"},
    # ── Chat (cross-gate) ────────────────────────────────────────────────────
    {"surface": "chat", "task": "Answer 'why did X happen' / diagnostics",
     "level": "EXPLAIN",
     "validators": "diagnostic honesty: cite a file/flag/event or say 'I need to check'; "
                   "log_issue for anything unresolved"},
    {"surface": "chat", "task": "Approve a gate",
     "level": "ACTION", "source": "sprint_state.claim_gate (cross-process CAS; losers refused) → background task"},
    {"surface": "chat", "task": "Edit the order",
     "level": "ACTION", "source": "tool_edit_order (Python-validated fields + bounds)"},
    {"surface": "chat", "task": "Log an operator issue",
     "level": "ACTION", "source": "tool_log_issue → db.report_issue (visible in admin + Digest)"},
    {"surface": "chat", "task": "Apply institutional learnings to recommendations",
     "level": "EXPLAIN", "validators": "learnings.md quoted, not paraphrased into new rules"},
    {"surface": "chat", "task": "Ask-ADAM wiki answers (public helper)",
     "level": "EXPLAIN", "validators": "wiki-grounded; read-only toolset; sources surfaced"},
]

_SURFACE_TITLES = {
    "gate_2": "Gate 2 — Order + Refs Review",
    "gate_3": "Gate 3 — Copy Review",
    "gate_4": "Gate 4 — Image Prompt Scan",
    "gate_5": "Gate 5 — Assembly Review",
    "gate_6": "Gate 6 — Final QA",
    "chat": "Chat (any time)",
}


def render_prompt_section() -> str:
    """The AUTHORITY MAP section of the agent's system prompt — generated so a
    task cannot reach the agent without a declared authority level."""
    lines = [
        "# AUTHORITY MAP — what you may create vs. what you only present",
        "",
        "Every task below carries an authority level. The level is a CONTRACT:",
        "",
    ]
    for name, contract in LEVELS.items():
        lines.append(f"- {name}: {contract}")
    lines.append("")
    for surface, title in _SURFACE_TITLES.items():
        rows = [t for t in TASKS if t["surface"] == surface]
        if not rows:
            continue
        lines.append(f"## {title}")
        for t in rows:
            src = t.get("source")
            val = t.get("validators")
            tail = f" — source: {src}" if src else (f" — fences: {val}" if val else "")
            lines.append(f"- [{t['level']}] {t['task']}{tail}")
        lines.append("")
    lines.append(
        "If a task is not in this map, it has NO declared authority — treat it as "
        "PRESENT (show the data, invent nothing) and log_issue so engineering "
        "classifies it."
    )
    return "\n".join(lines)


def render_markdown() -> str:
    """docs/AUTHORITY.md — the human/InfoSec/handoff version."""
    lines = [
        "# ADAM Authority Map",
        "",
        "*Generated from `authority.py` — edit that file, then run "
        "`python3 authority.py`. The regression suite fails if this doc drifts.*",
        "",
        "Which tasks ADAM's model has authority to CREATE, and which it is "
        "demoted to PRESENTING Python-computed facts. Everything not listed is "
        "deterministic pipeline code with no model involvement.",
        "",
        "## The five authority levels",
        "",
    ]
    for name, contract in LEVELS.items():
        lines.append(f"**{name}** — {contract}")
        lines.append("")
    for surface, title in _SURFACE_TITLES.items():
        rows = [t for t in TASKS if t["surface"] == surface]
        if not rows:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Level | Task | Source of truth / fences |")
        lines.append("|---|---|---|")
        for t in rows:
            detail = t.get("source") or t.get("validators") or ""
            lines.append(f"| {t['level']} | {t['task']} | {detail} |")
        lines.append("")
    return "\n".join(lines)


def validate() -> list[str]:
    """Registry invariants — the suite calls this."""
    errors = []
    for t in TASKS:
        lvl = t.get("level")
        if lvl not in LEVELS:
            errors.append(f"unknown level {lvl!r}: {t.get('task')}")
        if t.get("surface") not in _SURFACE_TITLES:
            errors.append(f"unknown surface {t.get('surface')!r}: {t.get('task')}")
        if lvl in ("PRESENT", "ACTION") and not t.get("source"):
            errors.append(f"{lvl} task missing source: {t.get('task')}")
        if lvl in ("CREATE", "JUDGE", "EXPLAIN") and not (t.get("validators") or t.get("source")):
            errors.append(f"{lvl} task missing validators: {t.get('task')}")
    return errors


if __name__ == "__main__":
    from pathlib import Path
    errs = validate()
    if errs:
        raise SystemExit("registry invalid:\n" + "\n".join(f"  - {e}" for e in errs))
    out = Path(__file__).parent / "docs" / "AUTHORITY.md"
    out.write_text(render_markdown())
    print(f"wrote {out} ({len(TASKS)} tasks, {len(LEVELS)} levels)")
