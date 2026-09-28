# Fixing errors (August runbook)

**Who this is for:** the Upwork team running ADAM while Logan is out (August 2026). No coding required for anything in the first two sections. This page is built from the actual issues we hit during the build — in rough order of how likely you are to see them.

**The golden rule:** ADAM fails *loudly and recoverably*. Almost every problem shows up in one of three places, and almost every fix is a button, an environment variable, or an edit to a text file — not code.

---

## Where problems show up (check in this order)

1. **The Reliability dashboard — `/admin/dashboard`** — the headline view. Shows the % of runs completing clean and an **incident list with the actual error message** for every failed run (which sprint, which stage, what went wrong). At the top is a **health strip** — three pills (Volume %, API + models, errors in the last 24h). If any pill is amber or red, that's your first clue; a red banner tells you a run will likely fail until it's fixed. Start here when someone says "ADAM's broken."
2. **The Activity timeline — `/admin/activity`** — *everything* that happened, newest first: orders, gate approvals, assemblies, edits, and **errors** in one feed. Filter by event type (there's an "⚠ Errors only" option), user, or sprint. This is the "what actually happened, in order" view — use it to see the sequence around a problem, or to catch up on a stretch you missed.
   - **🔍 Diagnose** — on any error row, click **Diagnose** and ADAM analyzes it *against this runbook* and hands back the likely cause + step-by-step fix + whether it needs an engineer. It's the fastest way to triage: let ADAM point you at the right section below before you read further.
3. **The sprint's own page — `/sprints/<id>`** — shows the exact state (`awaiting_gate_3`, `error`, `interrupted`…), the error text, and a **Resume** button.
4. **The Issues queue — `/admin/issues`** — where anyone can file "something looked wrong." Triage these weekly; distill the real ones into Learnings (see below). Open issues older than a week get flagged so nothing rots.

**Two more admin tabs, for the bigger picture:**
- **Spend — `/admin/spend`** — approximate tokens and cost, by day / user / model, with month-to-date vs. budget and an end-of-month projection. This is the screen to screenshot when someone asks "how much is ADAM costing." (Set `ADAM_MONTHLY_BUDGET_USD` in Railway to show a budget bar.)
- **Digest — `/admin/digest`** — the whole period on one screen (runs, assemblies, issues, errors, spend, deploys) with a **plaintext block you can copy straight into Slack or the change log**. This is the automated version of the manual August summary — pull it weekly.

---

## The most common problems and their fixes

### 1. A sprint failed or is stuck → read the error, hit Resume
The single most common situation. Open `/sprints/<id>` (or find it in the `/admin/dashboard` incident list), read the error, then click **Resume** — it re-runs just the failed stage, keeping all prior work.
- State says **`interrupted`** or mentions a server restart → a redeploy happened mid-run. Nothing is lost: **Resume**.
- Same stage fails twice with the same error → match the error text against the cases below.

### 2. "No space left on device" (ENOSPC) → prune old sprints
The storage volume (500 MB) fills up with sprint images; runs then die mid-image-stage. This bit us in production.
- **See usage (in a browser):** log in at <https://adam-production-9618.up.railway.app/admin/dashboard> — the sprint table has a **Size** column. For the raw per-sprint list, largest first, open <https://adam-production-9618.up.railway.app/admin/storage> in the same browser once you're logged into the dashboard.
- **Fix:** `POST /admin/prune` with the API key. This one is **not** a page — visiting it in a browser returns 405, because it deletes things and has to be a deliberate call. Deletes old/errored sprints. Keep anything the team still needs, then re-run the failed sprint from its gate.

> **Host matters.** Every `/admin/*` path lives on the **API** service,
> `adam-production-9618.up.railway.app` — *not* on `adam-web-production.up.railway.app`, which is the
> Next.js front end and will 404 on all of them.

### 3. "Your credit balance is too low" (HTTP 400 from Anthropic) → fund or swap the key
Copy generation returns a 400 (note: 400, *not* 401 — it looks like a bad request but it's billing).
- **Fix:** fund the Anthropic account, or set a funded `ANTHROPIC_API_KEY` in **Railway → adam service → Variables**, then **Resume from Gate 2**.

### 4. "model … not_found" (404) → the model ID is stale
Anthropic retires model IDs. If copy-gen or chat suddenly 404s naming a model string, the ID in code needs updating (this one *is* a code change — one string).
- **Interim:** file it in `/admin/issues` + the change log. It's a two-minute fix for any engineer: search the repo for the dead model ID, replace with the current one, push.

### 5. Copy quality is off (tone, format, structure) → that's steering, not a bug
Two levers, **neither needs code**:
- **Learnings (`/learnings`)** — the editable guidance ADAM reads on *every* run and chat. "Stop doing X, prefer Y" belongs here. Takes effect on the next run.
- **The issue → learning loop** — when someone reports copy problems in `/admin/issues`, use **"Distill into a learning"** on the issue: it appends your instruction to Learnings and marks the issue learned. This is the intended self-serve fix for recurring copy problems.
- Per-ad-type structure (character caps, chat-bubble-is-a-conversation, CTA rules) lives in `configs/ad_type_style_guide.json` — editable JSON, but changes need a push, so log those for an engineer or the September list.

### 6. Ads in Figma show placeholder / Lorem Ipsum / copy in the wrong slot → template layer names
The plugin fills copy into **named layers**. If a template's text layers get renamed in Figma, the plugin can't find them and leaves placeholder text.
- **Fix (designer):** check the layer names on that template against the working ones (`Copy_Headline`, `Copy_Subhead`, `CTA`, and the per-style names). Renaming back fixes it — no code.
- The plugin's log panel says exactly which fields it couldn't place and on which style.

### 7. Updating the copy reference documents (Adrie's PDFs)
The brand/legal/examples docs ADAM writes from live in `refs/` as text files, compiled by one script.
- **Process:** replace the file in `refs/` → run `python3 pipeline/build_refs.py` → commit + push (auto-deploys). If no engineer is around, attach the new doc to the change log — it's a five-minute swap.

### 8. A deploy failed (for whoever pushes code)
Two rules cover every deploy failure we ever hit:
- **Backend:** any dependency change in `pyproject.toml` must be followed by `uv lock` and committing `uv.lock` — the build runs `uv sync --locked` and fails on mismatch. (A failed deploy never takes the site down; the old version keeps serving.)
- **Frontend (adam-web):** never `railway up` from inside the repo — deploy from an isolated copy of `web/` only. Full commands are in [Deployment & ops](08-deployment-and-ops.md).

---

### 9. "No confirmed template" warnings → check whether the style actually rendered

Treat this warning as a lead, not a verdict. The 2026-08-21 isolation test ran only
the nine flagged styles and **eight of the nine rendered fine** — one real failure
(Search Bar with Talent Badge) hiding behind eight false alarms. If the style came
out of Figma looking right, the warning was wrong.

**Bespoke is flagged MANUAL by design and is never a defect.** Bespoke is always
custom and is expected to need hand design, so exclude it from any count of broken
templates. Leaving it in the list is how a clean run starts looking broken.

The method that settled this is worth reusing: isolate the suspect styles, run only
those, and log what actually rendered. Four earlier mixed runs could not answer the
question that one isolated run closed.

## When you can't fix it

1. **File it in `/admin/issues`** — with the sprint ID and what you expected vs got. This is the system of record.
2. **Add it to the August change log** (Bree owns it) — Logan reviews the log at the end of August and applies fixes in September.
3. **Template/visual problems** → Elise owns the Figma templates; copy-rule questions → Adrie; infrastructure/hosting → Haresh.

## Quick reference: where things live

| Thing | Where |
|---|---|
| API keys (Anthropic, Gemini, Figma) | Railway → `adam` service → Variables |
| Sprint data | Railway volume (`/data/runs`) — survives redeploys |
| Usage/reliability/spend data | Railway Postgres (`/admin/dashboard`, `/admin/activity`, `/admin/spend`, `/admin/digest` read it) |
| Monthly budget (optional) | `ADAM_MONTHLY_BUDGET_USD` env var on the `adam` service |
| Copy guidance ADAM follows | `/learnings` (editable in the app) |
| Approved testimonial quotes | `/quotes` (editable in the app; testimonial ads draw from it) |
| Per-ad-type copy rules | `configs/ad_type_style_guide.json` |
| Reference docs (brand/legal/examples) | `refs/` → compiled by `pipeline/build_refs.py` |
| Templates | Figma "Paid Acquisition 2026" (Elise) |
| The code | github.com/loganheath-oss/adam (private; Haresh has read access) |

## Template/layer problems in assembled boards
Run `railway run --service adam -- python3 tests/figma_template_lint.py` — it reports per-style template resolution and nested `Image-Placeholder` layers (the cause of wrong/duplicated photos and placeholder text). Naming standard: `docs/figma-naming-convention.md`.

## Is this plugin flag real? (ADAM-015)

The assembly log marks severity with a glyph. **The glyph is the answer** — you do
not have to judge each message. This table exists because "is this an error?" came
up repeatedly in the 2026-09-23 working session, and because a run can finish
perfectly while printing a dozen lines that look alarming.

| Glyph | Meaning | Do you act? |
|---|---|---|
| `✗` | **Real miss.** Something that should have been produced was not. Counts toward the run's miss tally. | Yes |
| `⚠` | **Real warning.** The run continued, but a slot, layer or pill did not get what it was meant to. Counts toward the warning tally. | Usually |
| `↻` | **Self-healed.** The plugin hit an ambiguity and resolved it correctly. | No |
| `·` | **Informational.** Expected absence, by template design. | No |

### The ones that look bad and are not

- **`· subhead/stat not filled — no layer matched`** — some template families are
  legitimately subhead-free (`subhead_only_without_cta`). Nothing is missing.
- **`· body not filled — no Copy_Body layer`** — same: that template has no body layer.
- **`↻ duplicate frames: chose '…'`** — two same-name same-size frames existed and the
  plugin picked the one with actual copy layers. Worth tidying the file eventually;
  the run is correct.
- **`⚠ Testimonial / Talent Profile: no Example Profiles found — kept template …`** —
  it fell back to the template's own headshot. The ad is fine.
- **`⚠ 'Generated Tests' container not found — placing boards loose on the page`** —
  placement only. The boards are there, just not inside a container.
- **`⚠ Captured node no longer exists — falling back to page search`** — it recovered.

### The ones that mean a real problem

`✗ board failed for concept`, `✗ No styled template found for`, `✗ No image target
found in clone`, `⚠ EMPTY TEMPLATE`, `⚠ headline NOT filled`, `⚠ cta NOT filled`,
`⚠ no image applied`, and `⚠ No template by convention and unknown visual_style`.

**`✗ Library node '…'`** deserves its own note: it usually means the photo library
could not be read, and the most common cause is an **expired `FIGMA_ACCESS_TOKEN`**,
not a bad template. Check the token before touching Figma.

**`⚠ Could not update '<layer>'`** now only appears when the house-font fallback ALSO
failed. On its own it used to be routine font noise; today it is real.

### Currently expected: `⚠ row missing figma_node_id`

Image generation is off (2026-09-24), so image rows carry `needs_human_selection`
with no photo pick. The main concept-board path skips the image step for those rows
and stays quiet, but the legacy and styled-per-row paths will print this warning.
**While image generation is off, treat it as informational.** It becomes a real
warning again the day image sourcing is turned back on.
