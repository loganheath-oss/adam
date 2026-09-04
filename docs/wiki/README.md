# ADAM Wiki — Home

> **ADAM** is the AI-assisted creative production pipeline for Upwork's Paid Acquisition team.
> It takes a brief and produces ad **copy + assembled static creatives** across multiple sizes
> and visual styles — replacing manual concepting and Figma assembly for batch ad production.

This wiki is the **single source of truth** for understanding, running, operating, and inheriting
ADAM. If something here contradicts an older doc (e.g. the root `CLAUDE.md` still mentions Fly/Replit),
**this wiki wins** — see [Known doc drift](#known-doc-drift).

---

## 🗺️ The whole system at a glance

```mermaid
flowchart LR
  U["Operator"] --> FORM["Order form<br/>(web app)"]
  FORM --> PIPE["Pipeline<br/>copy + imagery"]
  PIPE --> MAN["asset_manifest.csv"]
  MAN --> PLUG["Figma plugin<br/>assembles ads"]
  PLUG --> OUT["Finished creatives"]
  PIPE -. inspect .-> DASH["Dashboard<br/>+ Ask ADAM chat"]
  DASH -. approve at gates .-> PIPE
```

## 🚦 Status at a glance

| Thing | State |
|---|---|
| Local pipeline (`run_pipeline.py`) | ✅ Runs end-to-end through all 6 gates |
| Web app (`main.py`: order form + dashboard + chat) | ✅ Deployed on **Railway** (auto-deploy from GitHub) |
| In-app AI chat (`agent/`) | ✅ Live — Claude tool-use loop over sprints + learnings |
| Figma assembly plugin | ✅ Recognizes **all 24** order-form ad types (21 with plugin template mappings); auto-discovers templates; assembles grouped boards |
| Copy generation (Claude) | ✅ **Verified** — generated 30 real concepts on the Railway key (model fixed); local `.env` key is $0 for *local* dev only |
| Admin backend (`/admin`) | ✅ Reliability dashboard (clean-run % + incidents), Issues→Learnings loop, Roles — live July 2026 |
| Per-ad-type copy rules | ✅ Adrie's 24-entry Ad Type Style Guide enforced in code (`configs/ad_type_style_guide.json`) |
| Prospecting / Retargeting | ✅ Differentiated copy per audience; "both" = DISTINCT on-creative AND feed copy per audience (unique Text_On_Visual for Prospecting vs Retargeting) |
| MCP connector (`mcp_server/`) | ✅ Mounted in the web app at `/mcp` — live claude.ai connector reading the current `runs/` (replaced the stale standalone Fly server) |
| Production hardening (LLM Gateway, OAuth, audit) | ⏳ Pending — owned by Upwork eng |

> ✅ **Verified (2026-06-29):** copy-gen produces real, unique copy on the live Railway key — a 5-style test
> sprint generated **30 concepts** (the dead model ID `claude-sonnet-4-20250514` is fixed → `claude-sonnet-5`).
> (Local dev still needs your *own* funded key; the committed local `.env` key is empty.)

---

## 📖 Read in this order

**New to ADAM? Start here:**
1. [What is ADAM](01-what-is-adam.md) — the what, the why, who it's for
2. [Architecture](02-architecture.md) — how the pieces fit, end to end
3. [Repo map](03-repo-map.md) — where every file lives (and what's historical)

**Want to run it / operate it — start with YOUR role:**
- 🧾 [Paid Acquisition](17-role-paid-acquisition.md) — requesting ads. You fill out the order form; that's the whole job.
- ✍️ [Copywriter](18-role-copywriter.md) — running a sprint through the gates. Gate 3 is where your craft enters.
- 🎨 [Designer](19-role-designer.md) — Figma assembly, the plugin, and owning the templates.

The three roles are genuinely separate jobs — Paid Acquisition never runs the tool, and the Figma
half is different work from driving the pipeline. Read your own; skim the others to know who to
hand off to.

**Then the depth, in this order:**
4. [Using ADAM](07-using-adam.md) — the full runbook across all roles (order → gates → Figma → delivery)
5. [The pipeline](04-the-pipeline.md) — stages 00–06 and the gate model
6. [The Figma plugin](05-figma-plugin.md) — assembling creatives from a manifest
7. [The web app & chat](06-the-web-app-and-chat.md) — order form, dashboard, "ask ADAM anything"

**Operating, fixing, owning:**
8. [Deployment & ops](08-deployment-and-ops.md) — Railway, secrets, redeploys
9. [Configuration & references](09-configuration-and-refs.md) — configs/, refs/, registries
10. [Constraints](10-constraints.md) — the non-negotiable guardrails
11. [Troubleshooting](11-troubleshooting.md) — known failures and fixes
12. [FAQ](12-faq.md) · [Glossary](13-glossary.md)
13. [Handoff](14-handoff.md) — stakeholders, ownership, what's left
14. [Decisions log](15-decisions-log.md) — load-bearing history

---

## 🤖 This wiki feeds the chatbot

The "ask the tool any question and get an answer" goal is served by the in-app chat
(`agent/orchestrator.py`). That assistant already reads [`learnings.md`](../../learnings.md)
on every session. **Plan:** this wiki becomes a knowledge source the chat can cite, so a new
team member can ask *"how do I add a new visual style?"* or *"why is copy blank?"* and get a
grounded answer. See [The web app & chat → Making the wiki answerable](06-the-web-app-and-chat.md).

---

## Known doc drift

These are accurate as of this wiki; older docs lag:

- **Hosting is Railway**, not Fly and not Replit. `main.py`'s header still says "Replit entry point"
  and `mcp_server/fly.toml` still exists — both are historical. Replit POC lives in `replit-poc/` (retired).
- **`CLAUDE.md`** (root) is the original master spec. Still useful for decisions/constraints, but its
  "Status / Architectural direction" sections predate the Railway migration and the web-app + chat build.
- **AWS / Terraform** (`terraform/`) is dormant scaffolding — see [Constraints](10-constraints.md) (no native AWS).

> **Maintainers:** when you change how ADAM works, update the relevant wiki page in the same PR.
> A stale wiki is worse than no wiki because the chatbot will repeat it.
