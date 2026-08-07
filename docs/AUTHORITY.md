# ADAM Authority Map

*Generated from `authority.py` — edit that file, then run `python3 authority.py`. The regression suite fails if this doc drifts.*

Which tasks ADAM's model has authority to CREATE, and which it is demoted to PRESENTING Python-computed facts. Everything not listed is deterministic pipeline code with no model involvement.

## The five authority levels

**PRESENT** — Zero creative authority. The fact arrives computed from the named source — quote it VERBATIM (full text, line breaks, emoji), never shorten, relabel, or recompute it. `pipeline_flags: {none: true}` is a positive fact: no violation exists and none may be mentioned.

**EXPLAIN** — Authority over wording only. Every claim must cite a tool result or flag; tool data supersedes earlier chat messages; when unsure say 'I need to check' or log an issue — never assert 'by design'.

**JUDGE** — Score/rank/flag inside the given criteria. The judgment is advisory: deterministic enforcement (legal, caps, selection floor) runs after it and wins on any conflict.

**CREATE** — Invent freely INSIDE the fences: the output schema fixes the shape, deterministic validators (caps, legal blocklist, dedup, policy assertions) run on everything produced, and quality telemetry is recorded.

**ACTION** — The tool performs a deterministic, Python-validated operation. The model chooses when to invoke it; Python may refuse (state CAS, bounds checks) and the refusal is the final answer.

## Gate 2 — Order + Refs Review

| Level | Task | Source of truth / fences |
|---|---|---|
| PRESENT | Show the order (driver, platform, targeting, styles, quantities, resolutions) | tool_get_sprint → order.json |
| PRESENT | Show the brief VERBATIM and COMPLETE | tool_get_sprint → order.json.brief |
| PRESENT | Show which reference docs loaded (names + sizes) | tool_get_references → context.json |
| PRESENT | Surface every intake warning (unfilled/placeholder brief, style with no Figma template) BEFORE asking for approval | tool_get_sprint → order.json.intake_warnings (computed by 00_intake.validate_payload) |
| EXPLAIN | Brief breakdown (themes, angles, constraints extracted for copy gen) | json_schema on the breakdown call; raw brief always shown beside it |

## Gate 3 — Copy Review

| Level | Task | Source of truth / fences |
|---|---|---|
| CREATE | Generate copy concepts (all fields, per-audience, per style) | _concept_schema structured output · _enforce_lengths · _scan_banned_terms (legal) · _apply_cta_mix/_enforce_conditional_caps · near-dup + cross-sprint dedup · _deterministic_selection · quality telemetry |
| JUDGE | Score and rank concepts; select top choices | _deterministic_selection runs on EVERY path (fail-closed) |
| JUDGE | Campaign-level CD flags (monotony, tonal drift) | advisory only — appended to review_notes, never auto-applied |
| PRESENT | Show every concept — selected AND rejected — all fields | tool_get_copy_concepts → copy_outputs + targeting_copy |
| PRESENT | Show the ON-CREATIVE copy (what prints on the template) | tool_get_copy_concepts → on_creative (+ on_creative_note) |
| PRESENT | Report legal/length violations | tool_get_copy_concepts → pipeline_flags (none:true = clean, full stop) |
| PRESENT | Counts: concepts generated / selected / flagged per style | tool_get_copy_concepts → style_summary |
| EXPLAIN | Narrate WHY a concept ranked where it did | must quote score/rank/review_notes from the data |

## Gate 4 — Image Prompt Scan

| Level | Task | Source of truth / fences |
|---|---|---|
| CREATE | Write Gemini image prompts (non-people styles) | style routing sets · no-AI-people policy assertion (blocked_ai_people_photo) · template/size fields from registry data |
| JUDGE | Pick brand-library photos for people styles | tag matching + in-sprint exclusion; PHOTO_LIBRARY_STYLES can NEVER emit gemini_generate — library failure routes to human selection |
| PRESENT | Show every image prompt / photo pick IN FULL | tool_get_image_prompts → image_prompts.csv rows |
| EXPLAIN | Explain the visual direction reasoning | cites the prompt rows and the order brief |

## Gate 5 — Assembly Review

| Level | Task | Source of truth / fences |
|---|---|---|
| PRESENT | Show every manifest row (all copy + template + image columns) | tool_get_manifest → asset_manifest.csv |
| PRESENT | Show the image inventory | tool_get_sprint → recursive available_files / files_per_dir / file_total |
| EXPLAIN | Explain assembly problems the operator spots | cites manifest rows/files; unknowns → log_issue |

## Gate 6 — Final QA

| Level | Task | Source of truth / fences |
|---|---|---|
| PRESENT | Complete deliverable inventory — every file, nothing elided | tool_get_sprint → file_total + files_per_dir + available_files |
| PRESENT | Delivery counts incl. Gate-5 vetoes honored | run_summary (delivered / pending_assembly / removed_at_gate_5) |
| EXPLAIN | QA narrative (what to double-check before shipping) | grounded in run_summary + manifest data |

## Chat (any time)

| Level | Task | Source of truth / fences |
|---|---|---|
| EXPLAIN | Answer 'why did X happen' / diagnostics | diagnostic honesty: cite a file/flag/event or say 'I need to check'; log_issue for anything unresolved |
| ACTION | Approve a gate | sprint_state.claim_gate (cross-process CAS; losers refused) → background task |
| ACTION | Edit the order | tool_edit_order (Python-validated fields + bounds) |
| ACTION | Log an operator issue | tool_log_issue → db.report_issue (visible in admin + Digest) |
| EXPLAIN | Apply institutional learnings to recommendations | learnings.md quoted, not paraphrased into new rules |
| EXPLAIN | Ask-ADAM wiki answers (public helper) | wiki-grounded; read-only toolset; sources surfaced |
