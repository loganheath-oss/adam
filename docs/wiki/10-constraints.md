# Constraints (the non-negotiables)

These are **hard rules**. Treat them as guardrails when editing code or proposing architecture. (Source:
root `CLAUDE.md` §6, still authoritative for constraints.)

## 1. No AI-generated photography of people
Ratified by **Brian** (Upwork Creative Director), 2026-04-20. People photos come **only** from the approved,
rights-cleared Upwork brand library in Figma. Gemini is approved for **illustrations, abstract graphics,
gradients, UI backgrounds** — not people.
- *Open thread:* whether diffusion **editing** (crop, remove extra people, fix cut-off faces) differs from
  generation. Until Brian rules, the rule stands as-is.

## 2. No native AWS in the architecture
Confirmed by Leon, 2026-05-07. Upwork has no provisioning pipeline for tool infra (no automated
VPC/firewall/peering). **Don't** design anything needing Lambdas, RDS, custom VPCs. Use
platform-provided modules or stand services up inside the app container.
- The `terraform/` dir is dormant scaffolding; Logan has **no apply access**. AWS-side work is Upwork eng's.

## 3. LLM traffic must route through Upwork's internal LLM Gateway in production
Alpha may call Anthropic/Gemini directly (as it does now). **Pre-production:** every LLM call swaps to
gateway calls. Haresh's team owns the gateway and hasn't provided endpoint/key/model values yet.

## 4. Hosting is on CM accounts today, not Upwork
Acceptable for alpha. Production migration is to Upwork-internal infra. (Current host: **Railway**, billed to
CM — note the root `CLAUDE.md` still says Fly; that's stale.)

## 5. MindStudio is out
Finalized May 2026. Don't reference it in any flow. `mindstudio/` is historical only.

## Engineering conventions (also load-bearing)
- **Layered judgment:** rules define boundaries → AI judges inside them → humans veto at gates.
- **Per-style unique layer names** (mountain-peak-with-underscores).
- **Don't add backwards-compat shims** for unused paths — delete cleanly.
- **`pipeline/run_pipeline.py` is the source of truth**; the numbered stage modules lag it.
- **`refs_context.json` is compiled** — edit `refs/` + run `build_refs.py`, never hand-edit.
