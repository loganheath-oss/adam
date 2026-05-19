# ADAM Pipeline — MindStudio Setup Guide

**Purpose:** Step-by-step walkthrough to build the agent in MindStudio.
**Prerequisite:** Read `AGENT_SPEC.md` and `PROMPTS.md` first.
**Estimated time:** 4-8 hours for the first build, depending on MindStudio familiarity.

---

## Phase 0 — Before you start

### 0.1 Gather credentials

You need API keys for these services. Collect them now, save them somewhere secure (1Password, etc.). You'll paste them into MindStudio's secrets in Phase 4.

| Service | Key format | Where to get it |
|---|---|---|
| Anthropic API | `sk-ant-...` | console.anthropic.com → API Keys → Create |
| Google Gemini API | `AIza...` | aistudio.google.com → Get API key |
| Slack webhook | `https://hooks.slack.com/services/...` | Slack admin → App Directory → Incoming Webhooks → Add to `#paid-acquisition-pipeline` |
| Google Drive | OAuth connection | MindStudio's native Google Drive integration — connect with `logan@storysellers.co` |

### 0.2 Pre-stage reference documents

Before building the agent, upload these 13 files to MindStudio's knowledge base (once — they're reused every run):

From `~/Documents/upwork-creative-pipeline/refs/`:
1. `Claude * Upwork Brand Tone of Voice for Paid Ad copy .txt` → rename `brand_voice.txt`
2. `Upwork Writing Style Guide Audit - 2025 .txt` → rename `writing_style.txt`
3. `Revised Legal Guidance Content Guidelines .txt` → rename `compliance.txt`
4. `Claude Meta Ad_Copy_Mini_Playbook .txt` → rename `copy_playbook.txt`
5. `Copy of Marketing claims III .txt` → rename `approved_claims.txt`
6. `SMB Copy Bank_Phase 1_Final .txt` → rename `smb_copy_bank.txt`
7. `New : Trending Subcategory Keyword Research .txt` → rename `keyword_research.txt`
8. `visual_style_copy_rules.txt` → keep as-is
9. `visual_style_image_rules.txt` → keep as-is
10. `Prospecting ad copy examples Updated 2026 .txt` → rename `prospecting_examples.txt`
11. `Retargeting Ad copy examples Updated 2026 .txt` → rename `retargeting_examples.txt`
12. `koth top 8 static styles with examples.txt` → rename `performance_data.txt`
13. `brandon_template_rules.txt` → keep as-is

In MindStudio:
- Create a knowledge base collection named `adam-refs-v1`
- Upload all 13 files
- Verify retrieval works: query `brand voice` and confirm it returns the brand voice doc
- Note the knowledge base ID — you'll reference it in LLM nodes

---

## Phase 1 — Create the agent shell

### 1.1 Create a new agent

1. Click **Create Agent** (or whatever the equivalent is)
2. Name: `ADAM Creative Pipeline — Alpha`
3. Description: `Generates paid acquisition ad copy + images for Upwork sprints. 6 human-approval gates. Outputs to Google Drive review queue.`
4. Choose trigger type: **Form** (if available) or **Webhook**

### 1.2 Configure the agent settings

- Timeout per step: at least **10 minutes** (Claude calls can take 30-60 seconds; give margin)
- Max workflow duration: **72 hours** (gates may wait overnight)
- State persistence: **Enabled** — required so approval gates work across sessions

---

## Phase 2 — Build the order form (Stage 00)

### 2.1 Form fields

Open the form builder. Add these fields in order:

| Field name | Type | Required | Options / Validation |
|---|---|---|---|
| `driver` | Text | ✓ | Min 2 chars |
| `delivery_date` | Date | ✓ | Format YYYY-MM-DD |
| `targeting` | Select | ✓ | Prospecting / Retargeting / Prospecting and Retargeting |
| `deliverable` | Select | ✓ | images-copy / images-only / copy-only |
| `platform` | Select | ✓ | Meta / LinkedIn / Reddit / YouTube / Google / 3rd Party |
| `format` | Select | ✓ | Depends on platform — see below |
| `visual_styles` | Multi-select | ✓ | Lifestyle Photo / Photo with Text / Testimonial (scope alpha to these 3) |
| `style_quantities` | Number (per style) | ✓ | Default 1, min 1, max 10 |
| `resolutions` | Multi-select | ✓ | Depends on platform+format |
| `brief` | Long text | — | Optional, 1000 char max |
| `audience` | Text | Conditional | Required only when targeting = "Prospecting and Retargeting" |
| `carousel` | Toggle | — | Defaults false |
| `carousel_slides` | Number | Conditional | Required only when carousel = true, 2-10 |

