"""
ADAM Pipeline — Replit entry point
Serves the order form via FastAPI on port 5000.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "upwork-order-form.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ADAM Pipeline — Replit POC")

if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")


@app.get("/", response_class=HTMLResponse)
async def root():
    if not ORDER_FORM_PATH.exists():
        return HTMLResponse(
            "<h1>Order form not found</h1>"
            "<p>Expected at <code>order-form/upwork-order-form.html</code>.</p>",
            status_code=500,
        )
    return FileResponse(ORDER_FORM_PATH, media_type="text/html")


@app.post("/submit")
async def submit_order(request: Request):
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
