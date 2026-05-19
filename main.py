"""
ADAM Pipeline — Replit entry point
Serves the order form via FastAPI on port 5000.
On form submission, writes order.json and launches the pipeline
as a background task.
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "order-form-local.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(BASE_DIR / "pipeline"))
from run_pipeline import run_pipeline_auto

app = FastAPI(title="ADAM Pipeline — Replit POC")

if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")


def _generate_sprint_id(payload: dict) -> str:
    """Generate a sprint ID matching the pipeline's format: YYYY-MM-{platform}-{uid}."""
    platform_raw = (payload.get("batches") or [{}])[0].get("platform", "unknown")
    platform_slug = (
        platform_raw.lower()
        .replace(" / ", "-")
        .replace("/", "-")
        .replace(" ", "-")
        .replace("3rd-party", "affiliate")
    )
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:4]
    return f"{now.strftime('%Y-%m')}-{platform_slug}-{uid}"


async def _run_pipeline_task(payload: dict):
    """Run the pipeline in a thread pool so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    sprint_id = payload.get("sprint_id", "unknown")
    sprint_dir = RUNS_DIR / sprint_id

    def _write_state(state: str, error: str = ""):
        data = {
            "sprint_id": sprint_id,
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            data["error"] = error
        (sprint_dir / "pipeline_state.json").write_text(json.dumps(data, indent=2))

    _write_state("running")
    try:
        result = await loop.run_in_executor(None, run_pipeline_auto, payload)
        if result is None:
            _write_state("error", "Pipeline failed at intake — check order payload for validation errors")
    except Exception as exc:
        _write_state("error", str(exc))


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
async def submit_order(request: Request):
    payload = await request.json()

    sprint_id = payload.get("sprint_id") or _generate_sprint_id(payload)
    payload["sprint_id"] = sprint_id

    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(exist_ok=True)

    (sprint_dir / "order.json").write_text(json.dumps(payload, indent=2))
    (sprint_dir / "pipeline_state.json").write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": "queued",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    asyncio.create_task(_run_pipeline_task(payload))

    return JSONResponse({
        "ok": True,
        "sprint_id": sprint_id,
        "status_url": f"/sprints/{sprint_id}",
        "message": f"Pipeline started. Poll /sprints/{sprint_id} for status.",
    })


@app.get("/sprints/{sprint_id}/log")
async def get_sprint_log(sprint_id: str):
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    if not log_path.exists():
        return JSONResponse({"error": "Log not found"}, status_code=404)
    return HTMLResponse(
        f"<pre style='font-family:monospace;font-size:12px;white-space:pre-wrap'>{log_path.read_text()}</pre>"
    )


@app.get("/sprints/{sprint_id}")
async def get_sprint_status(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)

    state_path = sprint_dir / "pipeline_state.json"
    if state_path.exists():
        pipeline_state = json.loads(state_path.read_text())
    else:
        pipeline_state = {"state": "unknown"}

    result = {
        "ok": True,
        "sprint_id": sprint_id,
        "state": pipeline_state.get("state", "unknown"),
        "updated_at": pipeline_state.get("updated_at"),
    }

    if pipeline_state.get("error"):
        result["error"] = pipeline_state["error"]

    summary_path = sprint_dir / "run_summary.json"
    if summary_path.exists():
        result["summary"] = json.loads(summary_path.read_text())

    outputs = {}
    for fname in ["order.json", "context.json", "copy_outputs.json"]:
        if (sprint_dir / fname).exists():
            outputs[fname] = True
    for fname in ["asset_manifest.csv", "copy_review.csv", "image_prompts.csv"]:
        if (sprint_dir / fname).exists():
            outputs[fname] = True
    if outputs:
        result["outputs"] = outputs

    return JSONResponse(result)


@app.get("/sprints")
async def list_sprints():
    sprints = []
    for sprint_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not sprint_dir.is_dir():
            continue
        state_path = sprint_dir / "pipeline_state.json"
        state = "unknown"
        if state_path.exists():
            data = json.loads(state_path.read_text())
            state = data.get("state", "unknown")
        sprints.append({"sprint_id": sprint_dir.name, "state": state})
    return JSONResponse({"ok": True, "sprints": sprints})


@app.get("/health")
async def health():
    return {"ok": True, "order_form_present": ORDER_FORM_PATH.exists()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
