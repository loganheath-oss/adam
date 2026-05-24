"""
ADAM Pipeline — Replit entry point
Serves the order form, runs the pipeline, and provides a sprint dashboard.
"""

import asyncio
import csv
import hashlib
import hmac
import html
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, Security
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from agent.routes import router as agent_router

BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "order-form-local.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)
SYNC_LOG_PATH = BASE_DIR / "sync_log.jsonl"

sys.path.insert(0, str(BASE_DIR / "pipeline"))
from run_pipeline import run_pipeline_auto, resume_gate_2, resume_gate_3, resume_gate_4, resume_gate_5, resume_gate_6

GATE_HANDLERS = {2: resume_gate_2, 3: resume_gate_3, 4: resume_gate_4, 5: resume_gate_5, 6: resume_gate_6}

GATE_LABELS = {
    "awaiting_gate_2": {"num": 2, "label": "Order + Refs Review", "action": "Confirm order and refs"},
    "awaiting_gate_3": {"num": 3, "label": "Copy Review",         "action": "Approve copy concepts"},
    "awaiting_gate_4": {"num": 4, "label": "Image Prompt Scan",   "action": "Approve image prompts"},
    "awaiting_gate_5": {"num": 5, "label": "Assembly Review",     "action": "Approve images & assembly"},
    "awaiting_gate_6": {"num": 6, "label": "Final QA",            "action": "Mark sprint complete"},
}

STAGE_LABELS = {
    "queued":                   "Queued",
    "running":                  "Running",
    "stage_01_load_refs":       "Stage 1 — Loading refs",
    "stage_02_copy_gen":        "Stage 2 — Generating copy",
    "stage_03_image_prompts":   "Stage 3 — Building image prompts",
    "stage_04_generate_images": "Stage 4 — Generating images",
    "stage_05_figma_assembly":  "Stage 5 — Figma assembly",
    "stage_06_deliver":         "Stage 6 — Delivering",
    "complete":                 "Complete",
    "error":                    "Error",
    "interrupted":              "Interrupted",
}

INTERRUPTED_STATES = {"queued", "running"}

# ── Auth ──────────────────────────────────────────────────────────────────────
_SESSION_COOKIE = "pipeline_sess"
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query  = APIKeyQuery(name="api_key",    auto_error=False)


def _configured_key() -> str:
    return os.environ.get("PIPELINE_API_KEY", "")


def _session_token(api_key: str) -> str:
    """Derive a stable, verifiable session token from the API key."""
    return hmac.new(api_key.encode(), b"pipeline-session-v1", hashlib.sha256).hexdigest()


def _valid_session(cookie_value: str | None) -> bool:
    key = _configured_key()
    if not key or not cookie_value:
        return False
    return hmac.compare_digest(_session_token(key), cookie_value)


SYNC_LOG_MAX_ENTRIES = 500


def _append_sync_log(pusher: str, sha: str, status: str, detail: str = "") -> None:
    """Append one JSONL line to sync_log.jsonl, keeping at most SYNC_LOG_MAX_ENTRIES entries."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pusher": pusher,
        "sha": sha[:12] if sha else "",
        "status": status,
        "detail": detail[:500] if detail else "",
    }
    with SYNC_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    lines = SYNC_LOG_PATH.read_text(encoding="utf-8").splitlines()
    valid_lines = [l for l in lines if l.strip()]
    if len(valid_lines) > SYNC_LOG_MAX_ENTRIES:
        trimmed = valid_lines[-SYNC_LOG_MAX_ENTRIES:]
        SYNC_LOG_PATH.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def _read_sync_log(limit: int = 50) -> list[dict]:
    """Return the last `limit` sync log entries, newest first."""
    if not SYNC_LOG_PATH.exists():
        return []
    lines = SYNC_LOG_PATH.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return list(reversed(entries[-limit:]))


def _count_sync_log() -> dict:
    """Return total, ok, and error counts from sync_log.jsonl in a single pass."""
    if not SYNC_LOG_PATH.exists():
        return {"total": 0, "ok": 0, "errors": 0}
    total = ok = errors = 0
    for line in SYNC_LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            entry = json.loads(line)
            if entry.get("status") == "ok":
                ok += 1
            else:
                errors += 1
        except json.JSONDecodeError:
            errors += 1
    return {"total": total, "ok": ok, "errors": errors}


def _sync_mini_panel() -> str:
    """Return HTML for the compact recent-syncs panel shown on the sprints dashboard."""
    entries = _read_sync_log(5)
    if not entries:
        return ""
    counts = _count_sync_log()
    rows = ""
    for e in entries:
        status = e.get("status", "")
        dot_color = "#16a34a" if status == "ok" else "#dc2626"
        ts = e.get("ts", "").replace("T", " ").replace("+00:00", " UTC")[:19] + " UTC"
        pusher = html.escape(e.get("pusher", "—"))
        sha = html.escape(e.get("sha", "—"))
        detail = html.escape(e.get("detail", ""))
        detail_txt = detail[:60] + ("…" if len(detail) > 60 else "") if detail else ""
        rows += f"""<tr>
          <td style="padding:6px 14px;font-size:11px;color:#6b7280;white-space:nowrap">{ts}</td>
          <td style="padding:6px 14px;font-size:12px;font-weight:600">{pusher}</td>
          <td style="padding:6px 14px;font-family:monospace;font-size:11px">{sha}</td>
          <td style="padding:6px 14px;font-size:11px"><span style="color:{dot_color};font-weight:700">{"✓" if status=="ok" else "✗"} {status}</span></td>
          <td style="padding:6px 14px;font-size:11px;color:#6b7280;font-family:monospace">{detail_txt}</td>
        </tr>"""
    ok_count = counts["ok"]
    err_count = counts["errors"]
    return f"""<div style="margin-top:28px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
    <span style="font-size:12px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:0.05em">Recent GitHub Syncs</span>
    <a href="/sync-log" style="font-size:12px;color:#14a800;text-decoration:none">View all →</a>
  </div>
  <div style="margin-bottom:10px;font-size:12px;color:#6b7280">
    <span style="color:#16a34a;font-weight:600">{ok_count} ok</span>
    <span style="margin:0 4px">/</span>
    <span style="color:#dc2626;font-weight:600">{err_count} error{"s" if err_count != 1 else ""}</span>
    <span style="color:#9ca3af;margin-left:2px">total</span>
  </div>
  <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)">
    <thead><tr style="background:#f9fafb;border-bottom:1px solid #e5e7eb">
      <th style="padding:7px 14px;text-align:left;font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">Time</th>
      <th style="padding:7px 14px;text-align:left;font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">Pusher</th>
      <th style="padding:7px 14px;text-align:left;font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">SHA</th>
      <th style="padding:7px 14px;text-align:left;font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">Status</th>
      <th style="padding:7px 14px;text-align:left;font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">Detail</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


