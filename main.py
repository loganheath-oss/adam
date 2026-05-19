"""
ADAM Pipeline — Replit entry point
Serves the order form via FastAPI on port 5000.
On form submission, writes order.json and launches the pipeline
as a background subprocess.
"""

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "order-form-local.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
PIPELINE_SCRIPT = BASE_DIR / "pipeline" / "run_pipeline.py"
RUNS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ADAM Pipeline")

if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")


def _write_status(sprint_dir: Path, stage: str, detail: str = ""):
    (sprint_dir / "status.json").write_text(json.dumps({
        "stage": stage,
        "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def _run_pipeline(sprint_id: str, order_path: Path):
    sprint_dir = RUNS_DIR / sprint_id
    _write_status(sprint_dir, "running", "Pipeline started")
    log_path = sprint_dir / "pipeline.log"
    try:
        with open(log_path, "w") as log:
            result = subprocess.run(
                [sys.executable, str(PIPELINE_SCRIPT), "--json", str(order_path)],
                cwd=str(BASE_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=3600,
            )
        if result.returncode == 0:
            _write_status(sprint_dir, "complete", "Pipeline finished successfully")
        else:
            _write_status(sprint_dir, "failed", f"Exit code {result.returncode} — check pipeline.log")
    except subprocess.TimeoutExpired:
        _write_status(sprint_dir, "failed", "Pipeline timed out after 60 minutes")
    except Exception as e:
        _write_status(sprint_dir, "failed", str(e))


def _sprint_summary(sprint_id: str) -> dict:
    sprint_dir = RUNS_DIR / sprint_id
    status_file = sprint_dir / "status.json"
    status = json.loads(status_file.read_text()) if status_file.exists() else {"stage": "unknown"}
    order_file = sprint_dir / "order.json"
    order = json.loads(order_file.read_text()) if order_file.exists() else {}
    outputs = {
        "order": (sprint_dir / "order.json").exists(),
        "context": (sprint_dir / "context.json").exists(),
        "copy_outputs": (sprint_dir / "copy_outputs.json").exists(),
        "image_prompts": (sprint_dir / "image_prompts.csv").exists(),
        "asset_manifest": (sprint_dir / "asset_manifest.csv").exists(),
        "run_summary": (sprint_dir / "run_summary.json").exists(),
    }
    return {
        "sprint_id": sprint_id,
        "status": status,
        "driver": order.get("driver", ""),
        "platform": order.get("platform", ""),
        "outputs": outputs,
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    if not ORDER_FORM_PATH.exists():
        return HTMLResponse(
            "<h1>Order form not found</h1>"
            "<p>Expected at <code>order-form/order-form-local.html</code>.</p>",
            status_code=500,
        )
    return FileResponse(ORDER_FORM_PATH, media_type="text/html")


@app.post("/submit")
async def submit_order(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    sprint_id = (
        payload.get("sprint_id")
        or f"sprint_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(exist_ok=True)
    order_path = sprint_dir / "order.json"
    order_path.write_text(json.dumps(payload, indent=2))
    _write_status(sprint_dir, "queued", "Order received, pipeline starting")
    background_tasks.add_task(_run_pipeline, sprint_id, order_path)
    return JSONResponse({
        "ok": True,
        "sprint_id": sprint_id,
        "status_url": f"/sprints/{sprint_id}",
    })


@app.get("/sprints")
async def list_sprints():
    sprints = []
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            sprints.append(_sprint_summary(d.name))
    return JSONResponse(sprints)


@app.get("/sprints/{sprint_id}")
async def get_sprint(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"error": "Sprint not found"}, status_code=404)
    return JSONResponse(_sprint_summary(sprint_id))


@app.get("/sprints/{sprint_id}/log")
async def get_sprint_log(sprint_id: str):
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    if not log_path.exists():
        return JSONResponse({"error": "Log not found"}, status_code=404)
    return HTMLResponse(
        f"<pre style='font-family:monospace;font-size:12px;white-space:pre-wrap'>{log_path.read_text()}</pre>"
    )


@app.get("/health")
async def health():
    return {"ok": True, "order_form_present": ORDER_FORM_PATH.exists()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
