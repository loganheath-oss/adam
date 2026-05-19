# ADAM Pipeline — MindStudio Agent Specification

**Version:** 1.0 (alpha — no gateway integration)
**Last updated:** 2026-04-21
**Owner:** Logan Heath

## Purpose

This document specifies the MindStudio agent that orchestrates the ADAM creative pipeline. One agent, one run per ad creative order. Humans approve at 5 gates along the way. Final assets land in Google Drive for the team to pick up.

---

## Architecture overview

```
   Marketing                    MindStudio Agent                          External
      │                               │                                       │
      │── submits order form ────────►│                                       │
      │                               │                                       │
      │                          [Stage 00: Validate]                         │
      │                               │                                       │
      │                          [Stage 01: Load refs]◄──────────── Knowledge base
      │                               │                                       │
      │                          ╔═══════════════╗                            │
      │◄────────── email ────────║ GATE 2: Confirm ║─── Slack notification ──►│
      │─────────── approve ─────►║    order      ║                            │
      │                          ╚═══════════════╝                            │
      │                               │                                       │
      │                          [Stage 02a: Generate 6x copy]──────► Anthropic API
      │                          [Stage 02b: Self-review + rank]────► Anthropic API
      │                               │                                       │
      │                          ╔═══════════════╗                            │
      │◄────────── email ────────║ GATE 3: Review ║                           │
      │───── edit + approve ────►║    copy       ║                            │
      │                          ╚═══════════════╝                            │
      │                               │                                       │
      │                          [Stage 03: Image prompts]──────────► Anthropic API
      │                               │                                       │
      │                          ╔═══════════════╗                            │
      │◄────────── email ────────║ GATE 4: Review ║                           │
      │─────────── approve ─────►║   prompts     ║                            │
      │                          ╚═══════════════╝                            │
      │                               │                                       │
      │                          [Stage 04: Generate images]────────► Gemini API
      │                          [Stage 04b: Vision review]─────────► Anthropic API
      │                               │                                       │
      │                          ╔═══════════════╗                            │
      │◄────────── email ────────║ GATE 5: Review ║                           │
      │───── approve/reject ────►║   images      ║                            │
      │                          ╚═══════════════╝                            │
      │                               │                                       │
      │                          [Manual: Figma assembly ─────────────────────► Figma Desktop
      │                           Logan downloads, assembles,                  (plugin)
      │                           re-uploads final PNGs]                       │
      │                               │                                       │
      │                          [Stage 06: Deliver]─────────────────► Google Drive
      │                                                              ─► Slack
      │                               │
      │                          ╔═══════════════╗
      │◄────────── email ────────║ GATE 6: Final ║
      │─────────── sign-off ────►║    QA         ║
      │                          ╚═══════════════╝
      │                               │
      ▼                            [Complete]
   Done
```

---

## Agent state schema

MindStudio carries this state across every step. Variables in `{braces}` are substituted into prompts at runtime.

```yaml
# Set at Stage 00
sprint_id: "2026-04-meta-a3f2"
submitted_at: "2026-04-21T14:30:00Z"
driver: "Logan Heath"
delivery_date: "2026-04-25"
targeting: "Prospecting"          # Prospecting | Retargeting | Both
deliverable: "images-copy"         # images-copy | images-only | copy-only
platform: "Meta"
batches:
  - format: "Static Feed"
    quantity: 1
    visual_styles: ["Lifestyle Photo"]
    resolutions: [{size: "1440x1440", ratio: "1:1"}]
brief: "Showcase how Upwork helps SMBs hire fast..."

# Set at Stage 01
refs_loaded: true
refs_summary: "11 reference documents loaded"

# Set at Stage 02
copy_concepts_raw: [...]           # 6 per style — before review
copy_concepts_reviewed: [...]      # 6 per style — with scores + ranks
copy_selected: [...]               # top 3 per style (gate 3 approved)

# Set at Stage 03
image_prompts: [...]               # one per selected copy concept per resolution

# Set at Stage 04
generated_images: [...]            # image URLs + asset_ids
image_review_results: [...]        # per-image quality scores

# Set after manual Figma step
final_exports: [...]               # URLs of assembled final PNGs

# Set at Stage 06
drive_folder_url: "https://drive.google.com/drive/folders/..."
manifest_url: "https://drive.google.com/file/d/..."
```

---

## Stage-by-stage specification

### Stage 00 — Order Intake (Trigger + Validation)

**Node type:** Form trigger → Data transform

