# ADAM Pipeline — Replit POC

Goal: prove the order form runs hosted on Replit, looks identical to local, and accepts submissions. Once approved, expand to the full Replit migration plan (storage abstraction, review UI, MCP server hosting).

## Setup (~10 minutes)

### 1. Create the Repl

1. Go to replit.com (use your personal account for the demo; ownership can transfer to a CM/Upwork workspace later).
2. Click **Create Repl**.
3. Pick the **Python** template (any recent version is fine).
4. Name it `adam-pipeline-poc` or similar.

### 2. Copy in the scaffold files

From this folder (`upwork-creative-pipeline/replit-poc/`), drag these into your new Repl's root:

- `app.py`
- `requirements.txt`
- `.replit`
- `README.md` (this file, for reference)

### 3. Copy the order form

From `upwork-creative-pipeline/order-form/`, drag the entire `order-form/` folder into the Repl's root. This brings:

- `upwork-order-form.html` (the form itself, with Brandon's fonts/colors/logo/glimmer)
- `order-form-local.html` (the 24-style local variant, optional)
- `fonts/` (PP Neue Montreal woff2 files)

The Repl root should now look like:

```
adam-pipeline-poc/
├── app.py
├── requirements.txt
├── .replit
├── README.md
└── order-form/
    ├── upwork-order-form.html
    ├── order-form-local.html
    └── fonts/
        └── PPNeueMontreal-*.woff2
```

### 4. Install dependencies

Replit auto-detects `requirements.txt`. If it doesn't install on first run, open the Shell tab and run:

```bash
pip install -r requirements.txt
```

### 5. Click Run

The .replit config starts uvicorn on port 8000. Replit's webview will pop open with the order form rendered.

Public URL will be something like `https://adam-pipeline-poc.<your-username>.repl.co` — that's the link to share with stakeholders.

## What to demo

- Load the form — confirm Neue Montreal, brand greens, glimmer, Upwork logo all look identical to local.
- Fill in a fake order and submit. Submission lands at `runs/<sprint_id>/order.json` (visible in the Files panel).
- Hit `/health` to confirm the server sees the form.

## Phase 2 (after stakeholder sign-off)

Drop the `pipeline/`, `configs/`, `refs/`, and `mcp_server/` folders into the Repl. Add to `app.py`:

- `POST /submit` shells out to `python -m pipeline.run_pipeline --json runs/<id>/order.json` as a background task
- `GET /sprints/<id>` returns manifest + status
- Mount the MCP server (`mcp_server.server.mcp.streamable_http_app()`) at `/mcp` so claude.ai connectors keep working

See the May 8 architecture sketch (in conversation memory) for the full migration: storage abstraction (Postgres + Object Storage), SSO, review UI.

## What this POC deliberately does NOT do

- Run the pipeline (Phase 2).
- Authenticate users (SSO / password — add when leaving the demo).
- Persist beyond the Repl's filesystem (storage abstraction comes with Phase 2).
- Mount the MCP server (Phase 2).

Keep it small to validate the path quickly. Don't let scope creep slow the demo.

## Common gotchas

- **Fonts don't load**: confirm the `order-form/fonts/` folder made it into the Repl. The app mounts `/order-form/fonts` as a static directory.
- **Port complaints**: Replit picks the external port. The `.replit` config maps internal 8000 → external 80. Don't hardcode URLs.
- **Slow first load**: Replit cold-starts the container. Subsequent loads are fast.
- **Webview blank**: open the Shell and re-run `uvicorn app:app --host 0.0.0.0 --port 8000`. The .replit config should do this automatically on Run.