### 2.2 Platform → format mapping

If MindStudio supports conditional select options, wire these up:

- **Meta:** Static Feed, Stories, Reels, Carousel
- **LinkedIn:** Single Image, Carousel, Text Ad
- **Reddit:** Image, Carousel
- **YouTube:** Pre-Roll, Discovery
- **Google:** Display, Performance Max, Responsive Search
- **3rd Party / Affiliate:** General

### 2.3 Resolution mapping

Each platform+format combo has a set of valid resolutions. Start simple — for Meta Static Feed, expose only `1440x1440 (1:1)` and `1440x1800 (4:5)`. You can add more later.

See `configs/upwork_config.json` → `channel_specs` for the full list.

### 2.4 Validation step (after form submit)

Add a **data transform** or **code** node immediately after the form trigger. This runs the same validation as `00_intake.py:66-150`.

**Pseudocode** (translate to MindStudio's scripting syntax):
```javascript
const errors = [];
if (!isValidDate(delivery_date)) errors.push("delivery_date must be YYYY-MM-DD");
if (!VALID_TARGETING.includes(targeting)) errors.push("targeting invalid");
// ... etc

if (errors.length > 0) {
  return { success: false, errors };
}

// Generate sprint_id
const date = new Date();
const year_month = date.toISOString().substring(0, 7);  // "2026-04"
const platform_slug = platform.toLowerCase().replace(/\s+\/\s+/g, "-").replace(/\s+/g, "-");
const uid = crypto.randomBytes(2).toString("hex");
const sprint_id = `${year_month}-${platform_slug}-${uid}`;

return { success: true, sprint_id, submitted_at: new Date().toISOString() };
```

Store `sprint_id` and `submitted_at` in state.

---

## Phase 3 — Wire the workflow stages

For each stage below, add a node of the specified type, configure its inputs/prompts from `PROMPTS.md`, and connect it to the next node.

### 3.1 Stage 01 — Load References

**Node type:** Knowledge base retrieval (MindStudio native)
**Config:**
- Collection: `adam-refs-v1`
- Retrieval mode: **Full context** (we want all 13 docs available, not just top-K)
- Output variables: set each doc as a named variable accessible to later nodes

If MindStudio doesn't support loading all docs as static context, use their retrieval mode and query each one by name (`"brand_voice"`, `"writing_style"`, etc.) to pull them into state.

### 3.2 Gate 2 — Order + Refs Confirmation

**Node type:** Human approval step
**Config:**
- Notification: email to `{{driver}}` + Slack to `#paid-acquisition-pipeline`
- Email body: use the template in `AGENT_SPEC.md` → Gate 2
- Actions: Approve / Edit / Reject
- On Approve → continue
- On Edit → loop back to form (pre-filled)
- On Reject → end workflow, mark cancelled

### 3.3 Stage 02a — Copy Generation

**Node type:** LLM call (Claude Sonnet 4.6)
**Config:**
- System prompt: from `PROMPTS.md` → Stage 02a system
- User prompt: from `PROMPTS.md` → Stage 02a user
- Max tokens: 1500
- Temperature: 0.7
- **Iteration:** loop over `visual_styles` — one call per style
- Output parsing: JSON array → store as `copy_concepts_raw` (array per style)

**Prompt caching:** If MindStudio exposes Anthropic's `cache_control` feature, mark the reference docs section as cacheable. This saves ~90% on input costs since the refs are identical across calls.

### 3.4 Stage 02b — Copy Review

**Node type:** Data transform → LLM call
**Config:**
- Data transform: build `{{concepts_text}}` — format the 6 concepts as numbered blocks (see `PROMPTS.md` → "How to build {{concepts_text}}")
- LLM call: from `PROMPTS.md` → Stage 02b
- Output parsing: merge rankings back into concept objects, set `rank`, `selected`, `score`, `review_notes`
- Store as `copy_concepts_reviewed`

### 3.5 Gate 3 — Copy Approval

**Node type:** Human approval with table preview
**Config:**
- Display: spreadsheet view of `copy_concepts_reviewed`
- Columns: rank, selected, score, headline, body_short, cta, review_notes
- Editable: `selected` column (toggle YES/NO), headline / body / CTA text fields
- On Approve → capture edited state as `copy_selected`
- On Reject all → loop back to Stage 02a with feedback

### 3.6 Stage 03 — Image Prompt Generation

**Node type:** Data transform (no LLM)
**Config:**
- Input: `copy_selected` array
- For each concept × each resolution in its style:
  - Apply routing logic from `PROMPTS.md` → Stage 03 routing
  - Build prompt record with asset_id, generation_method, gemini_prompt, negative_prompt
- Output: `image_prompts` array

### 3.7 Gate 4 — Image Prompt Review

**Node type:** Human approval with table preview
**Config:**
- Display: `image_prompts` table
- Editable: `gemini_prompt` column (for generate-mode rows)
- On Approve → continue
- On Reject → loop back to Stage 03

### 3.8 Stage 04a — Image Generation

**Node type:** HTTP call (Gemini API) — iterate per row
**Config:**
- Filter rows where `generation_method = "generate"` (skip `library` rows — those handled in assembly)
- For each row:
  - POST to `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent`
  - Or use MindStudio's native image generation node if available
  - Body: `{ "contents": [{"parts": [{"text": prompt + "\n\nAvoid: " + negative_prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]} }`
  - Parse base64 image from response
- Store images in MindStudio's file storage with key `{asset_id}.png`
- Update `generated_images` array with image URLs/IDs

### 3.9 Stage 04b — Image Vision Review

**Node type:** LLM call (Claude Sonnet 4.6 with vision)
**Config:**
- Attach: the generated image for the current row
- System prompt + user prompt: from `PROMPTS.md` → Stage 04b
- Pick `{{image_category}}` based on visual_style (see PROMPTS.md criteria lookup)
- Max tokens: 300
- Temperature: 0.2
- Output parsing: JSON object with score/passed/notes/fix

**Retry branching:**
```
IF score < 7 AND attempts < 3:
  Set adjusted_prompt = original_prompt + "\n\nCRITICAL FIX: " + fix
  Loop back to Stage 04a for this asset_id only
  Increment attempts

ELSE:
  Mark complete, move to next image
```

### 3.10 Gate 5 — Image + Assembly Review

**Node type:** Human approval with image gallery + file upload
**Config:**
- Display: gallery of all generated images + library-pending placeholders
- Show manual assembly instructions (see `AGENT_SPEC.md` → Gate 5)
- File upload field: accept multiple final PNGs
- On Upload → store files, capture URLs into `final_exports`
- On Regenerate specific images → branch back to Stage 04a for those asset_ids
- On Approve → continue to Stage 06

### 3.11 Stage 06 — Delivery

**Node type:** MindStudio Google Drive integration + HTTP call for Slack

**Drive actions** (sequential):
1. Create folder: `/Upwork/Sprints/{{sprint_id}}/Review-Queue/` — use MindStudio's native folder-create action
2. Create platform subfolder: `/Review-Queue/{{platform_slug}}/`
3. For each `final_export`: upload PNG to platform subfolder
4. Build `asset_manifest.csv` in a data transform node (columns in `AGENT_SPEC.md` → Stage 06)
5. Upload manifest to sprint root folder
6. Build `run_summary.json`, upload to sprint root folder

**Slack action:**
- HTTP POST to `SLACK_WEBHOOK_URL` with Block Kit payload (template in `AGENT_SPEC.md` → Stage 06)

### 3.12 Gate 6 — Final QA

**Node type:** Human approval
**Config:**
- Display: link to Drive folder + manifest preview + run summary
- Actions: Ship it / Flag issue
- On Ship → mark `workflow_status: complete`
- On Flag → capture note, return to relevant stage

---

## Phase 4 — Configure secrets

In MindStudio's secrets / environment variables section, add:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GEMINI_API_KEY` | `AIza...` |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/...` |

Reference these from LLM and HTTP nodes via MindStudio's secret interpolation syntax (likely `{{secrets.ANTHROPIC_API_KEY}}` or similar).

---

## Phase 5 — Test the workflow

Test incrementally. Don't run end-to-end until each stage passes in isolation.

### 5.1 Smoke test: Stages 00-01 only

1. Submit a minimal test order (1 style, 1 resolution, Meta)
2. Verify: `sprint_id` generates, refs load, Gate 2 email arrives
3. Approve Gate 2
4. Check: workflow pauses at Stage 02 (before running it)
5. Manually cancel — this is just wiring verification

### 5.2 Copy test: Stages 00-03

1. Submit the same test order
2. Let it run through Stage 02a + 02b
3. Check: 6 concepts generated per style, ranked correctly at Gate 3
4. Approve Gate 3
5. Check: `image_prompts` table at Gate 4 looks correct
6. Cancel before running Stage 04 (save image gen credits)

### 5.3 Image test: Stages 00-05 (library styles only)

1. Submit test order with `Lifestyle Photo` only (library style → no Gemini calls)
2. Run through to Gate 5
3. Check: at Gate 5, the UI shows placeholders with "select from library during assembly" notes
4. Manually run the Figma plugin locally to assemble the final assets
5. Upload the final PNGs to Gate 5
6. Let Stage 06 + Gate 6 run
7. Verify: files land in Drive, Slack notification fires

### 5.4 Full test: Stages 00-06 (mixed styles)

1. Submit order with `Testimonial` + `Text Only` (mix of library + generate)
2. Full end-to-end run
3. Verify every stage produces correct output

---

## Phase 6 — Known limitations (alpha)

Things that won't work in this alpha build. Document them so expectations are clear:

| Limitation | Why | Workaround | Fix in later phase |
|---|---|---|---|
| Figma assembly is manual | Plugin must run in Figma desktop | Logan runs plugin between Gates 5 and 6 | Rewrite plugin against Figma REST API (6-8 weeks of work) |
| No LLM Gateway routing | Haresh's team needs to wire this | Direct API calls — document for compliance team | Phase 2 retrofit |
| No prompt caching visibility | Depends on MindStudio exposing `cache_control` | Accept ~$1.50 per sprint | Evaluate after first 10 runs |
| Limited to 3 visual styles | Only 3 templates exist | Users pick from available 3 | Expand as Brandon builds templates |
| Only Meta platform | Scope constraint | Other platforms show "coming soon" | Add LinkedIn next |
| No retry queue for gate reviewers | If reviewer is OOO, sprint stalls | Add backup reviewer | Ravi decides policy |

---

## Phase 7 — Troubleshooting

### "LLM call times out"
- Default MindStudio timeout may be 30s. Copy generation with full refs context can take 45-90s.
- Fix: increase node timeout to 120s.

### "JSON parse error on copy output"
- Claude occasionally wraps JSON in markdown code fences.
- Fix: add a post-processing step that strips ```json and ``` before parsing.

### "Gate approval doesn't persist when reviewer closes browser"
- Confirm MindStudio's state persistence is enabled (Phase 1.2).
- If still broken, this is a MindStudio limitation — move gates to Slack-based approvals instead.

### "Images don't generate — Gemini returns safety block"
- Gemini blocks prompts that might generate people even when Brian's rule says no AI photos.
- Fix: for library-routed styles, make sure they're not accidentally going to Stage 04a. Check routing in Stage 03.

### "Drive upload fails"
- MindStudio's Drive integration needs folder creation permission, not just file creation.
- Fix: re-auth with `drive.file` scope + `drive.readonly` scope.

---

## Phase 8 — When to loop back

Re-read `AGENT_SPEC.md` and update this guide when:
- Brandon delivers more templates → expand visual_styles in form
- Ravi confirms gateway migration path → swap direct API calls for gateway calls
- Real users test the form → update field labels and defaults based on feedback
- Performance data updates → replace `performance_data.txt` in knowledge base

---

## Quick reference — files in this folder

| File | Purpose |
|---|---|
| `AGENT_SPEC.md` | Complete workflow design: nodes, state, integrations |
| `PROMPTS.md` | Copy-paste-ready prompts for every LLM node |
| `SETUP_GUIDE.md` | This file — build instructions |