**Form fields** (recreate these in MindStudio's form builder):
- `driver` (text, required) — who's submitting
- `delivery_date` (date, required) — YYYY-MM-DD
- `targeting` (select, required) — Prospecting / Retargeting / Prospecting and Retargeting
- `deliverable` (select, required) — images-copy / images-only / copy-only
- `platform` (select, required) — Meta / LinkedIn / Reddit / YouTube / Google / 3rd Party
- `format` (select, required, options depend on platform) — Static Feed, Stories, etc.
- `visual_styles` (multi-select, required) — from 24-style list; scope alpha to the 3 confirmed
- `style_quantities` (number per selected style, required)
- `resolutions` (multi-select, required) — auto-populated from platform+format
- `brief` (long text, optional) — freeform creative direction
- `audience` (text, conditional on targeting = "Both")
- `carousel` (boolean) + `carousel_slides` (2-10, conditional)

**Validation rules** (same as `00_intake.py:66-150`):
- All required fields present
- `delivery_date` matches `YYYY-MM-DD`
- `targeting` is one of the 3 allowed values
- `deliverable` is one of the 3 allowed values
- `platform` is in the allowed set
- All `visual_styles` are in the allowed set
- At least one resolution selected
- `quantity` is a positive integer
- `audience` is required when `targeting = "Prospecting and Retargeting"`

**Sprint ID generation** (MindStudio code block or data transform):
```
sprint_id = {{year_month}}-{{platform_slug}}-{{random_4_char_hex}}
# Example: 2026-04-meta-a3f2
```

**Outputs to state:** all form fields + `sprint_id` + `submitted_at` timestamp

---

### Stage 01 — Load References

**Node type:** Knowledge base lookup (MindStudio native)

**Setup requirement:** Pre-upload these files to MindStudio's knowledge base, one time:
1. `brand_voice.txt` — Upwork brand voice & tone
2. `writing_style.txt` — writing style guide
3. `compliance.txt` — legal rules
4. `copy_playbook.txt` — category framework
5. `approved_claims.txt` — verified stats
6. `smb_copy_bank.txt` — approved headlines
7. `keyword_research.txt` — trending categories
8. `copy_style_rules.txt` — per-style copy rules (24 styles)
9. `image_style_rules.txt` — per-style image rules (24 styles)
10. `prospecting_examples.txt` — real prospecting copy
11. `retargeting_examples.txt` — real retargeting copy
12. `performance_data.txt` — KOTH top 8 performance data
13. `brandon_template_rules.txt` — template specs from Brandon

**What this stage does:** Injects all relevant reference documents into the conversation context so downstream LLM calls have access to them. MindStudio handles this natively via knowledge base retrieval.

**Outputs to state:** `refs_loaded: true`

---

### GATE 2 — Order + Refs Confirmation

**Node type:** Human approval step with email/Slack notification

**What the reviewer sees** (email template):
```
Subject: [ADAM] Sprint {sprint_id} — confirm order + refs

A new order is ready for your review.

ORDER SUMMARY
• Sprint: {sprint_id}
• Driver: {driver}
• Platform: {platform} / {format}
• Targeting: {targeting}
• Delivery: {delivery_date}
• Styles: {visual_styles}
• Resolutions: {resolutions}
• Brief: {brief}

REFERENCE DOCUMENTS
• 13 documents loaded from knowledge base
• Priority: order brief overrides standing reference docs

[ APPROVE ]   [ EDIT ORDER ]   [ REJECT ]

No API credits spent yet — this is the last free checkpoint.
```

**Approval actions:**
- Approve → continue to Stage 02
- Edit Order → reopen form pre-filled with current values
- Reject → stop pipeline, mark sprint cancelled

---

### Stage 02 — Copy Generation + Self-Review

This is two LLM calls in sequence, per visual style.

#### Stage 02a — Generate 6 concepts

**Node type:** LLM call (Claude Sonnet 4.6)

**System prompt:** See `PROMPTS.md` → `COPY_GEN_SYSTEM`

**User prompt:** See `PROMPTS.md` → `COPY_GEN_USER` — uses state variables `{brief}`, `{platform}`, `{format}`, `{targeting}`, `{visual_style}`, and loads the relevant style rules from the knowledge base.

**Output format:** JSON array of 6 concept objects with `headline`, `body_short`, `body_long`, `description`, `cta`, `concept_tag`.

**Iterate:** For each visual_style in the order, call this once with quantity=6.

**Outputs to state:** `copy_concepts_raw` (array of 6 per style)

#### Stage 02b — Self-review and rank

**Node type:** LLM call (Claude Sonnet 4.6)

**System prompt:** See `PROMPTS.md` → `COPY_REVIEW_SYSTEM`

**User prompt:** See `PROMPTS.md` → `COPY_REVIEW_USER` — takes the 6 concepts and returns them ranked 1-6 with scores and `selected: YES/NO` (top 3 = YES).

**Output format:** JSON array with the original fields plus `rank`, `score`, `selected`, `review_notes`.

**Outputs to state:** `copy_concepts_reviewed` (6 per style, ranked)

---

### GATE 3 — Copy Approval

**Node type:** Human approval with table preview

**What the reviewer sees:**
- Spreadsheet view of all concepts (6 per style × N styles)
- Columns: `rank`, `selected`, `score`, `headline`, `body_short`, `cta`, `review_notes`
- `selected` is editable — reviewer can flip YES/NO to override the AI's picks
- Approve button finalizes the selection

**Approval actions:**
- Approve → continue with whatever is marked `selected: YES`
- Edit → modify headlines/body/CTA inline, then approve
- Reject all → loop back to Stage 02 with feedback

**Outputs to state:** `copy_selected` (the YES-marked concepts after human edits)

---

### Stage 03 — Image Prompt Generation

**Node type:** LLM call (Claude Sonnet 4.6) + routing logic

**Routing rule** (based on visual_style):
- **Lifestyle Photo** → `generation_method: "library"` — no Gemini prompt needed. Human picks from Brandon's Figma photo library during assembly.
- **Photo with Text** → `generation_method: "library"` — same.
- **Testimonial** → `generation_method: "library"` — same.
- **Text Only, Chat Bubble, Notification, etc.** (abstract/UI styles) → `generation_method: "generate"` — build a Gemini background prompt.

**Note:** Per Brian's rule, no AI-generated photography. Photo styles route to Brandon's library. Only non-photo styles generate with Gemini.

**System prompt:** See `PROMPTS.md` → `IMAGE_PROMPT_SYSTEM`

**User prompt:** See `PROMPTS.md` → `IMAGE_PROMPT_USER`

**Output format:** CSV-like array, one row per image to generate:
```
asset_id, visual_style, resolution, linked_copy_asset_id, generation_method, gemini_prompt, negative_prompt
```

**Outputs to state:** `image_prompts`

---

### GATE 4 — Image Prompt Review

**Node type:** Human approval with table preview

**What the reviewer sees:**
- Table of all image prompts
- `generation_method` column shows "library" or "generate"
- For "generate" rows, `gemini_prompt` is editable
- For "library" rows, note says "Human selects from Brandon's photo library during assembly"

**Approval actions:**
- Approve → continue to Stage 04
- Edit prompts → save + approve
- Reject → loop back to Stage 03

---

### Stage 04 — Image Generation + Vision Review

Two-step inner loop per image: generate → review → retry if failed.

#### Stage 04a — Generate with Gemini

**Node type:** HTTP call to Gemini API (or MindStudio's Gemini node if they have one)

**For rows with `generation_method = "generate"`:**
- POST to Gemini Imagen 4 or Nano Banana Pro
- Pass `gemini_prompt` + `negative_prompt`
- Aspect ratio from the row
- Receive PNG bytes

**For rows with `generation_method = "library"`:**
- Skip — assembly step handles photo selection

**Outputs to state:** `generated_images` (array of {asset_id, image_url or image_base64})

#### Stage 04b — Vision review

**Node type:** LLM call (Claude Sonnet 4.6 with vision)

**System prompt:** See `PROMPTS.md` → `IMAGE_REVIEW_SYSTEM`

**User prompt:** Attach the generated image, ask Claude to score on:
- Quality (1-10)
- Person/subject clarity (if applicable)
- Composition fit for the visual style
- Overall pass/fail

**Retry logic:**
- If score < 7 and attempts < 3 → adjust prompt, regenerate
- If attempts = 3 → flag as failed, continue

**Outputs to state:** `image_review_results` (array with scores + pass/fail)

---

### GATE 5 — Image + Assembly Review

**Node type:** Human approval with image gallery + external action prompt

**What the reviewer sees:**
- Gallery of all generated images with their scores
- For "library" style rows: placeholder noting "Photo library asset required during assembly"
- Action required: download images, run Figma plugin for assembly, upload final PNGs

**Manual step instructions shown in the UI:**
```
MANUAL ASSEMBLY STEP
1. Click [ Download Images ] to get a zip of all generated PNGs
2. Open Figma → "Paid Acquisition 2026" file
3. Right-click canvas → Plugins → Development → Upwork Pipeline Assembly
4. Load the manifest: {download_manifest_url}
5. Select the downloaded images
6. For "library" style rows, select the matching photo from Brandon's library
7. Click "Assemble All Assets"
8. Export the final PNGs from Figma
9. Upload the final PNGs back here: [ Upload Final PNGs ]
```

**Approval actions:**
- Upload final PNGs → continue to Stage 06
- Regenerate specific images → loop back to Stage 04 for those asset_ids only
- Reject all → return to Stage 03

**Outputs to state:** `final_exports` (array of uploaded final PNGs)

---

### Stage 06 — Delivery

**Node type:** MindStudio Google Drive integration + Slack webhook

**Actions:**
1. **Create Drive folder structure:**
   - `/Upwork/Sprints/{sprint_id}/Review-Queue/`
   - Subfolder per platform: `/Meta/`, `/LinkedIn/`, etc.

2. **Upload final PNGs** to appropriate platform subfolder

3. **Build `asset_manifest.csv`** with columns:
   ```
   asset_id, sprint_id, platform, format, visual_style, resolution,
   headline, body_short, body_long, cta, concept_tag,
   drive_file_url, generated_at
   ```
   Upload to the sprint root folder.

4. **Build `run_summary.json`** with sprint totals. Upload to root folder.

5. **Send Slack notification** to `#paid-acquisition-pipeline`:
   ```
   ✅ Review Queue Ready
   Sprint: {sprint_id}
   Driver: {driver}
   Platform: {platform}
   Delivery: {delivery_date}
   Assets: {uploaded}/{total} uploaded
   Review: {drive_folder_url}
   ```

**Outputs to state:** `drive_folder_url`, `manifest_url`

---

### GATE 6 — Final QA

**Node type:** Human approval

**What the reviewer sees:**
- Link to Drive review folder
- Full manifest preview
- Run summary (total assets, any failures)
- Final sign-off button

**Approval actions:**
- Ship it → mark sprint complete
- Flag issue → reopens with note, returns to the relevant stage

---

## External integrations required

| Integration | Used in | Setup required |
|---|---|---|
| Anthropic API | Stages 02, 03, 04b | API key in MindStudio secrets |
| Gemini API | Stage 04a | API key in MindStudio secrets |
| Google Drive | Stage 06, reference docs | OAuth connect `logan@storysellers.co` or service account |
| Slack | Stage 06 | Incoming webhook URL for `#paid-acquisition-pipeline` |
| Figma | Manual assembly step | Existing plugin works as-is — Logan runs it locally |

---

## Assumptions and open questions

These are assumptions I made building the spec. Validate each before going live.

| # | Assumption | How to validate |
|---|---|---|
| 1 | MindStudio supports pausing a workflow for a human approval gate (minutes to days) and resuming it with state intact | Test: start a workflow, pause at gate, close browser, return 24hr later, verify it resumes |
| 2 | MindStudio's form builder can produce conditional fields (e.g., `carousel_slides` only appears when `carousel = true`) | Check the form builder UI |
| 3 | MindStudio can attach generated images to a follow-up LLM vision call (Stage 04b) | Check vision node capabilities |
| 4 | MindStudio's native LLM node supports system prompts + user prompts separately | Check LLM node config |
| 5 | MindStudio can call arbitrary HTTP endpoints (for Gemini API if no native node) | Check HTTP/webhook node availability |
| 6 | MindStudio's Google Drive integration supports folder creation + file upload, not just read | Check the integration docs |
| 7 | 13 reference docs can be pre-loaded to the knowledge base and retrieved per-run | Test knowledge base retrieval with your actual files |

---

## Scope for first build (alpha)

Keep the first build tight:

- **Only 3 visual styles:** Lifestyle Photo, Photo with Text, Testimonial
- **Only Meta platform:** skip LinkedIn/Reddit/etc. until Meta end-to-end works
- **Only 1:1 and 4:5 resolutions:** skip 9:16 stories for now
- **Skip carousels:** quantity = 1 only
- **Direct Anthropic/Gemini API:** no gateway integration yet

Once Meta end-to-end runs clean, expand to other platforms, then other styles, then gateway migration.
