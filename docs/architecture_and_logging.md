# ADAM Pipeline — Architecture & Logging Map

**Last updated:** 2026-04-29
**Owner:** Logan Heath (CM)

This document answers the infosec question *"where is each part of the pipeline running, and where is its activity logged?"* It's intentionally a map, not a system design — code and infrastructure both evolve and this doc is the index.

---

## 1. End-to-end flow

```
Order Form (browser)
   ↓ submit
Backend MCP Server (Fly.io, soon AWS)
   ↓ creates sprint
Claude.ai chat (Adrie's session)
   ↓ drives gates 2–6
   ↓ approve_gate calls back
Backend MCP Server
   ↓ runs pipeline subprocess
Pipeline stages 02–06 (Python on the same backend)
   ↓ writes asset_manifest.csv + Drive output
Slack notification → Brandon
   ↓ Brandon clicks
Figma plugin (Brandon's browser)
   ↓ assembles + polishes
Final CSV → Paid Acq team
```

Today, several of these handoffs are still manual (Slack notifications, the manifest → Brandon, the final CSV). Those gaps are flagged in §4.

---

## 2. Where each component lives

| # | Component | Runs in | Source | Notes |
|---|---|---|---|---|
| 1 | Order form (HTML+JS) | User's browser | `order-form/upwork-order-form.html` | Static page; can be hosted anywhere. POSTs to (3). |
| 2 | Order form data | Fly.io persistent volume `runs_data`, mounted at `/app/runs/{sprint_id}/order.json` | — | Data resides on Fly hardware in San Jose region. |
| 3 | MCP Server (Python) | Fly.io container `adam-pipeline-cm` | `mcp_server/server.py` | HTTP transport at `https://adam-pipeline-cm.fly.dev`. |
| 4 | Pipeline stages 00–06 | Fly.io container (subprocess of the MCP server) | `pipeline/00_intake.py` … `pipeline/06_deliver.py` | Triggered by `approve_gate` MCP tool. |
| 5 | Sprint state files (`order.json`, `copy_outputs.json`, etc.) | Fly.io volume `runs_data` | `runs/{sprint_id}/*` | Persists across container restarts. |
| 6 | LLM calls (Anthropic) | Anthropic's cloud, called from (4) | — | API key in `ANTHROPIC_API_KEY` Fly secret. |
| 7 | Image generation (Gemini / Nano Banana) | Google's cloud, called from (4) | — | API key in `GEMINI_API_KEY` Fly secret. |
| 8 | Photo library (Figma file) | Figma's cloud | — | Read-only via Figma REST API; access token in `FIGMA_ACCESS_TOKEN` Fly secret. |
| 9 | Figma assembly plugin | Brandon's browser, inside Figma | `plugin/code.js`, `plugin/ui.html` | Manual click; cannot be automated by Figma platform design. |
| 10 | Claude.ai chat | Anthropic's cloud (claude.ai) | — | Adrie's authenticated session. Custom MCP connector points to (3). |
| 11 | Project knowledge files (brand voice, legal, etc.) | Anthropic's cloud (Claude Project) | `refs/*.txt`, `refs/photo_library_tags.csv` | Uploaded to the Claude Project. Re-upload when source files change. |
| 12 | Final CSV → Paid Acq | TBD — likely Drive folder or Slack channel | `runs/{sprint_id}/asset_manifest.csv` (interim) | Format/destination not yet defined; awaiting Paid Acq spec. |

---

## 3. Where to look for evidence of activity

