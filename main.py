"""
ADAM Pipeline — Replit entry point
Serves the order form, runs the pipeline, and provides a sprint dashboard.
"""

import asyncio
import csv
import hashlib
import hmac
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).parent
ORDER_FORM_PATH = BASE_DIR / "order-form" / "order-form-local.html"
FONTS_DIR = BASE_DIR / "order-form" / "fonts"
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

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
}

app = FastAPI(title="ADAM Pipeline")

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
        "sprint_id": sprint_id, "state": "queued",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    asyncio.create_task(_run_pipeline_task(payload))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "status_url": f"/sprints/{sprint_id}"})


@app.post("/sprints/{sprint_id}/approve/{gate_num}")
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
</div>
</body>
</html>""")


@app.get("/sprints/{sprint_id}", response_class=HTMLResponse)
async def sprint_detail(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return HTMLResponse("<h1>Sprint not found</h1>", status_code=404)

    s = _sprint_data(sprint_id)

    def _badge(state):
        if state == "complete": return "#d1fae5", "#065f46"
        if state == "error": return "#fee2e2", "#991b1b"
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

    if s["state"] == "error":
        gate_section = f"""
        <div style="margin:24px 0;padding:16px;background:#fee2e2;border:1px solid #fca5a5;border-radius:8px">
          <div style="font-weight:600;color:#991b1b;margin-bottom:4px">Pipeline Error</div>
          <div style="font-size:13px;color:#7f1d1d">{s['error'] or 'Unknown error — check the log.'}</div>
        </div>"""

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
</div>

<script>
async function approveGate(num) {{
  const btn = document.querySelector('button[onclick^="approveGate"]');
  const msg = document.getElementById('gate-msg');
  if (btn) {{ btn.disabled = true; btn.textContent = 'Approving…'; }}
  try {{
    const r = await fetch('/sprints/{sprint_id}/approve/' + num, {{method:'POST'}});
    const d = await r.json();
    if (d.ok) {{
      if (msg) msg.textContent = 'Pipeline resumed — refreshing…';
      setTimeout(() => location.reload(), 2000);
    }} else {{
      if (msg) msg.textContent = 'Error: ' + (d.error || 'unknown');
      if (btn) {{ btn.disabled = false; btn.textContent = 'Retry'; }}
    }}
  }} catch(e) {{
    if (msg) msg.textContent = 'Network error';
    if (btn) {{ btn.disabled = false; }}
  }}
}}
</script>
</body>
</html>""")


@app.get("/sprints/{sprint_id}/copy")
async def sprint_copy(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    copy_path = sprint_dir / "copy_outputs.json"
    if not copy_path.exists():
        return JSONResponse({"ok": False, "error": "copy_outputs.json not yet available — pipeline has not reached Stage 02"}, status_code=404)
    data = json.loads(copy_path.read_text())
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "copy_outputs": data})


@app.get("/sprints/{sprint_id}/manifest")
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


@app.get("/sprints/{sprint_id}/files/{filename:path}")
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


@app.get("/sprints/{sprint_id}/log", response_class=HTMLResponse)
async def sprint_log(sprint_id: str):
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    content = log_path.read_text() if log_path.exists() else "(no log yet)"
    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Log — {sprint_id}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;font-size:12px;padding:24px;line-height:1.6}}
pre{{white-space:pre-wrap;word-break:break-all}}</style></head>
<body><pre>{content}</pre></body></html>""")


@app.get("/api/sprints")
async def api_sprints():
    sprints = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                sprints.append(_sprint_data(d.name))
    return JSONResponse({"ok": True, "sprints": sprints})


@app.get("/api/sprints/{sprint_id}")
async def api_sprint(sprint_id: str):
    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return JSONResponse({"ok": False, "error": "Sprint not found"}, status_code=404)
    return JSONResponse({"ok": True, **_sprint_data(sprint_id)})


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

    if ref != "refs/heads/main":
        return JSONResponse({"ok": True, "message": f"Ignored push to {ref}"})

    print(f"[webhook] Push to main by {pusher} — syncing from GitHub…")
    asyncio.create_task(_do_sync_and_restart(pusher))
    return JSONResponse({"ok": True, "message": "Sync triggered"})


async def _do_sync_and_restart(pusher: str = "webhook"):
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
        else:
            print(f"[webhook] Sync failed (exit {result.returncode}):\n{result.stderr}")
            return
    except Exception as exc:
        print(f"[webhook] Sync error: {exc}")
        return

    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
