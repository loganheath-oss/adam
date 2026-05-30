# ADAM Pipeline — Project Handoff & Conversation Resume Doc

Last updated: 2026-05-29

Purpose: complete context for resuming a Claude Code session on this project at any time. Captures who, what, where, why, and the current state of all moving pieces.

---

## 1. Project identity

**ADAM** is Upwork's paid-acquisition creative pipeline. A single order goes in (platform, visual styles, resolutions, brief, audience), and the system produces delivery-ready ad creatives end-to-end: copy, image picks/generation, and a final assembled asset rendered from a Figma template.

The pipeline is **gated**: five human-review checkpoints (gates 2–6) where a reviewer approves the artifact at that stage before the next stage runs.

| Gate | What's approved |
|---|---|
| 2 | Order + refs confirmed |
| 3 | Copy approved |
| 4 | Image prompts approved |
| 5 | Images approved |
| 6 | Final QA approved |

---

## 2. Logan's role and the commercial structure

- **Logan Heath** is the technical lead. He's a **CM (Creative Machine) contractor**, NOT an Upwork employee.
- **CM has a contract with Upwork.** Blake owns CM.
- The right billing entity for engagement infrastructure is CM, not Logan personally.
- The repo (`loganheath-oss/adam`) is currently on Logan's personal GitHub account. Eventual transfer to CM's org or Upwork's org is expected after stakeholder sign-off.

---

## 3. Stakeholders

| Person | Role | Why they matter |
|---|---|---|
| Brandon Morayo | Designer | Builds Figma templates. Owns brand palette, fonts, layout rules. |
| Adrie | Copy lead | Runs the claude.ai project that generates copy. Her system prompt lives in her Claude project, external to this codebase. |
| Brian | Brand/rights | Authoritative "no AI-generated photos of people" rule. All people photos must come from the brand library. |
| Ravi | Upwork eng leadership | LLM Gateway requirement context. |
| Haresh | Upwork eng leadership | LLM Gateway team. Production LLM traffic must go through internal gateway; alpha can skip. |
| Leon | Upwork stakeholder | Asked for the master CLAUDE.md spec at the project root. |
| Adam | Stakeholder | Pipeline name hints at target persona. |
| Blake | CM owner | Logan's direct contracting relationship. CM bills Upwork. |

---

## 4. Architecture (current state)

```
Order form (HTML)
   │
   ▼
POST /submit  (FastAPI on Replit — app.py)
   │   OR
POST /integrations/hightouch/brief  (Hightouch reverse ETL inbound)
   │
   ▼
runs/<sprint_id>/order.json
   │
   ▼
python pipeline/run_pipeline.py --json <order>
   │
   ├─ Stage 00: intake validation (pipeline/00_intake.py)
   ├─ Stage 01: refs (brand context, photo library cache)
   ├─ Stage 02: copy generation (Adrie's claude.ai project)         [GATE 3]
   ├─ Stage 03: image prompts                                        [GATE 4]
   ├─ Stage 04: image generation (Gemini + brand library picks)     [GATE 5]
   ├─ Stage 05: Figma assembly (plugin clones template, fills it)
   └─ Stage 06: deliver (manifest CSV, exports)                      [GATE 6]
   │
   ▼
Figma plugin (manual run today) assembles the final PNGs
```

**Two gate-driving surfaces exist:**

1. **claude.ai + MCP server on Fly** (`adam-pipeline-cm.fly.dev/mcp`) — the original path. Adrie's claude.ai project knows the 7 MCP tools and drives gates conversationally.
2. **Native Replit chat** at `/sprints/<id>/chat` — Phase 3 work. Same 7 tools as local Python functions, Anthropic SDK orchestrator, sprint-bound chat UI with gate tabs. Replaces the claude.ai dependency for gate driving.

Both currently work. The Replit chat is the strategic destination.

---

## 5. Tech stack & surfaces