async def require_api_key(
    header_key: str | None = Security(_api_key_header),
    query_key:  str | None = Security(_api_key_query),
) -> None:
    """Dependency: rejects requests that don't supply a valid API key.

    Accepted as either:
      • HTTP header  X-API-Key: <key>
      • Query param  ?api_key=<key>

    If PIPELINE_API_KEY is not configured the server returns 503 so operators
    know setup is incomplete rather than silently letting requests through.
    """
    configured = _configured_key()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="PIPELINE_API_KEY secret is not configured on this server.",
        )
    provided = header_key or query_key or ""
    if not hmac.compare_digest(configured, provided):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. "
                   "Supply it via the X-API-Key header or ?api_key= query param.",
        )


async def require_api_key_or_session(
    request: Request,
    header_key: str | None = Security(_api_key_header),
    query_key:  str | None = Security(_api_key_query),
) -> None:
    """Dependency: accepts a valid API key (header/query) OR a valid browser session cookie.

    Used for action endpoints (approve, retry) so the browser UI can call them
    after the user has authenticated via the inline auth form, without the API
    key ever being present in client-side HTML.
    """
    configured = _configured_key()
    if not configured:
        raise HTTPException(status_code=503, detail="PIPELINE_API_KEY secret is not configured.")
    provided = header_key or query_key or ""
    if provided and hmac.compare_digest(configured, provided):
        return
    cookie = request.cookies.get(_SESSION_COOKIE, "")
    if _valid_session(cookie):
        return
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key. Supply via X-API-Key header, ?api_key= param, or log in via the browser.",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup, mark any in-flight sprints as interrupted."""
    if RUNS_DIR.exists():
        for d in RUNS_DIR.iterdir():
            if not d.is_dir():
                continue
            state_path = d / "pipeline_state.json"
            if not state_path.exists():
                continue
            try:
                state_data = json.loads(state_path.read_text())
                if state_data.get("state") in INTERRUPTED_STATES:
                    state_data["state"] = "interrupted"
                    state_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    state_data["interrupted_reason"] = "Server restarted while pipeline was in progress"
                    state_path.write_text(json.dumps(state_data, indent=2))
            except Exception:
                pass
    yield


app = FastAPI(title="ADAM Pipeline", lifespan=lifespan)
app.include_router(agent_router, dependencies=[Depends(require_api_key)])

if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _generate_sprint_id(payload: dict) -> str:
    platform_raw = (payload.get("batches") or [{}])[0].get("platform", "unknown")
    platform_slug = (
        platform_raw.lower()
        .replace(" / ", "-").replace("/", "-").replace(" ", "-").replace("3rd-party", "affiliate")
    )
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:4]
    return f"{now.strftime('%Y-%m')}-{platform_slug}-{uid}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _sprint_data(sprint_id: str) -> dict:
    d = RUNS_DIR / sprint_id
    state_raw = _load_json(d / "pipeline_state.json")
    order = _load_json(d / "order.json")
    summary = _load_json(d / "run_summary.json")
    state = state_raw.get("state", "unknown")
    outputs = {
        f: (d / f).exists()
        for f in ["order.json", "context.json", "copy_outputs.json",
                  "copy_review.csv", "image_prompts.csv", "asset_manifest.csv", "run_summary.json"]
    }
    gate_info = GATE_LABELS.get(state)
    return {
        "sprint_id": sprint_id,
        "state": state,
        "state_label": STAGE_LABELS.get(state, state),
        "updated_at": state_raw.get("updated_at", ""),
        "error": state_raw.get("error", ""),
        "interrupted_reason": state_raw.get("interrupted_reason", ""),
        "driver": order.get("driver", ""),
        "platform": order.get("platform", ""),
        "targeting": order.get("targeting", ""),
        "delivery_date": order.get("delivery_date", ""),
        "summary": summary,
        "outputs": outputs,
        "gate": gate_info,
        "order": order,
    }


async def _run_pipeline_task(payload: dict):
    loop = asyncio.get_event_loop()
    sprint_id = payload.get("sprint_id", "unknown")
    sprint_dir = RUNS_DIR / sprint_id

    def _write_state(state: str, error: str = ""):
        data = {"sprint_id": sprint_id, "state": state, "updated_at": datetime.now(timezone.utc).isoformat()}
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