| Question | Where to look |
|---|---|
| "Did this order arrive in the system?" | Fly logs: `fly logs --app adam-pipeline-cm` — look for `POST /submit-order` lines. Also: `runs/{sprint_id}/order.json` exists on the volume. |
| "Did Claude call a tool?" | Claude.ai chat history (Adrie's account) shows tool calls inline. Fly logs show the matching `POST /mcp` requests. |
| "What did the pipeline do at gate X?" | `runs/{sprint_id}/generation_log.json` — captures stage timing, model used, prompt size, output length. |
| "Was the LLM call successful?" | Same `generation_log.json` plus the relevant output file (`copy_outputs.json`, `image_prompts.csv`). |
| "Who/what edited a sprint last?" | `runs/{sprint_id}/pipeline_state.json` — has `updated_at` timestamp. Currently no per-user audit trail. |
| "What is the deployed server actually running?" | `fly status --app adam-pipeline-cm` (image hash) and `fly releases --app adam-pipeline-cm` (deployment history). |
| "What secrets are configured?" | `fly secrets list --app adam-pipeline-cm` (names only — values are write-only). |

**Operational logs:** Fly retains stdout/stderr from the container. Anthropic retains API call records (visible via `console.anthropic.com/usage`). Figma retains plugin invocations on file activity logs.

**No formal log aggregation today.** This is acknowledged. The interim answer to "where do I find activity X" is the table above. Production migration to Upwork AWS will route logs to CloudWatch or whatever standard observability stack Upwork uses — that supersedes this section.

---

## 4. Known gaps and what they mean

| Gap | Today | Production target |
|---|---|---|
| Compute hosted by CM (Fly.io), not Upwork | Fly account billed to `logan.heath@cm.studio` | Upwork AWS (Lambda or ECS) deployed by Haresh's team. Same Docker image. |
| LLM traffic direct to Anthropic | Direct API calls from container | Routed through Upwork's internal LLM Gateway |
| Sprint data on Fly volume | `runs_data` volume in San Jose | S3 inside Upwork's AWS, KMS-encrypted |
| Custom connector registered on Logan's personal Max plan | Adrie / team can't access it | Custom connector registered org-wide in Upwork's Anthropic Enterprise |
| No Slack notifications | Manual: Adrie checks chat for new sprints, manually pings Brandon | Webhook on form submit and gate transitions |
| No final CSV format | `asset_manifest.csv` is the interim handoff | Spec to be defined with Paid Acq team |
| No per-user audit trail | Single bearer token = "system" identity | OAuth + per-user identity in production |

---

## 5. Authentication & access

| Surface | How access is controlled |
|---|---|
| Order form | Static HTML — anyone with the URL can submit. Will need form-level auth (Octa SSO) before non-team-internal use. |
| MCP server (`/mcp` and `/submit-order`) | Bearer token via URL query parameter. Single token shared across the form and Adrie's claude.ai connector. |
| Claude.ai chat | Adrie's individual account, authenticated via Octa SSO → claude.ai. |
| Figma | Each user authenticates to Figma directly; plugin runs in their browser session. |
| Slack | Each user's standard Slack workspace login. |

**Important:** the bearer token is *the* secret protecting the backend. If it leaks, anyone who finds the URL can submit orders or trigger pipeline runs. Pre-production hardening: replace with OAuth + short-lived per-user tokens.

---

## 6. Migration path to Upwork AWS

This setup exists to prove the architecture; the production destination is Upwork's AWS account.

**What ships unchanged:** the `mcp_server/` Python code, the `pipeline/` Python code, the Docker image format.

**What gets re-hosted:** the running container moves from Fly.io to AWS Lambda (or ECS). The volume becomes an S3 bucket. The bearer token becomes OAuth. The LLM calls go through Haresh's gateway. The custom connector URL gets re-registered against the new endpoint in Upwork's Anthropic admin console.

**Owner of each migration step:**
- Container deployment: Haresh's team (existing Terraform)
- S3 bucket + KMS: AWS owner at Upwork
- LLM Gateway integration: Haresh + Logan
- OAuth / identity: Upwork platform / IT
- Anthropic connector re-registration: whoever holds Anthropic admin in Upwork's org

---

## 7. Quick links

- Live server: https://adam-pipeline-cm.fly.dev
- Health: https://adam-pipeline-cm.fly.dev/healthz
- Repo: `/Users/loganheath/Documents/upwork-creative-pipeline`
- Order form: `order-form/upwork-order-form.html`
- Pipeline entrypoint: `pipeline/run_pipeline.py`
- MCP server: `mcp_server/server.py`
- Figma plugin: `plugin/`
- Reference docs (uploaded to Claude project): `refs/`
- Photo library tag map: `refs/photo_library_tags.csv`
- This doc: `docs/architecture_and_logging.md`

---

*Updates: when components move, replace the row in §2. When a new gap closes, move it from §4 into §2. This doc should never grow stale by more than one significant change.*