| Surface | Path | Purpose |
|---|---|---|
| `pipeline/` | Python | 6-stage runner (`run_pipeline.py`), photo-library matcher (`figma_library.py`), template inspector (`inspect_templates.py`), intake validator (`00_intake.py`) |
| `configs/template_registry.json` | JSON | THE source of truth for templates: frame IDs, layer IDs, copy rules, variant lists |
| `plugin/` | Figma plugins | Assembler (`plugin/code.js`), tag_manager (Brandon's tag browser), library_tagger |
| `mcp_server/` | Python (FastMCP) | Fly-hosted MCP server. 7 tools exposed to claude.ai. URL: `adam-pipeline-cm.fly.dev/mcp` |
| `agent/` | Python + HTML | Phase 3 native orchestrator: tools.py mirrors MCP tools, orchestrator.py runs Anthropic tool-use loop, sprint_chat_ui.html is the gate-tab chat |
| `app.py` | FastAPI entry | Serves order form, accepts /submit, exposes /sprints status, includes agent + integrations routers |
| `integrations/hightouch.py` | FastAPI router | Inbound `/integrations/hightouch/brief` endpoint for Hightouch reverse ETL triggers |
| `order-form/` | HTML | `upwork-order-form.html` (legacy 13-style production form) + `order-form-local.html` (24-style modern form with thumbnails) |
| `refs/` | Text/MD | Copy rules, visual style guide, photo library tag vocabulary |
| GitHub | `github.com/loganheath-oss/adam` | Source of truth. Private repo on Logan's personal account. Created 2026-03-30. |
| Replit | (Logan's personal account) | Hosts the live demo. Bridged to GitHub via PAT. The Repl uses the project root, runs `uvicorn app:app`. |
| Fly | `adam-pipeline-cm.fly.dev` | MCP server, kept as a fallback gate-driving path. |

---

## 6. Brand & creative constraints

### Brian's rules

- **NO AI-generated photos of people.** All people photos must come from the brand library (tagged Figma frames). Abstracts and backgrounds can be AI-generated.
- This is non-negotiable. The pipeline routes accordingly: `PHOTO_LIBRARY_STYLES` use `figma_library.pick_photo_for_asset`; `BACKGROUND_ONLY` styles use Gemini for gradient backgrounds; meme/illustrated styles ship with baked-in template imagery.

### Brand palette (Brandon, May 12)

- Primary green: `#14A800`
- Hero green (text callouts): `#67DC12`
- Green ramp light → dark: `#E9F899`, `#E0F5C3`, `#C4F4C0`, `#9ED79B`, `#41D131`, `#2EBE1B`, `#67DC12`, `#14A800`
- Black `#000000`, White `#FFFFFF`
- PrimaryGlimmer + SecondaryGlimmer (gradient PNG textures, not flat colors)
- Figma swatch node IDs documented in `memory/project_brand_palette.md`

### Typography

- **PP Neue Montreal** (paid font, self-hosted woff2 in `order-form/fonts/`)
- Weight capped at Regular (400) per Brandon's spec
- Both forms have the font + weight cap + ambient glimmer + Upwork logo applied

### Adrie's copy rules

Live in `refs/visual_style_copy_rules.txt`. Per-style character ceilings:

| Style | Headline | Subhead/Name | CTA | Notes |
|---|---|---|---|---|
| Text Only | 104 (Quote) | 52 (Name) | 14 | Multi-variant emit (WhiteBorder + NoBorder) |
| Split Screen | 36 | — | 14 | Two image placeholders (left + right) |
| Reminder | 104 (body) | 52 (label "Reminder") | 32 (CTA pill text) | Body and label share layer name; disambiguated by index |
| Meme | 104 (caption) | — | hidden | Meme image baked into template per family |

Adrie's claude.ai project does NOT yet have these structural rules in its system prompt. That's an open dependency for any expansion.

### Six-week milestone

Friday May 1 2026 was the formal review. Local-only demo was accepted. Brandon delivered 3–5 templates by that Friday.

---

## 7. Template registry state

24 visual styles defined in the order form. Pipeline routing is wired for all 24. **Templates exist for 7.** The other 17 styles will validate and route but produce no final assembled creative until Brandon (or a successor designer) ships the Figma template family.

### Templates that work end-to-end

1. **Lifestyle Photo** (`Template_LifestylePhoto_1440x1440`)
2. **Photo with Text** (`Template_PhotoWithText_1440x1440`)
3. **Testimonial** (`Quote_1080x1080` / TestimonialA / TestimonialB)
4. **Split Screen** (`Template_SplitScreen_1440x1440` + 1440x1800)
5. **Text Only** (3 variants under `Adtype: Text Only`, frames named `Template_TestimonialC_1440x1440`)
6. **Reminder** (`Template_Reminder_1440x1440` x 2 variants)
7. **Meme** (this-is-fine dog template — 3 frame variants under `Adtype: Meme`, frames named `Template_SplitScreen_1440x1440`)

### Quirks the codebase handles (do not "fix" without context)

- **Text Only** frames are named `Template_TestimonialC_*` (Brandon reused the TestimonialC base). Disambiguated via `STYLE_ADTYPE_CONTAINERS["text only"] = ["Adtype: Text Only"]` in the plugin.
- **Meme** frames are named `Template_SplitScreen_*` (Brandon reused the SplitScreen skeleton). Same container-scoping disambiguation.
- **Reminder** has TWO TEXT layers both named `Notification_Headline_Text` — one is the static "Reminder" label, one is the body. Plugin disambiguates by index (0 = label, 1 = body).
- **Multi-variant emit:** Text Only and Meme ship TWO variants per concept (white-border + no-border). Brandon's call so he has comparable options.
- **Split Screen** needs TWO library photos. The template has `left_image_placeholder` + `right_image_placeholder`. Pipeline calls `pick_photo_for_asset` twice with `exclude_ids` to guarantee distinct picks.

Full quirk documentation lives in `memory/project_brandon_template_quirks.md`.

### Styles defined but waiting for templates

Graphic with Text, Us vs Them, Social Media Profile, Pie Chart, Hybrid, Search Results, Search Bar with Talent Badge, Chat Bubble, Notification, Device UI, Platform UI, Sticky Note, Poll, Tweet / Post Mockup, Text with Button, Talent Profile, Bespoke.

---

## 8. What's been built — chronological

### April – early May
- Pipeline working for Lifestyle Photo, Photo with Text, Testimonial
- Figma plugin for template assembly
- MCP server live on Fly with 7 tools
- Order form (static HTML)
- April 30: gate-model redesign discussion. Gates 4+5 are no-ops for library-fed sprints. Proposed 5-gate flow with conditional Gemini-QA gate.

### May 7
- **Replit selected as user-facing platform.** AWS native permanently out. SSO in flight.

### May 8
- Created master CLAUDE.md at project root per Leon's request.
- Sketched the Replit architecture (FastAPI + MCP mount + storage abstraction).

### May 11–18 — new ad types
- **Text Only** wired end-to-end (3 variants, multi-emit ships white-border + no-border)
- **Reminder** wired end-to-end with body/label disambiguation by layer index
- **Split Screen** wired with dual brand-library photo picks (added `exclude_ids` param to `pick_photo_for_asset`)
- **Meme** wired end-to-end (this-is-fine dog template, multi-emit white + no-border)
- Added structural copy rules to `refs/visual_style_copy_rules.txt`

### May 12 — brand applied to order form
- PP Neue Montreal self-hosted, replaced Bebas Neue + IBM Plex Mono
- Brandon's green palette in `:root` CSS variables
- Section badges repainted to cycle through three light greens
- Upwork wordmark SVG inlined in header
- Submit button → pill shape, hover turns brand green
- Ambient glimmer (CSS-animated radial blobs in brand greens)
- Font weight capped at Regular (400) globally
- Production form: added Text Only and Reminder to dropdown

### May 14
- **Motion ads put in scope.** Logan picked **Path A (motion-wrap)**: take static PNGs, add GSAP intro/outro, render via headless Chromium + ffmpeg. Not yet built.

### May 18
- **Decision: meme library architecture.** Brandon to ship a generic Meme template with `meme_image_placeholder` plus a tagged Meme Library page in Figma. Plus rights tags. Plus legal sign-off on which memes are licensed for commercial use. Not yet built — current meme = single this-is-fine template family.

### May 19 — Replit migration day
- Replit POC scaffold (`app.py`, `.replit`, `requirements.txt`)
- First Repl created from zip upload, then connected to GitHub
- **Phase 1**: order form hosted on Replit at a public `.replit.dev` URL
- **Phase 2**: form submission spawns pipeline subprocess; `/sprints/<id>` status endpoint reads on-disk artifacts
- **Phase 3 scaffold pushed**: `agent/` module with native Claude API orchestrator, mirroring the MCP server's 7 tools. Vanilla-JS chat UI at `/chat/ui`. Replaces "open ADAM Pipeline in claude.ai" with in-Replit chat.
- GitHub repo `loganheath-oss/adam` established as the source of truth. Force-pushed local current state over older history. Bridge to Replit via OAuth + PAT in progress.

### May 24 — Phase 3 UX redesign
- Replit Agent's parallel Phase 2 build (a `main.py` file in the Repl) diverged from GitHub for several days. Caused the "API key gate on sprint detail page" bug and accumulated friction.
- **Sprint-bound chat UI shipped (commit `ad745e6`)**: split-pane layout, gate tabs on right (Order+Refs / Copy / Image Prompts / Images / Final QA), auto-bootstrap on load, redirect after submit.
- **Form: instant redirect (commit `b588b7c`)**: no popup, no splash. Submit → straight to `/sprints/<id>/chat`.
- Resolution path: hard-reset the Repl to GitHub via `git fetch origin main && git reset --hard origin/main` in the Repl shell. That wiped the Agent's drift.
- Confirmed working: Logan submitted an order, landed in chat with gate tabs visible. ANTHROPIC_API_KEY was missing so chat couldn't actually talk to Claude, but the routing/UI is solid.

### May 26 — strategic options discussion
- Three options framed for Upwork continuation:
  1. **Ship + integrate** — lock current pipeline, focus on Hightouch and integrations. 7-style catalog cap.
  2. **Ship + integrate + designer** — adds a designer to ship the remaining 17 templates over months.
  3. **Ship + integrate + designer + motion** — adds the motion-wrap output path. Highest leverage.
- These are cumulative, not competing. Position as a phased roadmap with stop-points.

### May 29 — Hightouch integration (commit `1bc303b`)
- New `integrations/` directory + `integrations/hightouch.py`
- `POST /integrations/hightouch/brief` — bearer-authed endpoint accepting a flat campaign-brief JSON, translating to canonical order.json, creating a sprint, firing the pipeline
- Idempotent on `external_id` via `runs/_hightouch_external_id_index.json`
- Validation reuses `pipeline/00_intake.py` (no schema drift)
- Health probe + by-external-id lookup endpoints for Hightouch destination setup
- Spec doc at `docs/hightouch_integration.md` ready to send to Upwork's data team
- Sample brief at `docs/hightouch_sample_brief.json` for local curl tests

---

## 9. Current operational state

### What's on GitHub `main` (HEAD = `1bc303b`)

- Order form with brand styling + instant redirect on submit
- FastAPI `app.py` serves form, `/submit`, `/sprints`, `/sprints/<id>`, agent router, hightouch router
- Sprint-bound chat UI at `/sprints/<id>/chat` with gate tabs
- Agent orchestrator (Anthropic SDK + tool-use loop)
- Hightouch inbound integration endpoint
- 7 working ad types end-to-end (Lifestyle Photo, Photo with Text, Testimonial, Split Screen, Text Only, Reminder, Meme)

### What's likely in the Repl

Unknown without checking. Likely behind GitHub `main` if Logan hasn't pulled since May 24's reset. Run `git fetch origin main && git reset --hard origin/main` in the Repl shell to sync.

### Required env vars in Replit Secrets

- `ANTHROPIC_API_KEY` — for the native chat orchestrator (Phase 3). Without it, the chat tells the user the key is missing.
- `GEMINI_API_KEY` — for image generation in stage 4.
- `FIGMA_ACCESS_TOKEN` — for refs loading and brand library photo picks.
- `HIGHTOUCH_API_KEY` — for the Hightouch inbound integration. Without it, the endpoint returns 503.

### Replit-side gotchas (lessons learned)

- **Repl free tier sleeps** after inactivity. Public URL goes 502 until you click Run. For real demo URLs, use Reserved VM (paid, ~$7/mo).
- **The Replit Agent should NOT be used for code design.** It edits in-Repl files that don't make it back to GitHub. Pattern: I (Claude Code) design + push to GitHub. Logan hard-resets the Repl to GitHub. Replit Agent only for environment ops (Secrets, restarts, log inspection, cache-bust diagnostics).
- **The chat UI is at `/sprints/<id>/chat`**, NOT the `/chat/ui` playground. The form redirects to the sprint-bound URL automatically.

---

## 10. Open decisions & pending work

### Product decisions Logan needs to make/relay

1. **Adrie's copy generator needs the structural rules.** Per-style character ceilings live in `refs/visual_style_copy_rules.txt`. She needs to update her claude.ai project's system prompt. External to this codebase.
2. **Meme library architecture.** When Brandon's ready, port from per-meme template families to a generic Meme template + tagged Meme Library page in Figma. Includes rights/usage tags. Legal sign-off needed on which memes are licensed for commercial use.
3. **Motion ads.** Path A (motion-wrap) is the chosen approach but not yet built. ~1 week of engineering when prioritized.
4. **Production order form still on the legacy 13-style list.** Local form has all 24. Production needs syncing.
5. **Auth on the Replit app.** Anyone with the URL can submit and drive gates. Need at least password gate before sharing widely. SSO is the eventual target.

### Engineering tasks not yet done

- Hightouch outbound integration (ADAM → warehouse for performance reporting)
- HMAC request signing on Hightouch endpoint (if Upwork security requires per-row signatures)
- Job queue for >1 sprint/min volume (currently subprocess fire-and-forget)
- Database (Postgres) for sprint state instead of filesystem JSON files
- Object Storage for sprint artifacts (currently filesystem in runs/)
- Repo ownership transfer to CM org or Upwork org

### Things explicitly OUT of scope (for now)

- MCP server move from Fly to Replit (Fly works, leave it)
- The CM creative dashboard (separate project — clip viewer, AI subject swap, storyboarding, likely Luma Labs)
- AWS native deployment (permanently out per May 7 decision)
- MindStudio orchestration (out as of May 2026)

---

## 11. Strategic options on the table (May 26 framing)

Three options for continuing the Upwork engagement, **cumulative**:

### Option 1 — Ship and Integrate
- Lock current pipeline as v1.
- Spend remaining engagement connecting to Hightouch + performance feedback loops.
- 7-style catalog cap. Hard ceiling on creative variety unless a designer joins.
- Lowest cost. Minimal ongoing engineering.

### Option 2 — Ship, Integrate, Expand the Catalog
- Everything in Option 1, plus a dedicated designer (Brandon-equivalent) building out the remaining 17 templates.
- ~1–2 templates per week sustained = full catalog in ~3–4 months.
- Adds designer cost ($5–10K/mo part-time contractor).
- Designer must understand the layer-naming conventions in `template_registry.json`, not just visual craft.

### Option 3 — Ship, Integrate, Expand, Move
- Everything in Option 2, plus motion ad output path (motion-wrap).
- Opens YouTube pre-roll, TikTok in-feed, Reels — placements the current pipeline cannot serve at all.
- Highest leverage: motion typically outperforms static on Meta/Reels/TikTok.
- Brand-consistent motion at scale is hard; locks in real technical differentiation.

### Cross-cutting points to keep in any version

- **Phasing as a feature.** Months 0–2 = Option 1. Decision point. Months 2–6 = Option 2. Decision point. Months 6+ = Option 3 if ROI justifies.
- **Performance feedback is the linchpin.** Without ad performance data feeding back into the system, you can't defend "is this 24th template worth building?" Hightouch (Option 1) is what makes Options 2 and 3 defensible.
- **Operational risk question.** Who runs this six months from now if Logan moves on? Worth scoping maintenance/handover into all three options.

---

## 12. Memory entries that shape behavior

These are stored in `~/.claude/projects/-Users-loganheath-Documents-content-pipeline/memory/`:

### User profile
- Logan Heath, technical lead on ADAM. CM contractor. Hands-on but not Upwork employee.

### Project context
- ADAM pipeline overview, stakeholders, gates
- Brian's no-AI-photos rule
- LLM Gateway requirement (Haresh's team)
- Template status + AWS constraint
- Six-week milestone (May 1 2026)
- Orchestration is MCP server + claude.ai (MindStudio is out)
- Anthropic Enterprise plan (Upwork is on Enterprise)
- CM contracts with Upwork (Blake owns CM)
- MCP server deployment state
- Gate model needs redesign
- Template layer naming decisions
- CM creative dashboard (separate project)
- Replit pivot (May 7)
- Brand library AI history (May 7 Adrie reveal)
- Master CLAUDE.md (May 8)
- Brandon template quirks (May 11)
- Upwork brand palette (May 12)

### Reference
- File locations
- Brand library tag vocabulary

### Behavioral feedback Claude Code has learned
- **No em dashes** — substitute periods, commas, parens, colons
- **Action over planning** — when Logan says "build," produce deliverables; don't gate on more questions
- **Don't ask permission to continue** — skip "want me to..." / "should I proceed?" prompts
- **Destructive git ops pre-authorized in personal repos** — on `loganheath-oss/*`, force push / reset --hard / etc. are pre-authorized

---

## 13. File map (cheat sheet)

```
upwork-creative-pipeline/
├── CLAUDE.md                          Leon's master spec
├── app.py                             FastAPI: form + /submit + /sprints + routers
├── .replit                            Replit run config (port 5000)
├── requirements.txt                   FastAPI, anthropic, google-genai, sse-starlette, etc.
├── pipeline/
│   ├── run_pipeline.py                6-stage runner (entry: --json <order.json>)
│   ├── figma_library.py               Brand-library photo picker
│   ├── 00_intake.py                   Validation (REQUIRED_TOP_LEVEL, VALID_STYLES, etc.)
│   └── inspect_templates.py           Figma template introspector
├── configs/
│   └── template_registry.json         SOURCE OF TRUTH for templates
├── plugin/
│   ├── code.js                        Figma assembler plugin
│   ├── tag_manager/                   Brandon's tag browser plugin
│   └── library_tagger/                Photo library tagger plugin
├── mcp_server/
│   └── server.py                      Fly-hosted MCP server (7 tools)
├── agent/                             Phase 3 native orchestrator
│   ├── tools.py                       7 tools as local Python functions
│   ├── orchestrator.py                Anthropic SDK tool-use loop
│   ├── system_prompt.py               Gate-driving system prompt
│   ├── routes.py                      /chat, /chat/ui, /sprints/{id}/chat
│   ├── chat_ui.html                   Playground chat (sprint-less)
│   └── sprint_chat_ui.html            Sprint-bound chat with gate tabs (DEFAULT)
├── integrations/
│   ├── __init__.py
│   └── hightouch.py                   /integrations/hightouch/brief endpoint
├── order-form/
│   ├── upwork-order-form.html         Legacy 13-style production form
│   ├── order-form-local.html          Modern 24-style form
│   └── fonts/                         PP Neue Montreal woff2 files (8 weights)
├── refs/
│   ├── visual_style_copy_rules.txt    Per-style copy char limits
│   ├── photography_tags_central_list.md
│   └── brandon_template_rules.txt
├── docs/
│   ├── architecture_and_logging.md    Deep infra dive
│   ├── hightouch_integration.md       Spec for Upwork's data team
│   ├── hightouch_sample_brief.json    curl test payload
│   └── PROJECT_HANDOFF.md             THIS FILE
├── runs/<sprint_id>/                  Per-sprint outputs (gitignored)
│   ├── order.json                     Intake artifact
│   ├── pipeline.log                   Subprocess stdout/stderr
│   ├── copy_outputs.json              Gate 3 artifact
│   ├── image_prompts.csv              Gate 4 artifact
│   ├── asset_manifest.csv             Gate 6 artifact
│   └── run_summary.json               Final summary
└── runs/_hightouch_external_id_index.json   Hightouch idempotency map
```

---

## 14. How to resume this conversation

When restarting a Claude Code session:

1. **Read this file first.** `docs/PROJECT_HANDOFF.md` is the full state dump.
2. **Check current git state**: `git log --oneline -5` and `git status` to see what's local vs remote.
3. **Check Repl state** by visiting `/health` on the live Replit URL OR by running `git status` in the Repl shell.
4. **Check what env vars are set in the Repl** via the Secrets panel before doing anything that depends on API keys.
5. **Pick up where the "Current operational state" + "Open decisions" sections leave off.**

### Recent commits on `main`

```
1bc303b  Hightouch integration: inbound brief endpoint + idempotency + spec doc
b588b7c  Form: instant redirect on submit, no popup at all
ad745e6  Sprint-bound chat UX with gate tabs (Phase 3 redesign)
5ffba31  Phase 3 scaffold: native gate orchestration via Claude API
1b16fc4  Phase 2: form submission triggers the pipeline subprocess
8fa5359  Serve the 24-style form (order-form-local.html) by default
05acb50  Snapshot of ADAM creative pipeline (Apr 21 — May 19 work)
```

### Hosting URLs

- GitHub: `https://github.com/loganheath-oss/adam`
- MCP server (Fly): `https://adam-pipeline-cm.fly.dev/mcp`
- Replit: (Logan's personal Repl, URL changes when restored)

### One-command Repl sync

```bash
git fetch origin main && git reset --hard origin/main
```

Run in the Repl's Shell tab. Wipes any Replit Agent drift and matches GitHub exactly.

---

## 15. Working pattern that has proven to work

After several iterations of the Replit Agent diverging from GitHub and causing accumulating bugs, the productive workflow that emerged is:

| Use Claude Code (Logan + me) for | Use Replit Agent for |
|---|---|
| Designing new features | Restarting workflows |
| Multi-file code changes | Setting up Secrets |
| Maintaining cross-file coherence | Diagnosing iframe / cache issues |
| Pushing to GitHub | Tailing logs, running shell commands |
| Architecture and long-context decisions | Replit-native integrations (their DB, auth) |
| Anything that affects more than 1 file | "Try this and see if it works" experiments |

The anti-pattern that hurt the project: asking the Replit Agent to edit code that should live in GitHub. Every such edit diverges the Repl from the canonical source. Hard-resetting the Repl to GitHub is the corrective.

---

End of handoff document.
