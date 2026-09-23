# ADAM Pipeline (Master Spec)

**Purpose:** AI-assisted creative production for Upwork's Paid Acquisition team. Takes a brief, produces ad copy + assembled static creatives across multiple sizes and visual styles. Replaces manual concepting and design assembly for batch ad production.

**Status:** Alpha. Web app, pipeline, and the MCP connector all run on **Railway** (deployed from `loganheath-oss/adam`); the Figma plugin assembles final creatives. (The earlier Replit direction in §10 is retired — Railway is the platform.)

**Owner during build:** Logan Heath (CM). Day-to-day collaborators: Adrie Etherington (creative lead, copy), Natelise "Elise" Loeb (designer — Figma templates, library, runs the plugin), Breanna "Bree" Hovan (design producer). Upwork stakeholder: Lee Riley. Architectural sponsor inside Upwork: Leon Zhao. (Brandon Morayo left in July 2026; everything of his moved to Elise.)

This file is the orientation doc for both humans inheriting the project and agents working on the codebase. Specific deep dives live in `docs/`.

---

## 1. Repo map

```
adam/
├── pipeline/
│   ├── run_pipeline.py           Local end-to-end pipeline (source of truth for current logic)
│   ├── 00_intake.py              Stage modules (AWS-bound; behind run_pipeline feature-wise)
│   ├── 01_load_refs.py
│   ├── 02_copy_gen.py
│   ├── 03_image_prompts.py
│   ├── 04_generate_images.py
│   ├── 05_figma_assembly.py
│   ├── 06_deliver.py
│   ├── build_refs.py             Compiles refs/*.txt → configs/refs_context.json
│   └── figma_library.py          Tag-based photo lookup against the Figma file
├── mcp_server/
│   ├── server.py                 7-tool MCP server (stdio + Streamable HTTP)
│   ├── Dockerfile
│   └── fly.toml                  Retired standalone Fly host (MCP now mounted in the web app)
├── plugin/                       Figma plugin (the designer's assembly UI — Elise runs it)
├── order-form/                   HTML order forms (local + hosted)
├── configs/
│   ├── upwork_config.json        Drive folder IDs, Figma file ID, channel specs
│   ├── template_registry.json    Template IDs + per-template rules
│   └── refs_context.json         Compiled brand/legal context (~135KB)
├── refs/                         Raw reference docs (brand voice, legal, KOTH performance, tags)
├── runs/{sprint_id}/             Per-sprint outputs (order.json, copy_outputs.json, manifest, images, etc.)
├── terraform/                    AWS scaffolding (intake Lambda only) — Logan has no write access
├── docs/
│   ├── architecture_and_logging.md   Where each component runs, how to find evidence of activity
│   └── demo_prompts.md
└── mindstudio/                   Historical (deprecated, see §6)
```