async def _run_gate_task(sprint_id: str, gate_num: int):
    loop = asyncio.get_event_loop()
    handler = GATE_HANDLERS[gate_num]
    try:
        await loop.run_in_executor(None, handler, sprint_id)
    except Exception as exc:
        sprint_dir = RUNS_DIR / sprint_id
        (sprint_dir / "pipeline_state.json").write_text(json.dumps({
            "sprint_id": sprint_id, "state": "error",
            "error": str(exc),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    if not ORDER_FORM_PATH.exists():
        return HTMLResponse("<h1>Order form not found</h1><p>Expected at <code>order-form/order-form-local.html</code>.</p>", status_code=500)
    return FileResponse(
        ORDER_FORM_PATH,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/submit")
async def submit_order(request: Request):
    payload = await request.json()
    sprint_id = payload.get("sprint_id") or _generate_sprint_id(payload)
    payload["sprint_id"] = sprint_id
    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(exist_ok=True)
    (sprint_dir / "order.json").write_text(json.dumps(payload, indent=2))
    (sprint_dir / "pipeline_state.json").write_text(json.dumps({
        "sprint_id": sprint_id, "state": "queued",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    asyncio.create_task(_run_pipeline_task(payload))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "status_url": f"/sprints/{sprint_id}"})


@app.post("/sprints/{sprint_id}/approve/{gate_num}", dependencies=[Depends(require_api_key_or_session)])
async def approve_gate(sprint_id: str, gate_num: int):
    if gate_num not in GATE_HANDLERS:
        return JSONResponse({"ok": False, "error": f"Unknown gate {gate_num}. Valid: 2–6"}, status_code=400)
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    state_path = sprint_dir / "pipeline_state.json"
    pipeline_state = _load_json(state_path)
    current_state = pipeline_state.get("state", "unknown")
    expected_state = f"awaiting_gate_{gate_num}"
    if current_state != expected_state:
        raise HTTPException(
            status_code=409,
            detail=f"Sprint is in state '{current_state}', expected '{expected_state}'",
        )
    state_path.write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": f"resuming_gate_{gate_num}",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    asyncio.create_task(_run_gate_task(sprint_id, gate_num))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "gate": gate_num, "message": f"Gate {gate_num} approved, pipeline resuming"})


@app.post("/sprints/{sprint_id}/retry", dependencies=[Depends(require_api_key_or_session)])
async def retry_sprint(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    state_path = sprint_dir / "pipeline_state.json"
    pipeline_state = _load_json(state_path)
    current_state = pipeline_state.get("state", "unknown")
    if current_state != "interrupted":
        raise HTTPException(
            status_code=409,
            detail=f"Sprint is in state '{current_state}', expected 'interrupted'",
        )
    order_path = sprint_dir / "order.json"
    if not order_path.exists():
        return JSONResponse({"ok": False, "error": "order.json not found — cannot retry"}, status_code=400)
    payload = _load_json(order_path)
    payload["sprint_id"] = sprint_id
    state_path.write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": "queued",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    asyncio.create_task(_run_pipeline_task(payload))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "message": "Sprint re-queued from interrupted state"})


@app.get("/sprints", response_class=HTMLResponse)
async def sprints_dashboard():
    sprints = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                sprints.append(_sprint_data(d.name))

    def _badge(state):
        colors = {
            "complete": ("#d1fae5", "#065f46"),
            "error": ("#fee2e2", "#991b1b"),
            "interrupted": ("#fce7f3", "#9d174d"),
            "running": ("#dbeafe", "#1e40af"),
            "queued": ("#f3f4f6", "#374151"),
        }
        for key, (bg, fg) in colors.items():
            if key in state:
                return bg, fg
        if "awaiting" in state:
            return ("#fef9c3", "#854d0e")
        return ("#f3f4f6", "#374151")

    rows = ""
    for s in sprints:
        bg, fg = _badge(s["state"])
        gate_btn = ""
        if s["gate"]:
            g = s["gate"]
            gate_btn = f'<a href="/sprints/{s["sprint_id"]}" style="display:inline-block;margin-left:10px;padding:4px 12px;background:#14a800;color:#fff;border-radius:4px;font-size:11px;text-decoration:none;font-weight:600;">Review →</a>'
        rows += f"""
        <tr onclick="location.href='/sprints/{s['sprint_id']}'" style="cursor:pointer">
          <td style="padding:12px 16px;font-size:12px;color:#6b7280">{s['updated_at'][:16].replace('T',' ') if s['updated_at'] else '—'}</td>
          <td style="padding:12px 16px;font-weight:600;font-size:13px">{s['sprint_id']}</td>
          <td style="padding:12px 16px;font-size:13px">{s['driver'] or '—'}</td>
          <td style="padding:12px 16px;font-size:13px">{s['platform'] or '—'}</td>
          <td style="padding:12px 16px">
            <span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">{s['state_label']}</span>
            {gate_btn}
          </td>
        </tr>"""

    empty = '<tr><td colspan="5" style="padding:40px;text-align:center;color:#9ca3af;font-size:14px">No sprints yet — submit an order to get started</td></tr>' if not sprints else ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADAM Pipeline — Sprints</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111827}}
  .nav{{background:#fff;border-bottom:1px solid #e5e7eb;padding:0 24px;display:flex;align-items:center;gap:24px;height:52px}}
  .nav-logo{{font-weight:700;font-size:15px;letter-spacing:0.05em;color:#14a800}}
  .nav a{{font-size:13px;color:#6b7280;text-decoration:none;padding:4px 10px;border-radius:4px}}
  .nav a:hover{{background:#f3f4f6;color:#111}}
  .container{{max-width:1100px;margin:0 auto;padding:32px 24px}}
  h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
  .sub{{font-size:13px;color:#6b7280;margin-bottom:24px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  thead tr{{background:#f9fafb;border-bottom:1px solid #e5e7eb}}
  th{{padding:10px 16px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;letter-spacing:0.05em;text-transform:uppercase}}
  tbody tr{{border-bottom:1px solid #f3f4f6}}
  tbody tr:last-child{{border-bottom:none}}
  tbody tr:hover{{background:#f9fafb}}
  .refresh{{float:right;padding:6px 14px;background:#fff;border:1px solid #d1d5db;border-radius:6px;font-size:12px;cursor:pointer;color:#374151}}
  .refresh:hover{{background:#f9fafb}}
</style>
</head>
<body>
<nav class="nav">
  <span class="nav-logo">ADAM Pipeline</span>
  <a href="/">Order Form</a>
  <a href="/sprints" style="color:#111;font-weight:600">Sprints</a>
  <a href="/sync-log">Sync Log</a>
</nav>
<div class="container">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <h1>Sprint Runs</h1>
    <button class="refresh" onclick="location.reload()">↻ Refresh</button>
  </div>
  <p class="sub">{len(sprints)} sprint{"s" if len(sprints)!=1 else ""} · click any row to view details</p>
  <table>
    <thead><tr><th>Time</th><th>Sprint ID</th><th>Driver</th><th>Platform</th><th>Status</th></tr></thead>
    <tbody>{rows}{empty}</tbody>
  </table>
  <div id="sync-mini-panel">{_sync_mini_panel()}</div>
</div>
<script>
(function() {{
  var INTERVAL = 30000;
  function refresh() {{
    fetch('/sprints/sync-panel')
      .then(function(r) {{ return r.text(); }})
      .then(function(html) {{
        var el = document.getElementById('sync-mini-panel');
        if (el) el.innerHTML = html;
      }})
      .catch(function() {{}});
  }}
  setInterval(refresh, INTERVAL);
}})();
</script>
</body>
</html>""")


_SPRINT_CHAT_UI = BASE_DIR / "agent" / "sprint_chat_ui.html"


@app.get("/sprints/sync-panel", response_class=HTMLResponse)
async def sprints_sync_panel():
    """Return just the sync mini-panel fragment for polling refreshes."""
    return HTMLResponse(_sync_mini_panel())


@app.get("/sprints/{sprint_id}/chat", response_class=HTMLResponse)
async def sprint_chat_ui(sprint_id: str):
    """Sprint-bound chat UI — public (no API key required, sprint_id is the access token)."""
    if not _SPRINT_CHAT_UI.exists():
        return HTMLResponse("<h1>sprint_chat_ui.html not found</h1>", status_code=500)
    return HTMLResponse(_SPRINT_CHAT_UI.read_text().replace("__SPRINT_ID__", sprint_id))


@app.post("/sprints/{sprint_id}/chat/stream")
async def sprint_chat_stream(sprint_id: str, request: Request):
    """SSE endpoint for the sprint-bound chat UI — public."""
    from agent.orchestrator import run_agent_turn

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    body = await request.json()
    messages = body.get("messages", [])

    if not api_key:
        async def _no_key():
            yield 'data: {"type":"text","text":"⚠️ ANTHROPIC_API_KEY is not configured. Ask the server admin to add it as a Replit secret."}\n\n'
            yield 'data: {"type":"done"}\n\n'
        return StreamingResponse(_no_key(), media_type="text/event-stream")

    async def _stream():
        try:
            async for chunk in run_agent_turn(messages, api_key, sprint_id=sprint_id):
                yield chunk
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/sprints/{sprint_id}/auth")
async def sprint_auth(sprint_id: str, request: Request, response: Response):
    """Browser login: validate API key submitted via form, set session cookie, redirect."""
    form = await request.form()
    api_key = (form.get("api_key") or "").strip()
    configured = _configured_key()
    if not configured:
        return HTMLResponse("PIPELINE_API_KEY is not configured on this server.", status_code=503)
    if not hmac.compare_digest(configured, api_key):
        return RedirectResponse(url=f"/sprints/{sprint_id}?auth_error=1", status_code=303)
    redirect = RedirectResponse(url=f"/sprints/{sprint_id}", status_code=303)
    redirect.set_cookie(
        key=_SESSION_COOKIE,
        value=_session_token(configured),
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return redirect


@app.get("/sprints/{sprint_id}", response_class=HTMLResponse)
async def sprint_detail(sprint_id: str, request: Request, auth_error: str = ""):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return HTMLResponse("<h1>Sprint not found</h1>", status_code=404)

    # Show inline auth form if not logged in via session cookie
    if not _valid_session(request.cookies.get(_SESSION_COOKIE)):
        err_msg = '<p style="color:#dc2626;font-size:13px;margin-bottom:12px">Incorrect key — try again.</p>' if auth_error else ""
        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADAM — {sprint_id}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.box{{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.1);padding:32px;width:100%;max-width:360px}}
h2{{font-size:16px;font-weight:700;margin-bottom:4px}}
.sub{{font-size:13px;color:#6b7280;margin-bottom:20px}}
input{{width:100%;padding:9px 12px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;margin-bottom:12px}}
button{{width:100%;padding:10px;background:#14a800;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer}}
</style></head>
<body><div class="box">
  <h2>ADAM Pipeline</h2>
  <p class="sub">Enter your API key to view this sprint.</p>
  {err_msg}
  <form method="POST" action="/sprints/{sprint_id}/auth">
    <input type="password" name="api_key" placeholder="API key" autofocus required>
    <button type="submit">Continue</button>
  </form>
</div></body></html>""")

    s = _sprint_data(sprint_id)

    def _badge(state):
        if state == "complete": return "#d1fae5", "#065f46"
        if state == "error": return "#fee2e2", "#991b1b"
        if state == "interrupted": return "#fce7f3", "#9d174d"
        if "awaiting" in state: return "#fef9c3", "#854d0e"
        if state in ("running", "queued") or state.startswith("stage_"): return "#dbeafe", "#1e40af"
        return "#f3f4f6", "#374151"

    bg, fg = _badge(s["state"])

    # Gate approval button
    gate_section = ""
    if s["gate"]:
        g = s["gate"]
        gate_section = f"""
        <div style="margin:24px 0;padding:20px;background:#fffbeb;border:1px solid #fcd34d;border-radius:8px">
          <div style="font-weight:600;font-size:14px;color:#92400e;margin-bottom:6px">⏸ Awaiting Gate {g['num']}: {g['label']}</div>
          <div style="font-size:13px;color:#78350f;margin-bottom:14px">Review the outputs below, then approve to continue the pipeline.</div>
          <button onclick="approveGate({g['num']})"
            style="padding:10px 24px;background:#14a800;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer">
            ✓ {g['action']}
          </button>
          <span id="gate-msg" style="margin-left:12px;font-size:12px;color:#6b7280"></span>
        </div>"""

    if s["state"] == "interrupted":
        reason = s.get("interrupted_reason") or "The server restarted while this pipeline was in progress."
        gate_section = f"""
        <div style="margin:24px 0;padding:20px;background:#fdf2f8;border:1px solid #f0abdb;border-radius:8px">
          <div style="font-weight:600;font-size:14px;color:#9d174d;margin-bottom:6px">⚠ Pipeline Interrupted</div>
          <div style="font-size:13px;color:#831843;margin-bottom:14px">{reason}</div>
          <button onclick="retrySprint()"
            style="padding:10px 24px;background:#9d174d;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer">
            ↺ Retry from beginning
          </button>
          <span id="retry-msg" style="margin-left:12px;font-size:12px;color:#6b7280"></span>
        </div>"""

    if s["state"] == "error":
        gate_section = f"""
        <div style="margin:24px 0;padding:16px;background:#fee2e2;border:1px solid #fca5a5;border-radius:8px">
          <div style="font-weight:600;color:#991b1b;margin-bottom:4px">Pipeline Error</div>
          <div style="font-size:13px;color:#7f1d1d">{s['error'] or 'Unknown error — check the log.'}</div>
        </div>"""

    # Sync-overlap notice
    sync_notice = ""
    order_json_path = sprint_dir / "order.json"
    if order_json_path.exists():
        sprint_start_ts = order_json_path.stat().st_mtime
        sprint_start_dt = datetime.fromtimestamp(sprint_start_ts, tz=timezone.utc)
        recent_syncs = _read_sync_log(1)
        if recent_syncs:
            latest_sync = recent_syncs[0]
            sync_ts_str = latest_sync.get("ts", "")
            try:
                sync_dt = datetime.fromisoformat(sync_ts_str.replace("Z", "+00:00"))
                if sync_dt > sprint_start_dt:
                    display_time = sync_dt.strftime("%Y-%m-%d %H:%M UTC")
                    sync_notice = f"""
                    <div style="margin-bottom:20px;padding:14px 18px;background:#fefce8;border:1px solid #fde047;border-radius:8px;display:flex;align-items:center;gap:10px">
                      <span style="font-size:15px;flex-shrink:0">⚠</span>
                      <span style="font-size:13px;color:#854d0e">Code was synced at <strong>{display_time}</strong> — this run may have been affected.&nbsp;<a href="/sync-log" style="color:#713f12;font-weight:600;text-decoration:underline">View sync log →</a></span>
                    </div>"""
            except Exception:
                pass

    # Outputs table
    out_rows = ""
    file_links = {
        "order.json": "Order",
        "context.json": "Ref Context",
        "copy_outputs.json": "Copy Concepts",
        "copy_review.csv": "Copy Review CSV",
        "image_prompts.csv": "Image Prompts CSV",
        "asset_manifest.csv": "Asset Manifest",
        "run_summary.json": "Run Summary",
    }
    for fname, label in file_links.items():
        exists = s["outputs"].get(fname, False)
        icon = "✓" if exists else "·"
        color = "#065f46" if exists else "#9ca3af"
        link = f'<a href="/sprints/{sprint_id}/files/{fname}" target="_blank" style="color:#1d4ed8;font-size:12px">download</a>' if exists else '<span style="font-size:12px;color:#d1d5db">—</span>'
        out_rows += f'<tr><td style="padding:8px 16px;font-size:13px;color:{color}">{icon} {label}</td><td style="padding:8px 16px">{link}</td></tr>'

    # Order summary
    order = s["order"]
    batches = order.get("batches", [{}])
    batch = batches[0] if batches else {}
    styles = batch.get("visual_styles", [])
    brief = order.get("brief", "")

    summary_rows = ""
    for k, v in [("Driver", s["driver"]), ("Platform", s["platform"]), ("Targeting", s["targeting"]),
                  ("Delivery", s["delivery_date"]), ("Styles", ", ".join(styles) if styles else "—"),
                  ("Brief", (brief[:120] + "…") if len(brief) > 120 else brief or "—")]:
        summary_rows += f'<tr><td style="padding:6px 16px;font-size:12px;color:#6b7280;width:120px">{k}</td><td style="padding:6px 16px;font-size:13px">{v}</td></tr>'

    run_sum = s["summary"]
    summary_stat = ""
    if run_sum:
        summary_stat = f"""
        <div style="display:flex;gap:16px;margin:16px 0">
          <div style="padding:12px 20px;background:#f0fdf4;border-radius:6px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:#14a800">{run_sum.get('total_assets',0)}</div>
            <div style="font-size:11px;color:#6b7280">Assets</div>
          </div>
          <div style="padding:12px 20px;background:#eff6ff;border-radius:6px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:#1d4ed8">{run_sum.get('concepts_selected',0)}</div>
            <div style="font-size:11px;color:#6b7280">Concepts</div>
          </div>
          <div style="padding:12px 20px;background:#fefce8;border-radius:6px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:#854d0e">{run_sum.get('images_generated',0)}</div>
            <div style="font-size:11px;color:#6b7280">Images</div>
          </div>
        </div>"""

    # ── Copy Concepts ─────────────────────────────────────────────────────────
    copy_section = ""
    def _e(v):
        """HTML-escape a value from an untrusted file."""
        return html.escape(str(v) if v is not None else "")

    copy_path = sprint_dir / "copy_outputs.json"
    if copy_path.exists():
        try:
            copy_data = json.loads(copy_path.read_text())
            concepts = copy_data.get("concepts", [])
            concept_cards = ""
            for c in concepts:
                selected = c.get("selected", False)
                score = c.get("score", "")
                headline = _e(c.get("headline", "—"))
                body = str(c.get("body", c.get("body_long", "")))
                body_preview = _e((body[:180] + "…") if len(body) > 180 else body)
                concept_id = _e(c.get("concept_id", ""))
                style = _e(c.get("visual_style", c.get("concept_tag", "")))
                sel_bg = "#d1fae5" if selected else "#fee2e2"
                sel_fg = "#065f46" if selected else "#991b1b"
                sel_label = "Selected" if selected else "Rejected"
                score_html = f'<span style="background:#f3f4f6;color:#374151;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">Score {_e(score)}</span> ' if score else ""
                concept_cards += f"""
                <div style="padding:14px 16px;border-bottom:1px solid #f3f4f6">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
                    <span style="font-weight:600;font-size:13px">{headline}</span>
                    <span style="background:{sel_bg};color:{sel_fg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{sel_label}</span>
                    {score_html}
                    <span style="font-size:11px;color:#9ca3af;margin-left:auto">{concept_id}</span>
                  </div>
                  <div style="font-size:12px;color:#6b7280;line-height:1.5">{body_preview or '—'}</div>
                  {"" if not style else f'<div style="margin-top:4px;font-size:11px;color:#9ca3af">{style}</div>'}
                </div>"""
            n_sel = sum(1 for c in concepts if c.get("selected"))
            copy_section = f"""
            <div class="card">
              <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
                <span>Copy Concepts</span>
                <span style="font-weight:400;font-size:11px;color:#9ca3af">{n_sel} selected / {len(concepts)} total · <a href="/sprints/{sprint_id}/files/copy_outputs.json" target="_blank" style="color:#1d4ed8">download</a></span>
              </div>
              {concept_cards or '<div style="padding:16px;font-size:13px;color:#9ca3af">No concepts found.</div>'}
            </div>"""
        except Exception as exc:
            copy_section = f'<div class="card"><div style="padding:16px;font-size:13px;color:#991b1b">Could not parse copy_outputs.json: {_e(exc)}</div></div>'

    # ── Asset Manifest ────────────────────────────────────────────────────────
    manifest_section = ""
    manifest_path = sprint_dir / "asset_manifest.csv"
    if manifest_path.exists():
        try:
            manifest_rows_data = []
            with manifest_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    manifest_rows_data.append(dict(row))
            if manifest_rows_data:
                # Detect columns flexibly (case-insensitive key lookup)
                sample = manifest_rows_data[0]
                col_assetid = next((k for k in sample if "asset_id" in k.lower()), "asset_id")
                col_platform = next((k for k in sample if k.lower() == "platform"), "Platform")
                col_format = next((k for k in sample if k.lower() == "format"), "Format")
                col_style = next((k for k in sample if "style" in k.lower()), "Visual_Style")
                col_status = next((k for k in sample if k.lower() == "status"), "status")
                col_headline = next((k for k in sample if "headline" in k.lower()), "Headline")
                mf_rows = ""
                for r in manifest_rows_data:
                    status_raw = r.get(col_status, "").strip().lower()
                    status_display = _e(r.get(col_status, ""))
                    st_bg = "#d1fae5" if status_raw == "delivered" else "#fef9c3"
                    st_fg = "#065f46" if status_raw == "delivered" else "#854d0e"
                    mf_rows += f"""<tr>
                      <td style="padding:8px 12px;font-size:12px;color:#374151;font-family:monospace">{_e(r.get(col_assetid,''))}</td>
                      <td style="padding:8px 12px;font-size:12px">{_e(r.get(col_platform,''))}</td>
                      <td style="padding:8px 12px;font-size:12px">{_e(r.get(col_format,''))}</td>
                      <td style="padding:8px 12px;font-size:12px">{_e(r.get(col_style,''))}</td>
                      <td style="padding:8px 12px;font-size:12px">{_e(r.get(col_headline,'')[:60])}</td>
                      <td style="padding:8px 12px"><span style="background:{st_bg};color:{st_fg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{status_display}</span></td>
                    </tr>"""
                delivered = sum(1 for r in manifest_rows_data if r.get(col_status, "").strip().lower() == "delivered")
                manifest_section = f"""
                <div class="card">
                  <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
                    <span>Asset Manifest</span>
                    <span style="font-weight:400;font-size:11px;color:#9ca3af">{delivered} delivered / {len(manifest_rows_data)} total · <a href="/sprints/{sprint_id}/files/asset_manifest.csv" target="_blank" style="color:#1d4ed8">download</a></span>
                  </div>
                  <div style="overflow-x:auto">
                  <table style="min-width:600px">
                    <thead><tr style="background:#f9fafb;border-bottom:1px solid #e5e7eb">
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Asset ID</th>
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Platform</th>
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Format</th>
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Style</th>
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Headline</th>
                      <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;font-weight:600">Status</th>
                    </tr></thead>
                    <tbody>{mf_rows}</tbody>
                  </table>
                  </div>
                </div>"""
        except Exception as exc:
            manifest_section = f'<div class="card"><div style="padding:16px;font-size:13px;color:#991b1b">Could not parse asset_manifest.csv: {_e(exc)}</div></div>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADAM — {sprint_id}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111827}}
  .nav{{background:#fff;border-bottom:1px solid #e5e7eb;padding:0 24px;display:flex;align-items:center;gap:24px;height:52px}}
  .nav-logo{{font-weight:700;font-size:15px;letter-spacing:0.05em;color:#14a800}}
  .nav a{{font-size:13px;color:#6b7280;text-decoration:none;padding:4px 10px;border-radius:4px}}
  .nav a:hover{{background:#f3f4f6;color:#111}}
  .container{{max-width:900px;margin:0 auto;padding:32px 24px}}
  .card{{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:20px;overflow:hidden}}
  .card-head{{padding:14px 16px;border-bottom:1px solid #f3f4f6;font-size:12px;font-weight:600;color:#6b7280;letter-spacing:0.05em;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse}}
  tbody tr:not(:last-child){{border-bottom:1px solid #f9fafb}}
</style>
</head>
<body>
<nav class="nav">
  <span class="nav-logo">ADAM Pipeline</span>
  <a href="/">Order Form</a>
  <a href="/sprints">Sprints</a>
  <span style="font-size:13px;color:#111;font-weight:600">› {sprint_id}</span>
</nav>
<div class="container">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
    <h1 style="font-size:20px;font-weight:700">{sprint_id}</h1>
    <span style="background:{bg};color:{fg};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600">{s['state_label']}</span>
    <a href="/sprints/{sprint_id}/log" target="_blank" style="margin-left:auto;font-size:12px;color:#6b7280;text-decoration:none">View log →</a>
  </div>

  {sync_notice}
  {gate_section}
  {summary_stat}

  <div class="card">
    <div class="card-head">Order Details</div>
    <table><tbody>{summary_rows}</tbody></table>
  </div>

  <div class="card">
    <div class="card-head">Pipeline Outputs</div>
    <table><tbody>{out_rows}</tbody></table>
  </div>

  {copy_section}
  {manifest_section}
</div>

<script>
async function approveGate(num) {{
  const btn = document.querySelector('button[onclick^="approveGate"]');
  const msg = document.getElementById('gate-msg');
  if (btn) {{ btn.disabled = true; btn.textContent = 'Approving…'; }}
  try {{
    const r = await fetch('/sprints/{sprint_id}/approve/' + num, {{method:'POST', credentials:'same-origin'}});
    const d = await r.json();
    if (d.ok) {{
      if (msg) msg.textContent = 'Pipeline resumed — refreshing…';
      setTimeout(() => location.reload(), 2000);
    }} else {{
      if (msg) msg.textContent = 'Error: ' + (d.error || d.detail || 'unknown');
      if (btn) {{ btn.disabled = false; btn.textContent = 'Retry'; }}
    }}
  }} catch(e) {{
    if (msg) msg.textContent = 'Network error';
    if (btn) {{ btn.disabled = false; }}
  }}
}}
async function retrySprint() {{
  const btn = document.querySelector('button[onclick="retrySprint()"]');
  const msg = document.getElementById('retry-msg');
  if (btn) {{ btn.disabled = true; btn.textContent = 'Re-queuing…'; }}
  try {{
    const r = await fetch('/sprints/{sprint_id}/retry', {{method:'POST', credentials:'same-origin'}});
    const d = await r.json();
    if (d.ok) {{
      if (msg) msg.textContent = 'Sprint re-queued — refreshing…';
      setTimeout(() => location.reload(), 2000);
    }} else {{
      if (msg) msg.textContent = 'Error: ' + (d.error || d.detail || 'unknown');
      if (btn) {{ btn.disabled = false; btn.textContent = '↺ Retry from beginning'; }}
    }}
  }} catch(e) {{
    if (msg) msg.textContent = 'Network error';
    if (btn) {{ btn.disabled = false; }}
  }}
}}
</script>
</body>
</html>""")


@app.get("/sprints/{sprint_id}/copy", dependencies=[Depends(require_api_key)])
async def sprint_copy(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    copy_path = sprint_dir / "copy_outputs.json"
    if not copy_path.exists():
        return JSONResponse({"ok": False, "error": "copy_outputs.json not yet available — pipeline has not reached Stage 02"}, status_code=404)
    data = json.loads(copy_path.read_text())
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "copy_outputs": data})


@app.get("/sprints/{sprint_id}/manifest", dependencies=[Depends(require_api_key)])
async def sprint_manifest(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    manifest_path = sprint_dir / "asset_manifest.csv"
    if not manifest_path.exists():
        return JSONResponse({"ok": False, "error": "asset_manifest.csv not yet available — pipeline has not completed Stage 06"}, status_code=404)
    rows = []
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "count": len(rows), "assets": rows})


@app.get("/sprints/{sprint_id}/files/{filename:path}", dependencies=[Depends(require_api_key)])
async def sprint_file(sprint_id: str, filename: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"error": "Sprint not found"}, status_code=404)
    # Resolve path and guard against directory traversal
    try:
        target = (sprint_dir / filename).resolve()
        sprint_dir_resolved = sprint_dir.resolve()
        target.relative_to(sprint_dir_resolved)
    except ValueError:
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    if not target.exists() or not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    suffix = target.suffix.lower()
    media_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
        ".log": "text/plain",
    }
    media = media_types.get(suffix, "application/octet-stream")
    return FileResponse(target, media_type=media, filename=target.name)


@app.get("/sprints/{sprint_id}/log", response_class=HTMLResponse, dependencies=[Depends(require_api_key)])
async def sprint_log(sprint_id: str):
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    content = log_path.read_text() if log_path.exists() else "(no log yet)"
    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Log — {sprint_id}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;font-size:12px;padding:24px;line-height:1.6}}
pre{{white-space:pre-wrap;word-break:break-all}}</style></head>
<body><pre>{content}</pre></body></html>""")


@app.get("/api/sprints", dependencies=[Depends(require_api_key)])
async def api_sprints():
    sprints = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                sprints.append(_sprint_data(d.name))
    return JSONResponse({"ok": True, "sprints": sprints})


@app.get("/api/sprints/{sprint_id}", dependencies=[Depends(require_api_key)])
async def api_sprint(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    return JSONResponse({"ok": True, **_sprint_data(sprint_id)})


@app.get("/sync-log", response_class=HTMLResponse, dependencies=[Depends(require_api_key_or_session)])
async def sync_log_page(request: Request):
    entries = _read_sync_log(50)
    counts = _count_sync_log()
    total = counts["total"]
    ok_count = counts["ok"]
    err_count = counts["errors"]

    rows = ""
    for e in entries:
        status = e.get("status", "")
        bg = "#d1fae5" if status == "ok" else "#fee2e2"
        fg = "#065f46" if status == "ok" else "#991b1b"
        label = "ok" if status == "ok" else "error"
        sha = html.escape(e.get("sha", "—"))
        pusher = html.escape(e.get("pusher", "—"))
        ts = html.escape(e.get("ts", "—").replace("T", " ").replace("+00:00", " UTC"))
        detail = html.escape(e.get("detail", ""))
        detail_cell = f'<span title="{detail}" style="font-size:11px;color:#6b7280;font-family:monospace">{detail[:80] + ("…" if len(detail) > 80 else "")}</span>' if detail else "—"
        rows += f"""<tr>
          <td style="padding:10px 16px;font-size:12px;color:#6b7280;white-space:nowrap">{ts}</td>
          <td style="padding:10px 16px;font-size:13px;font-weight:600">{pusher}</td>
          <td style="padding:10px 16px;font-family:monospace;font-size:12px">{sha}</td>
          <td style="padding:10px 16px"><span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">{label}</span></td>
          <td style="padding:10px 16px">{detail_cell}</td>
        </tr>"""

    empty = '<tr><td colspan="5" style="padding:40px;text-align:center;color:#9ca3af;font-size:14px">No syncs recorded yet</td></tr>' if not entries else ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADAM — Sync History</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111827}}
  .nav{{background:#fff;border-bottom:1px solid #e5e7eb;padding:0 24px;display:flex;align-items:center;gap:24px;height:52px}}
  .nav-logo{{font-weight:700;font-size:15px;letter-spacing:0.05em;color:#14a800}}
  .nav a{{font-size:13px;color:#6b7280;text-decoration:none;padding:4px 10px;border-radius:4px}}
  .nav a:hover{{background:#f3f4f6;color:#111}}
  .container{{max-width:1100px;margin:0 auto;padding:32px 24px}}
  h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
  .sub{{font-size:13px;color:#6b7280;margin-bottom:24px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  thead tr{{background:#f9fafb;border-bottom:1px solid #e5e7eb}}
  th{{padding:10px 16px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;letter-spacing:0.05em;text-transform:uppercase}}
  tbody tr{{border-bottom:1px solid #f3f4f6}}
  tbody tr:last-child{{border-bottom:none}}
</style>
</head>
<body>
<nav class="nav">
  <span class="nav-logo">ADAM Pipeline</span>
  <a href="/">Order Form</a>
  <a href="/sprints">Sprints</a>
  <a href="/sync-log" style="color:#111;font-weight:600">Sync Log</a>
</nav>
<div class="container">
  <h1>GitHub Sync History</h1>
  <p class="sub">Showing {len(entries)} of {total} total event{"s" if total != 1 else ""} (capped at {SYNC_LOG_MAX_ENTRIES}) · {ok_count} ok, {err_count} error{"s" if err_count != 1 else ""} · newest first</p>
  <table>
    <thead><tr><th>Time (UTC)</th><th>Pusher</th><th>Commit SHA</th><th>Status</th><th>Detail</th></tr></thead>
    <tbody>{rows}{empty}</tbody>
  </table>
</div>
</body>
</html>""")


@app.get("/health")
async def health():
    return {"ok": True, "order_form_present": ORDER_FORM_PATH.exists()}


@app.post("/github-webhook")
async def github_webhook(request: Request):
    """
    GitHub push webhook. Verifies HMAC-SHA256 signature, runs sync_from_github.sh,
    then restarts the process so new code is picked up immediately.

    GitHub webhook setup:
      Payload URL : https://<your-repl-domain>/github-webhook
      Content type: application/json
      Secret      : value of WEBHOOK_SECRET Replit secret
      Events      : Just the push event
    """
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "")
    if not webhook_secret:
        return JSONResponse({"ok": False, "error": "WEBHOOK_SECRET not configured"}, status_code=503)

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    expected = "sha256=" + hmac.new(
        webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body) if body else {}
    ref = payload.get("ref", "")
    pusher = payload.get("pusher", {}).get("name", "unknown")
    sha = (payload.get("head_commit") or {}).get("id", "")

    if ref != "refs/heads/main":
        return JSONResponse({"ok": True, "message": f"Ignored push to {ref}"})

    print(f"[webhook] Push to main by {pusher} ({sha[:12] or 'no-sha'}) — syncing from GitHub…")
    asyncio.create_task(_do_sync_and_restart(pusher, sha))
    return JSONResponse({"ok": True, "message": "Sync triggered"})


async def _do_sync_and_restart(pusher: str = "webhook", sha: str = ""):
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["bash", str(BASE_DIR / "sync_from_github.sh")],
                capture_output=True, text=True, timeout=120,
            ),
        )
        if result.returncode == 0:
            print(f"[webhook] Sync complete. Restarting process…")
            print(result.stdout)
            _append_sync_log(pusher, sha, "ok", result.stdout.strip())
        else:
            detail = result.stderr.strip() or result.stdout.strip()
            print(f"[webhook] Sync failed (exit {result.returncode}):\n{detail}")
            _append_sync_log(pusher, sha, "error", f"exit {result.returncode}: {detail}")
            return
    except Exception as exc:
        print(f"[webhook] Sync error: {exc}")
        _append_sync_log(pusher, sha, "error", str(exc))
        return

    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
