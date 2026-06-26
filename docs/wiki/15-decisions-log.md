# Decisions log

Load-bearing decisions that shape how to read the code or extend it. Newest first. (Seeded from root
`CLAUDE.md` §8 plus this build's decisions; keep appending as you go.)

## This build (2026-06)
- **Hosting moved to Railway** (from Fly/Replit). Auto-deploys from GitHub `loganheath-oss/adam`; local repo
  kept in sync. Replit retired (`replit-poc/`).
- **Plugin/template work brought in-house** — ship live, no branch-for-review. Plugin made fully
  config-driven and **auto-discovers templates document-wide** (no Capture step, no template picking).
- **All 21 templates recognized** (verified 21/21, 0 failures). Multi-field copy-gen added for Us vs Them,
  Sticky Note, Pie Chart.
- **Testimonial rewired** to the content-bearing `Template_TestimonialC` in "Adtype: Testimonial Variants";
  **Chat Bubble CTA** un-skipped.
- **Documentation = this wiki** under `docs/wiki/`; `CLAUDE.md` demoted to historical spec for status/hosting.

## Earlier (from CLAUDE.md)
- **2026-05-07 — Replit selected as target platform** *(since superseded by Railway).* Build portable: no
  native AWS, container-internal services.
- **2026-05-07 — Diffusion-editing rule reopened** — bring evidence to Brian on edit-vs-generate.
- **2026-05-07 — Linear integration not pursued.**
- **2026-04-30 — Per-style unique layer names** (mountain-peak-with-underscores).
- **2026-04-30 — Gate model needs redesign** — 6→5 gates; conditional Gemini-QA gate for library-fed sprints.
  Don't refactor in-flight.
- **2026-04-29 — Anthropic Enterprise confirmed** — unlocks custom MCP connectors for the Upwork org
  (admin escalation still needed to register).
- **2026-04-28 — Copy generation curated in Adrie's Claude Project** — re-upload `refs/*` when sources change.
- **2026-04-20 — Brian's no-AI-photo rule ratified** — people photos = library only.

## Open questions
- Diffusion **editing** vs generation (Brian to rule).
- Final delivery format from Figma to the Paid Acq team (currently `asset_manifest.csv` + assembled frames).
- `runs/` persistence model on Railway (volume vs DB/blob).

> How to use this page: when you make a decision that future-you would need to know to read the code
> correctly, add a dated line at the top of "This build."