**Source of truth is GitHub → Railway.** The repo is `loganheath-oss/adam`
(https://github.com/loganheath-oss/adam); pushing to `main` auto-deploys the backend. Logan's
working checkout is `~/dev/adam-progress`. An older checkout at
`~/Documents/upwork-creative-pipeline` has DIVERGED and is stale — do not work from it.

---

## 2. Quickstart

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r mcp_server/requirements.txt
cp .env.example .env   # then fill in keys

# 2. Run the local pipeline against a test order
python3 pipeline/run_pipeline.py --test

# 3. Or with a real order CSV from the form
python3 pipeline/run_pipeline.py --csv path/to/order.csv

# 4. Run the MCP server locally (stdio, for Claude Code)
python3 mcp_server/server.py

# 5. The MCP connector is mounted in the web app at /mcp — it ships WITH the backend.
#    Push to main → Railway redeploys and the connector updates. No separate deploy.
```

Required env vars: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `FIGMA_ACCESS_TOKEN`, `DATABASE_URL`,
`PIPELINE_API_KEY`, `MCP_AUTH_TOKEN`. See `.env.example`, which is generated from real env reads.

**`GOOGLE_SERVICE_ACCOUNT_JSON` is NOT required** and is not set in production. It appears only in
`01_load_refs.py` / `06_deliver.py`, which are the non-canonical AWS-era scaffold, and in terraform.
The canonical path compiles refs locally and delivers through the manifest plus the Figma plugin, so
there is no Drive upload to authenticate. This line used to list it, which sent people hunting for a
credential that does nothing (corrected 2026-09-22).

Prefer `railway run --service adam -- <cmd>` over a local `.env`: it injects the real service env, so
you never handle a key directly.

**Two credentials expire and fail SILENTLY.** `FIGMA_ACCESS_TOKEN` is a Figma personal access token
with an expiry; when it lapses, the photo library degrades to `needs_human_selection` rather than
erroring, and sprints complete looking fine with no photos. The self-check now has a canary for it.
`SLACK_WEBHOOK_URL` is optional and currently unset, which means the daily digest — the only thing
that carries a failing self-check to a human — no-ops. Set it.

---

## 3. Pipeline at a glance

Order intake → copy generation → image direction → image production (or library lookup) → Figma assembly → delivery. Sprints live under `runs/{sprint_id}/`.

| Stage | What it produces |
|---|---|
| 00 intake | `order.json`, sprint ID |
| 01 load_refs | `context.json` (compiled brand + legal + performance refs) |
| 02 copy_gen | `copy_outputs.json` (6 concepts per style, AI-scored top 3) |
| 03 image_prompts | `image_prompts.csv` (Gemini prompts) OR photo selections from the library |
| 04 generate_images | `images/` (Gemini PNGs) — skipped entirely for library-fed sprints |
| 05 figma_assembly | `asset_manifest.csv` (the handoff to the Figma plugin) |
| 06 deliver | `run_summary.json`, Drive upload, Slack notification |

**Gates** (current 6-gate model, with humans approving via the MCP server's `approve_gate` tool):
1. Order form submission
2. Order + refs confirmation
3. Copy review
4. Image prompt scan
5. Image generation + assembly review
6. Final QA

A 5-gate redesign is proposed (see §10). Don't refactor mid-sprint.

For where each piece runs, what's logged, and how secrets are managed, see `docs/architecture_and_logging.md`. That doc is the source of truth on infrastructure; this section is just the map.

---

## 4. MCP connector

Mounted **inside the Railway web app** at `/mcp` — canonical `https://adam-production-9618.up.railway.app/mcp/` (trailing slash; bare `/mcp` 307-redirects to it, preserving POST + query). `main.py` loads the FastMCP instance from `mcp_server/server.py` by path, mounts `mcp.streamable_http_app()` at `/mcp`, and runs its session manager inside the app lifespan — so the connector reads the **same live `/data/runs` volume + env** as the web app.

**Tools exposed:** `list_sprints`, `get_sprint`, `get_copy_concepts`, `get_image_prompts`, `get_manifest`, `get_generation_log`, `approve_gate`.

**Transports:** stdio (Claude Code, default — `python3 mcp_server/server.py`) and Streamable HTTP (mounted in the web app on Railway; `MCP_TRANSPORT=http` still runs `server.py` standalone for local HTTP testing).

**Auth:** `?auth=<token>` query param or `Authorization: Bearer <token>`, checked against `MCP_AUTH_TOKEN` (falls back to `PIPELINE_API_KEY` when unset). Anthropic's connector form only supports OAuth or no-auth, so we bake the token into the URL and treat the URL as the secret. Pre-production hardening is real OAuth (and a dedicated `MCP_AUTH_TOKEN` so the admin key isn't in the URL).

**Hosting:** Railway service `adam` (same container as the web app). The old standalone Fly server (`adam-pipeline-cm`, `mcp_server/fly.toml`, CM-billed) is **retired** — it served a `runs/` copy baked into its image, which is exactly why it went stale.

**Connector registration:** the connector is registered in **Logan's personal Claude Max account**, not Upwork's Enterprise org. Upwork is on Anthropic Enterprise (which permits custom connectors), but Logan's role in the org doesn't have permission to add connectors — the button is grayed out. Org-wide registration is a follow-up requiring escalation.

