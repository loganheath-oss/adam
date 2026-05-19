"""
ADAM Pipeline — FastAPI app for Replit hosting
==============================================
Phase 2: serves the order form, accepts submissions, and kicks off the
existing run_pipeline.py as a background subprocess. Sprint state is
readable via GET /sprints/<id>, which inspects on-disk artifacts written
by the pipeline stages (order.json → copy_outputs.json → image_prompts.csv
→ asset_manifest.csv → run_summary.json).

Gates remain driven by claude.ai (via the MCP server) — this app just
wires the form to the pipeline so an end-to-end Replit-hosted run is
possible without leaving the browser.
"""

import asyncio
import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Phase 3: gate orchestrator (chat UI + Claude tool-use loop).
# Lazy import inside the include so the rest of the app still boots
# if the anthropic SDK isn't installed yet.
try:
    from agent.routes import router as agent_router
except Exception as _agent_import_err:  # noqa: F841
    agent_router = None


BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "order-form-local.html"
LEGACY_FORM_PATH = BASE_DIR / "order-form" / "upwork-order-form.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
PIPELINE_SCRIPT = BASE_DIR / "pipeline" / "run_pipeline.py"

RUNS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ADAM Pipeline")

if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")

if agent_router is not None:
    app.include_router(agent_router)


# ── Pipeline subprocess launcher ────────────────────────────────────────────

async def _launch_pipeline(sprint_id: str, order_json_path: Path) -> None:
    """Spawn `python pipeline/run_pipeline.py --json <order>` as a detached
    subprocess. We don't await it — pipeline runs take minutes. Status is
    surfaced through the artifacts the pipeline writes into runs/<sprint_id>/.
    """
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    log_handle = log_path.open("w", buffering=1)
    log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] starting pipeline for {sprint_id}\n")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(PIPELINE_SCRIPT),
            "--json",
            str(order_json_path),
            cwd=str(BASE_DIR),
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ},
        )
        log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] pid={proc.pid}\n")
    except Exception as e:
        log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] FAILED TO LAUNCH: {e}\n")
        log_handle.close()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    if not ORDER_FORM_PATH.exists():
        return HTMLResponse(
            f"<h1>Order form not found at {ORDER_FORM_PATH}</h1>",
            status_code=500,
        )
    return FileResponse(ORDER_FORM_PATH, media_type="text/html")


@app.post("/submit")
async def submit_order(request: Request):
    """Accept an order payload, persist it, and fire off the pipeline."""
    payload = await request.json()
    sprint_id = (
        payload.get("sprint_id")
        or f"sprint_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(exist_ok=True)
    order_path = sprint_dir / "order.json"
    order_path.write_text(json.dumps(payload, indent=2))

    pipeline_started = False
    pipeline_error: Optional[str] = None
    if PIPELINE_SCRIPT.exists():
        try:
            asyncio.create_task(_launch_pipeline(sprint_id, order_path))
            pipeline_started = True
        except Exception as e:
            pipeline_error = str(e)
    else:
        pipeline_error = f"pipeline script not found at {PIPELINE_SCRIPT}"

    return JSONResponse(
        {
            "ok": True,
            "sprint_id": sprint_id,
            "stored_at": str(order_path),
            "pipeline_started": pipeline_started,
            "pipeline_error": pipeline_error,
            "status_url": f"/sprints/{sprint_id}",
        }
    )


# ── Status / inspection ─────────────────────────────────────────────────────

_STAGE_ARTIFACTS = [
    ("00_intake", "order.json"),
    ("01_refs", "context.json"),
    ("02_copy", "copy_outputs.json"),
    ("03_image_prompts", "image_prompts.csv"),
    ("06_deliver", "asset_manifest.csv"),
    ("final", "run_summary.json"),
]


def _stage_status(sprint_dir: Path) -> list[dict]:
    out = []
    for stage, fname in _STAGE_ARTIFACTS:
        p = sprint_dir / fname
        out.append({
            "stage": stage,
            "artifact": fname,
            "complete": p.exists(),
            "modified": (
                datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
                if p.exists()
                else None
            ),
        })
    return out


def _read_manifest(sprint_dir: Path) -> list[dict]:
    manifest_path = sprint_dir / "asset_manifest.csv"
    if not manifest_path.exists():
        return []
    with manifest_path.open() as f:
        return list(csv.DictReader(f))


@app.get("/sprints/{sprint_id}")
async def sprint_status(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail=f"sprint {sprint_id} not found")

    summary_path = sprint_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None

    log_path = sprint_dir / "pipeline.log"
    log_tail = ""
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        log_tail = "\n".join(lines[-40:])

    manifest = _read_manifest(sprint_dir)

    return {
        "sprint_id": sprint_id,
        "stages": _stage_status(sprint_dir),
        "manifest_row_count": len(manifest),
        "manifest_sample": manifest[:3],
        "summary": summary,
        "log_tail": log_tail,
    }


@app.get("/sprints")
async def list_sprints():
    if not RUNS_DIR.exists():
        return {"sprints": []}
    items = []
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        order_path = d / "order.json"
        items.append({
            "sprint_id": d.name,
            "has_order": order_path.exists(),
            "has_manifest": (d / "asset_manifest.csv").exists(),
            "modified": datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"sprints": items[:50]}


@app.get("/legacy", response_class=HTMLResponse)
async def legacy_form():
    if not LEGACY_FORM_PATH.exists():
        return HTMLResponse("<h1>Legacy form not found</h1>", status_code=404)
    return FileResponse(LEGACY_FORM_PATH, media_type="text/html")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "order_form_present": ORDER_FORM_PATH.exists(),
        "legacy_form_present": LEGACY_FORM_PATH.exists(),
        "pipeline_script_present": PIPELINE_SCRIPT.exists(),
        "runs_dir": str(RUNS_DIR),
    }
