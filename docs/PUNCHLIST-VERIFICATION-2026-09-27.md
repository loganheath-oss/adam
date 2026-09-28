# August punchlist — verified against code, 2026-09-27

Source: `ADAM Dashboard 08.26.xlsx` (Adrie's tracker, 9 tabs, read in full).

**Why this file exists.** The tracker marks 21 of 22 issues **Done** and, at the same
time, marks **all 53 acceptance criteria "No"** — zero verifiers, zero dates, every
Progress cell reading "0 of 2 met". Its own Dashboard tab reports "Issues open: 0"
four rows above "Criteria met: 0 of 53", and those are formulas, so the sheet is
accurately reporting that its two columns disagree. The Status column therefore
cannot be used as evidence of anything. This is the verification the sheet is
missing, done against the code rather than against the Status column.

Lee has asked for final QA with Haresh and Max. This is the file to hand them.

## Score

Twenty issues carry IDs (ADAM-001 … 020). Two rows have no ID: one is a Figma link
for a template image (no action), the other is the "a style assembles but fills
nothing" troubleshooting note, which is the only row the sheet leaves **In progress**
and which now lives in the designer guide.

| | Count | IDs |
|---|---|---|
| Verified addressed | 9 | 002, 004, 005, 007, 008\*, 009, 010, 014, 019 |
| Fixed 2026-09-27 | 4 | 001, 011, 015, 018 |
| Partly addressed | 2 | 006, 017 |
| Deliberately NOT built | 1 | 003 — see the warning below |
| Open | 4 | 012, 013, 016, 020 |

\* ADAM-008 is a chat tool, not the "editable field per ad row" the criterion words.

**Nothing in the spreadsheet itself has been updated.** All 53 acceptance criteria
still read "No" in the workbook, because that file is Adrie's and this record is the
evidence she would need to fill it in.

## Verified addressed

| ID | Evidence |
|---|---|
| ADAM-002 | `/admin/archive`, `archived.json` marker, nightly Postgres backup off-volume |
| ADAM-004 | `/sprints/{id}/retry` and `/sprints/{id}/resume` — resume re-runs only the failed stage |
| ADAM-005 | `sprint_state` writes atomically (temp + `os.replace`); torn-file recovery covered by `tests/copy_regression.py` |
| ADAM-007 | Mapping table is `docs/figma-naming-convention.md` (version-controlled, 2026-07-28). Missing layers fail loudly and name the field — `⚠ headline NOT filled — no layer matched [...]`, `⚠ cta NOT filled`, `⚠ No copy panel found`. Confirmed live over the Figma MCP 2026-09-27: sprint `2026-09-reddit-7f2a1b1591af` has real feed copy rendered into its boards. |
| ADAM-008 | `edit_copy` agent tool — Gate-3-gated, writes `copy_outputs.json`, logs a `copy_edited` decision |
| ADAM-009 | `_concept_has_placeholder_copy()` sets `placeholder_flag`; flagged concepts excluded from selection |
| ADAM-010 | `/sprints/{id}/copy-select` — state guard (`awaiting_gate_3` only), at-least-one-selected check, CTA-mix reapplication, event logged |
| ADAM-014 | Documented in `05-figma-plugin.md`: `findTemplatesRoot()` scans all pages, prefers the Template Library page |
| ADAM-019 | `learnings.md` on the `/data` volume, stated in `12-faq.md`, `/learnings` editor with save + event log |

**ADAM-008 carries a caveat.** The criterion says "Gate 3 exposes an editable field
per ad row." It is implemented as a **chat tool**, not a form field. Functionally it
closes the loop the Learnings tab called the top priority ("the human has judgment
but no controls"), but if someone checks the criterion literally, it does not match.

## Fixed today, in response to this review

| ID | What changed |
|---|---|
| ADAM-001 | The `volume` self-check fired at 80% with a bare percentage. Now fires at **70%** and names **how many sprints are older than `ARCHIVE_AFTER_DAYS`** and therefore eligible for archive — the criterion as written. `_disk_guard()` already covered "checked at intake" and "readable copy". |
| ADAM-011 | `16-fixing-errors.md` §9 now states that Bespoke is MANUAL by design and excluded from the defect count, and records the 8-of-9 false-alarm result from the 2026-08-21 isolation test. |
| ADAM-018 | `07-using-adam.md` now documents the ~5-assets-per-run recommendation. This existed **only inside the spreadsheet**; nothing in the tool enforces it, so it is on the person ordering. |

## Not addressed — real gaps

| ID | Missing |
|---|---|
| ADAM-003 | The Gate 4 guard does not exist. **See the warning below before building it.** Gate 5 per-style counts (rows with copy / images / exports) not found. |
| ADAM-006 | *(Correction: this was listed as unaddressed in the first pass because I searched UI code. The fix is in `agent/orchestrator.py`'s Gate 5 guidance — `ready_for_figma` rows are declared NORMAL, only a 0-row manifest is a defect, and "NEVER tell the user to wait and check back later — no such background completion exists" closes the third criterion. What is genuinely missing is a literal **Re-check** control; the agent re-reads by calling `get_manifest` again.)* |
| ADAM-015 | **Closed 2026-09-27.** `16-fixing-errors.md` now classifies every flag the plugin emits by severity glyph (`✗` real miss / `⚠` real warning / `↻` self-healed / `·` informational), extracted from `plugin/code.js`, and names which specific messages look alarming but are not. Includes that `✗ Library node` usually means an expired Figma token rather than a bad template, and that `⚠ row missing figma_node_id` is expected while image generation is off. |
| ADAM-016 | No intake cancel-reset path found. |
| ADAM-017 | Partly addressed. The known instances are patched in the agent prompt ("NEVER tell the user to wait and check back later", "Never say the copy can't be changed"), and a `WHAT YOU CANNOT DO` block exists — but that block scopes the **public wiki-only helper**, not the sprint-driving agent. There is no general rule stopping the sprint agent proposing an action it has no tool for. |
| ADAM-020 | The creative-range experiment appears never to have run. |

**ADAM-012 and ADAM-013** both require "renders on three consecutive runs". The
2026-08-21 isolation test cleared eight of nine flagged styles and left **Search Bar
with Talent Badge** as the one confirmed render failure. Three-consecutive-run
evidence cannot be produced from the repo; it needs live runs.

## ⚠ Do not implement ADAM-003 as worded

The criterion asks that "`generation_method: skip` with an empty prompt fails Gate 4
loudly". Built literally, that now fails **every image row in every run**, because an
empty prompt is the normal shape for two legitimate cases:

- the image-generation kill switch (2026-09-24) rewrites every Gemini-bound row to
  `needs_human_selection` with `prompt = ""`, and
- self-contained styles (Us vs Them, Pie Chart, Device UI, Platform UI, Meme, Social
  Media Profile, Talent Profile) ship `skip` with no prompt **by design** — the
  template carries its own imagery.

The actual ADAM-003 defect was rows reaching `pending_assembly` with **no route at
all**. Gate the check on "no `generation_method` resolved", never on "the prompt
string is empty". A matching warning sits beside `NON_GEMINI_METHODS` in
`pipeline/run_pipeline.py`.

## The Reddit tab is the live one

Thirteen items, all still marked "Not started". Current status:

- **Fixed and covered by tests** — Reddit generating a headline when only ~100-char
  body copy is wanted, and the stray description (`reddit caps: body_short is the
  ONLY feed field`); copy-only unusable and Reddit unselectable for it; image-only
  crashing at Gate 2; the `Button Label` / `loadFontAsync` error (house-font fallback
  added after a census found the wrong font on 42 pill layers across 14 board masters).
- **Probably fixed, unverifiable outside Figma** — the two "Multiple Template
  Sourcing errors" entries and the two "an error occurred while running this plugin"
  crashes. Reddit template resolution landed in plugin 2026.09.17 and per-board error
  isolation exists.
- **Partly fixed** — duplicate same-name same-size frames. The `countCopyLayers`
  tie-break picks the richer frame, so it is no longer a coin flip when they differ.
  Two identical frames still fall through to the name-based choice, and the duplicates
  are still in the Figma file.
- **Open** — 12 of 20 Reddit style thumbnails are blank. `web/public/style-previews/reddit/`
  was never created, so the picker falls back to the Meta previews and only styles
  whose names coincide with a Meta style get an image. Blocked on `FIGMA_ACCESS_TOKEN`.