**Live data, no redeploy.** The connector reads `/data/runs` (Railway's persistent volume) directly, so sprints appear immediately — no image rebuild. This replaced the old Fly server's baked-in `runs/`, the root cause of its stale data.

For details on how each tool is wired up: read `mcp_server/server.py`. For a complete inventory of where the deployed server's secrets and state live: `docs/architecture_and_logging.md` §2.

---

## 5. Figma assembly plugin

Plugin lives in `plugin/`. **Elise runs it manually in Figma desktop** after the pipeline produces a
manifest CSV. Nobody else can run it: plugin code only executes inside Figma desktop, which is the
defining constraint of that file and has shipped false confidence twice. The countermeasure is
`scripts/verify_plugin_changes.py`, which replays the plugin's own lookups in Python against live
Figma JSON before you push.

**Workflow:** load manifest → plugin clones the appropriate template per row → fills `image_placeholder` (real image file, not a frame), per-style text layers (`lifestyle_image_headline`, `photo_text_headline_text`, etc.), and on-image `CTA` → exports.

**Layer naming convention** (decided April 30, 2026):
- Per-style unique layer names. No generic `headline_text` lookup that would clash across templates.
- Mountain-peak-with-underscores capitalization, matching the existing pipeline spreadsheets.
- `image_placeholder` is a real image file (Figma can't mask frames).
- `CTA` is on-image only. Platform CTA buttons (Meta's "Sign Up" dropdown, etc.) are not pipeline-generated.

**Templates:** `template_registry.json` maps each visual style to a template frame in the Figma file (`DoDwumxELkuAuKKSP5p00e`, now named "ADAM 2026"). New styles require a new template before the plugin can assemble them.

---

## 6. Constraints (non-negotiable)

These are hard rules. Treat them as guardrails when editing code or proposing architecture.

**No AI-generated photography of people.** Brian (Upwork's Creative Director) ratified this April 20, 2026. People photos pull from the approved Upwork brand library in Figma. Gemini is approved for illustrations, designs, abstract graphics, gradients, UI backgrounds. *Open thread (May 7):* Leon pushed back that diffusion *editing* (cropping, removing extra people, fixing cut-off faces) is meaningfully different from generation. Adrie noted the brand library is itself heavily AI-manipulated (green-screen people composited with AI tablets/desks/scenes). Worth revisiting with Brian. Until then, the rule stands.

**No native AWS in the architecture.** Confirmed by Leon May 7. Upwork has no pipeline for tools (no automated VPC/firewall/peering provisioning). Don't design anything requiring Lambdas, RDS, custom VPCs. Use platform-provided modules or stand things up inside the application container (Temporal for workflow/audit, etc.).

**Logan has no AWS write access.** The existing Terraform (`terraform/main.tf`) provisions the intake Lambda + API Gateway + S3. Logan can't `terraform apply` changes. Anything AWS-side is Haresh's team's responsibility.

**LLM traffic must route through Upwork's internal LLM Gateway in production.** Alpha can call Anthropic / Gemini directly. Pre-production: every LLM call swaps to gateway calls (scaffolding exists in stage modules via `LLM_GATEWAY_*` env vars). Haresh's team owns the gateway and has not yet provided endpoint / key / model values.

**MindStudio is out.** Architectural decision finalized May 2026. Don't reference it in current or future flows. The `mindstudio/` directory is historical.

**Hosting today is on CM accounts, not Upwork.** Railway (project `angelic-liberation`, service
`adam`) is CM-billed. The old Fly.io host is **retired**, not a second environment — it served a
`runs/` copy baked into its image, which is exactly why it went stale. Production migration is to
Upwork-internal infrastructure, targeted **end of December 2026** (Lee Riley, 2026-09-21): Upwork
engineering is building a formalized intake for asks like this one because InfoSec was reinventing
the wheel per request. Q4 is covered by a monthly budget for hosting and tokens plus an ad-hoc
support menu agreed between Lee and Blake. The agreed migration shape is Ravi's: build the migrated
version side by side inside Upwork's pipeline while the current one keeps serving, then cut over, so
the wider team sees no downtime.

---

## 7. Stakeholders and ownership

| Person | Role | Owns |
|---|---|---|
| Logan Heath | Tech lead (CM contractor) | Pipeline code, MCP server, plugin, end-to-end integration |
| Adrie Etherington | Creative lead | Copy generation prompts, brand voice, runs sprints through the gates |
| Natelise Loeb ("Elise") | Designer | Figma templates + library tagging, runs the plugin, owns the Designer guide |
| Breanna Hovan ("Bree") | Design producer | Production schedule, stakeholder coordination, merging the role guides |
| Lee Riley | Upwork stakeholder | Q4 support + budget, migration timeline, guide requirements |
| Brian | Upwork CD | Veto on AI photography. Source of the no-AI-photo rule |
| Leon Zhao | Upwork architect / sponsor | Hosting platform decisions, InfoSec narrative, post-contract handoff support |
| Ravi Vora | Director of AI at Wonder | High-level architecture sign-off |
| Haresh's team (incl. Max) | Upwork engineering | Internal LLM Gateway, production deployment, the December migration |
| Brandon Morayo | Departed 2026-07 | Former owner of Figma templates + library tagging — everything moved to Elise |
| Sal / Shams | Upwork InfoSec | Security review (currently being re-engaged via Leon) |
| Blake | CM owner | Logan's contracting entity |

---

## 8. Decisions log (load-bearing context)

Decisions that affect how to read the code or extend it. Older decisions move down or out as they stop being load-bearing.

- **2026-05-07 — Replit selected as target user-facing platform.** Leon's instance provisioned, SSO in flight. Build with portability in mind: no native AWS components, use Replit modules or container-internal services. Master spec (this file) requested explicitly by Leon.
- **2026-05-07 — Diffusion-editing rule reopened.** Logan to bring evidence (Adrie's brand-library AI-manipulation reveal + Leon's distinction) back to Brian.
- **2026-05-07 — Linear integration not pursued.** No PDLC synergy for external marketing use.
- **2026-04-30 — Per-style unique layer names.** Lifestyle uses `lifestyle_image_*`, photo-with-text uses `photo_text_*`, sticky-note uses positional names (`left_headline_text`, etc.). Plugin lookups must respect this.
- **2026-04-30 — Gate model needs redesign.** Current 6-gate model assumes AI image generation; library-fed sprints make gates 4 and 5 hollow. Proposed 5-gate flow with conditional Gemini-QA gate. Don't refactor in-flight; this is a post-demo conversation.
- **2026-04-29 — Anthropic Enterprise confirmed.** Unlocks custom MCP connectors in claude.ai for Upwork org. Logan still lacks the role to add connectors himself; deployment to org requires admin escalation.
- **2026-04-28 — Copy generation moved to Adrie's Claude Project.** Project knowledge files (`refs/*.txt`, `refs/photo_library_tags.csv`) are uploaded there. Re-upload when source files change.
- **2026-04-20 — Brian's no-AI-photo rule ratified.** People photos = library only. Gemini = illustrations / abstracts / backgrounds.

---

## 9. Current state (what works, what's pending)

*Last verified 2026-09-22. The three template/ownership lines here were a year out of date and
described Brandon, who left in July — treat anything undated in this section as suspect.*

**Working:**
- The pipeline runs end-to-end. `pipeline/run_pipeline.py --test`, or a real order through `/new`
- **Meta and Reddit both ship.** 44 ad types carry copy rules and templates: 24 Meta, 20 Reddit.
  The order form offers 23 Meta styles and 20 Reddit
- The Figma plugin assembles both platforms. Reddit was the 2026-09 push: four stacked defects took
  it from 0/40 to 40/40 resolving, with no Meta regression
- MCP connector mounted in the Railway backend at `/mcp` — 7 tools, reading the live `/data/runs`
- Adrie drives the six gates from chat, the web UI, or the connector
- The tagged brand-library lookup in Figma works — **when the Figma token is valid**, see §6
- Web app: order form, sprint pages, `/wiki`, `/learnings`, `/quotes`, and the `/admin/*` surfaces
  (note `/admin` itself 404s; the dashboard is `/admin/dashboard`)
- Off-volume nightly backup to Postgres, and a self-check with a Figma-token canary

**Pending:**
- **Reddit style thumbnails.** 13 of 20 show an empty box and the other 7 show META artwork for a
  Reddit ad type. `scripts/harvest_reddit_thumbs.py` renders them from the real templates; blocked
  on the Figma token
- **`SLACK_WEBHOOK_URL` unset**, so nothing alerts (§2)
- LinkedIn, YouTube, Google/Bing and 3rd Party have templates but **no ad types and no copy rules**,
  so the order form cannot offer them. Adrie and Elise are working through the copy requirements
- Final delivery format from Figma to the Paid Acq team — still `asset_manifest.csv`
- LLM Gateway integration — Haresh's team has not provided endpoint values
- MCP custom-connector registration in Upwork's Enterprise org — admin escalation required. The
  connector currently lives in **Logan's personal Claude Max account**, which is a handoff blocker
- OAuth on the MCP server (replacing the bearer token in the URL)
- Per-user audit trail (the bearer token is a single "system" identity)
- Localization expected ~November 2026. Animation explicitly deferred (Lee, 2026-09-21)

---

## 10. Architectural direction

**The Replit direction is RETIRED.** It was the May 2026 plan and is listed in the decisions log
below for history only. The user-facing surface was built as a Next.js app and ships on Railway
alongside the backend; the order form is no longer static HTML. Do not design toward Replit.

**Migration target is Upwork-internal, end of December 2026.** See §6 for the shape: side-by-side
build, then cut over, so the wider team sees no downtime. The MCP server and pipeline are portable
Python and should stay that way.

**Gate model** moves from 6 gates to 5, with the Gemini-QA gate skipped automatically when no Gemini calls happened (library-fed sprints). Stage 03 needs to expose photo+copy pairings as a reviewable artifact; stage 05 needs to actually present the manifest for review (today it just runs through). Tag derivation in stage 03 is currently a 25-line rule-based function; an LLM-derived tags-within-rule-guardrails approach would sharpen the "right photo for this concept" decision.

**Visual regression** Claude has native visual-regression capability (text overflow, image cut-offs, boundary checks for PowerPoint / PDF / web). Worth a 30-minute test against an exported Figma frame to see if it can replace a planned QA gate.

**Handoff model post-Logan-contract:**
- This file (and the `docs/` companion) is the spec source of truth
- Coding agents (Claude Code or claude.ai with the MCP) are the day-to-day support
- Logan retainer for technical issues
- Leon's AI admins as fallback

---

## 11. Working with this codebase

**Source of truth for current pipeline logic:** `pipeline/run_pipeline.py`. The numbered stage files (`00_intake.py` … `06_deliver.py`) are the AWS-bound production scaffold and currently lag the monolithic version.

**When extending stages:** `run_pipeline.py` is the ONLY canonical implementation and the only port source. The numbered modules 02–06 are a stale, NON-CANONICAL scaffold (stamped as such, 2026-07-31) — do not port to or from them; a future AWS migration starts from `run_pipeline.py`. `00_intake.py` is live and load-bearing. The MCP server loads `run_pipeline.py` directly via `importlib` (the leading-digit filenames forbid normal import).

**Reference data is compiled.** Edit raw refs in `refs/`, then run `python3 pipeline/build_refs.py` to regenerate `configs/refs_context.json`. Don't hand-edit the compiled file.

**Templates and library:** changes to `template_registry.json` and the Figma file's tagged photo library are coordinated with **Elise**. Don't add visual styles to the order form before the corresponding template exists.

**Don't reintroduce MindStudio** in any flow. The `mindstudio/` directory is kept for historical reference only.

**No redeploy is needed to see new sprint data.** The connector reads `/data/runs` on the Railway
volume directly, so sprints appear immediately. The old Fly server baked `runs/` into its image,
which is why its data went stale — that host is retired. For pure code iteration, prefer Claude
Code in stdio mode (no deploy needed).

**Conventions:**
- Mountain-peak-with-underscores for layer names (matches existing spreadsheets)
- Layered judgment principle: rules define boundaries (Brian's no-AI rule, rights, no repeats), AI makes judgment calls inside them, humans veto/override at gates
- Don't add backwards-compatibility shims for unused code paths; delete cleanly

---

## 12. Pointers

- **Live MCP connector:** https://adam-production-9618.up.railway.app/mcp/ (mounted in the web app; auth via `?auth=<token>`)
- **Figma file:** `DoDwumxELkuAuKKSP5p00e` (Paid Acquisition 2026)
- **Drive folders** (IDs in `configs/upwork_config.json`):
  - Brand: `1Jn42lIOVAir9QU-PAMGnDmO8gMsz6BGA`
  - Sprints (review queue): `1YpFoiUadL3pguWDJ_Uu4dasek1dj-mLY`
  - Approved: `1OO2Yg7n1E5UhTw3cEJ9mUN_GF0I5xnKv`
- **Architecture and logging deep dive:** `docs/architecture_and_logging.md`
- **Demo prompts and walkthroughs:** `docs/demo_prompts.md`
- **Slack channel:** `#paid-acquisition-pipeline`
