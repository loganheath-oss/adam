# Fixing errors (August runbook)

**Who this is for:** the Upwork team running ADAM while Logan is out (August 2026). No coding required for anything in the first two sections. This page is built from the actual issues we hit during the build — in rough order of how likely you are to see them.

**The golden rule:** ADAM fails *loudly and recoverably*. Almost every problem shows up in one of three places, and almost every fix is a button, an environment variable, or an edit to a text file — not code.

---

## Where problems show up (check in this order)

1. **The Reliability dashboard — `/admin`** — the headline view. Shows the % of runs completing clean and an **incident list with the actual error message** for every failed run (which sprint, which stage, what went wrong). At the top is a **health strip** — three pills (Volume %, API + models, errors in the last 24h). If any pill is amber or red, that's your first clue; a red banner tells you a run will likely fail until it's fixed. Start here when someone says "ADAM's broken."
2. **The Activity timeline — `/admin/activity`** — *everything* that happened, newest first: orders, gate approvals, assemblies, edits, and **errors** in one feed. Filter by event type (there's an "⚠ Errors only" option), user, or sprint. This is the "what actually happened, in order" view — use it to see the sequence around a problem, or to catch up on a stretch you missed.
3. **The sprint's own page — `/sprints/<id>`** — shows the exact state (`awaiting_gate_3`, `error`, `interrupted`…), the error text, and a **Resume** button.
4. **The Issues queue — `/admin/issues`** — where anyone can file "something looked wrong." Triage these weekly; distill the real ones into Learnings (see below). Open issues older than a week get flagged so nothing rots.

**Two more admin tabs, for the bigger picture:**
- **Spend — `/admin/spend`** — approximate tokens and cost, by day / user / model, with month-to-date vs. budget and an end-of-month projection. This is the screen to screenshot when someone asks "how much is ADAM costing." (Set `ADAM_MONTHLY_BUDGET_USD` in Railway to show a budget bar.)
- **Digest — `/admin/digest`** — the whole period on one screen (runs, assemblies, issues, errors, spend, deploys) with a **plaintext block you can copy straight into Slack or the change log**. This is the automated version of the manual August summary — pull it weekly.

---

## The most common problems and their fixes

### 1. A sprint failed or is stuck → read the error, hit Resume
The single most common situation. Open `/sprints/<id>` (or find it in the `/admin` incident list), read the error, then click **Resume** — it re-runs just the failed stage, keeping all prior work.
- State says **`interrupted`** or mentions a server restart → a redeploy happened mid-run. Nothing is lost: **Resume**.
- Same stage fails twice with the same error → match the error text against the cases below.

### 2. "No space left on device" (ENOSPC) → prune old sprints
The storage volume (500 MB) fills up with sprint images; runs then die mid-image-stage. This bit us in production.
- **See usage:** `GET /admin/storage` (per-sprint sizes, largest first).
- **Fix:** `POST /admin/prune` (needs the API key) — deletes old/errored sprints. Keep anything the team still needs, then re-run the failed sprint from its gate.

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

## When you can't fix it

1. **File it in `/admin/issues`** — with the sprint ID and what you expected vs got. This is the system of record.
2. **Add it to the August change log** (Bree owns it) — Logan reviews the log at the end of August and applies fixes in September.
3. **Template/visual problems** → Elise owns the Figma templates; copy-rule questions → Adrie; infrastructure/hosting → Haresh.

## Quick reference: where things live

| Thing | Where |
|---|---|
| API keys (Anthropic, Gemini, Figma) | Railway → `adam` service → Variables |
| Sprint data | Railway volume (`/data/runs`) — survives redeploys |
| Usage/reliability/spend data | Railway Postgres (`/admin`, `/admin/activity`, `/admin/spend`, `/admin/digest` read it) |
| Monthly budget (optional) | `ADAM_MONTHLY_BUDGET_USD` env var on the `adam` service |
| Copy guidance ADAM follows | `/learnings` (editable in the app) |
| Approved testimonial quotes | `/quotes` (editable in the app; testimonial ads draw from it) |
| Per-ad-type copy rules | `configs/ad_type_style_guide.json` |
| Reference docs (brand/legal/examples) | `refs/` → compiled by `pipeline/build_refs.py` |
| Templates | Figma "Paid Acquisition 2026" (Elise) |
| The code | github.com/loganheath-oss/adam (private; Haresh has read access) |
