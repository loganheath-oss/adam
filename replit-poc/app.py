"""
ADAM Pipeline — Replit POC
==========================
Minimal FastAPI app for proving the order form works hosted on Replit.

Phase 1 (this file): serves the existing order form, accepts submissions,
writes order JSON to disk. Goal is to demo "the form runs in Replit and
looks identical to local" to stakeholders.

Phase 2 (later): subprocess the existing pipeline (`python -m pipeline.run_pipeline`)
on submit, return a sprint_id, poll for status. See README.md for the
larger architecture once this POC is approved.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "upwork-order-form.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ADAM Pipeline — Replit POC")

# Serve the fonts folder so the order form can load PP Neue Montreal.
# Mount at /fonts because the form's CSS uses a relative path (`fonts/...`)
# which resolves to /fonts/... when the form is served from /.
if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the order form HTML."""
    if not ORDER_FORM_PATH.exists():
        return HTMLResponse(
            "<h1>Order form not found</h1>"
            "<p>Drop the <code>order-form/</code> folder from the parent project "
            "into this Repl's root. See README.md.</p>",
            status_code=500,
        )
    return FileResponse(ORDER_FORM_PATH, media_type="text/html")


@app.post("/submit")
async def submit_order(request: Request):
    """Accept an order payload, write it to runs/<sprint_id>/order.json."""
    payload = await request.json()
    sprint_id = (
        payload.get("sprint_id")
        or f"sprint_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(exist_ok=True)
    (sprint_dir / "order.json").write_text(json.dumps(payload, indent=2))
    return JSONResponse(
        {
            "ok": True,
            "sprint_id": sprint_id,
            "stored_at": str(sprint_dir / "order.json"),
            "next_step": "Phase 2 will kick off the pipeline here.",
        }
    )


@app.get("/health")
async def health():
    return {"ok": True, "order_form_present": ORDER_FORM_PATH.exists()}
