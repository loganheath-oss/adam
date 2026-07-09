# ADAM — Complete Source Backup

**ADAM** is an AI-assisted ad-creative production pipeline built for Upwork's Paid
Acquisition team. A marketer submits a brief; ADAM generates ad copy and assembles
finished static creatives across every ad size and visual style — copy + imagery,
on-brand, ready to ship. It replaces manual concepting and Figma assembly for batch
ad production.

This archive is a full source snapshot: the backend, the creative pipeline, the
Figma assembly plugin, and the web app — everything needed to run or rebuild the tool.

## Architecture

- **Backend / API** — `main.py` (FastAPI). Order intake, sprint state, the 6-gate
  approval flow, the in-app "Ask ADAM" chat (a Claude tool-use loop), file serving,
  and admin endpoints. Deployed on Railway.
- **Pipeline** — `pipeline/run_pipeline.py`. The creative engine: load refs →
  generate copy (Claude) → image direction → image production (Gemini) or library
  photo lookup → Figma assembly manifest → deliver. Runs as in-process background
  tasks, pausing at each human-approval gate.
- **Agent** — `agent/` (orchestrator + sprint chat UI). The tool-use loop that
  drives a sprint conversationally and approves gates.
- **Figma plugin** — `plugin/` (`code.js`, `ui.html`, `manifest.json`). Reads the
  assembly manifest, clones the "Meta - Static Grouped" board, and fills text +
  imagery across all sizes and visual styles. Includes auto-fit so copy never clips.
- **Web app** — `web/` (Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui). The full
  front end: landing page, the 3-step order-form wizard + style picker, the sprint
  chat workspace (streaming responses, live gate rail, pipeline narration), a wiki,
  and more. Server-side proxying keeps the API key off the browser. Deployed on
  Railway as a separate service.
- **Configs / refs** — `configs/` (Figma file IDs, template registry, compiled
  brand + legal context), `refs/` (raw brand-voice, legal, and performance references).

## Rebuild / run

**Backend + pipeline (Python):**
```bash
cp .env.example .env    # fill: ANTHROPIC_API_KEY, GEMINI_API_KEY, FIGMA_ACCESS_TOKEN, GOOGLE_SERVICE_ACCOUNT_JSON
python3 -m venv .venv && source .venv/bin/activate
pip install -r mcp_server/requirements.txt   # or: uv sync  (see pyproject.toml / uv.lock)
uvicorn main:app --reload                     # the web API + order form + chat
python3 pipeline/run_pipeline.py --test       # run the pipeline standalone
```

**Web app (Next.js):**
```bash
cd web
npm install
# set ADAM_API_URL + ADAM_API_KEY (pointing at the backend) in .env.local
npm run dev
```

**Figma plugin:** Figma → Plugins → Development → Import plugin from manifest… →
`plugin/manifest.json`.

## Notes

- **No secrets are included.** API keys and service accounts live only in `.env`
  (git-ignored); use `.env.example` as the template.
- **Before publishing any of this publicly**, review `configs/` and `refs/` for
  client-specific or sensitive content.
- Full architecture spec: `CLAUDE.md`. In-app knowledge base: the web app's wiki (`/wiki`).

## Stack

FastAPI · Python · Claude (Anthropic API, tool use) · Gemini · Figma plugin API ·
Next.js 16 · TypeScript · Tailwind v4 · shadcn/ui · Railway.
