"""
ADAM Pipeline — Replit entry point
Serves the order form, runs the pipeline, and provides a sprint dashboard.
"""

import asyncio
import csv
import hashlib
import io
import tempfile
import zipfile
import hmac
import html
import json
import logging
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, Security
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
from run_pipeline import run_full_pipeline, run_pipeline_auto, resume_gate_2, resume_gate_3, resume_gate_4, resume_gate_5, resume_gate_6

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
        dot_color = "var(--good)" if status == "ok" else "var(--bad)"
        ts = e.get("ts", "").replace("T", " ").replace("+00:00", " UTC")[:19] + " UTC"
        pusher = html.escape(e.get("pusher", "—"))
        sha = html.escape(e.get("sha", "—"))
        detail = html.escape(e.get("detail", ""))
        detail_txt = detail[:60] + ("…" if len(detail) > 60 else "") if detail else ""
        rows += f"""<tr>
          <td style="padding:8px 14px;font-size:11px;color:var(--ink-mid);white-space:nowrap;font-variant-numeric:tabular-nums">{ts}</td>
          <td style="padding:8px 14px;font-size:12px;color:var(--ink)">{pusher}</td>
          <td style="padding:8px 14px;font-size:11px;letter-spacing:.02em;font-variant-numeric:tabular-nums">{sha}</td>
          <td style="padding:8px 14px;font-size:11px"><span style="color:{dot_color}">{"✓" if status=="ok" else "✗"} {status}</span></td>
          <td style="padding:8px 14px;font-size:11px;color:var(--ink-mid)">{detail_txt}</td>
        </tr>"""
    ok_count = counts["ok"]
    err_count = counts["errors"]
    return f"""<div style="margin-top:32px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
    <span style="font-size:11px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.12em">Recent GitHub Syncs</span>
    <a href="/sync-log" style="font-size:12px;color:var(--brand-green)">View all →</a>
  </div>
  <div style="margin-bottom:12px;font-size:12px;color:var(--ink-mid)">
    <span style="color:var(--good-fg)">{ok_count} ok</span>
    <span style="margin:0 5px;color:var(--ink-dim)">/</span>
    <span style="color:var(--bad-fg)">{err_count} error{"s" if err_count != 1 else ""}</span>
    <span style="color:var(--ink-dim);margin-left:3px">total</span>
  </div>
  <div style="background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-xl);overflow:hidden;box-shadow:var(--shadow-soft-sm)">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:var(--hover);border-bottom:1px solid var(--rule)">
      <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em">Time</th>
      <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em">Pusher</th>
      <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em">SHA</th>
      <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em">Status</th>
      <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em">Detail</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
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

STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── SHARED UI SHELL ────────────────────────────────────────────────────────────
# The ADAM design system lives in /static/adam-design.css and is documented in
# /DESIGN.md. These helpers render the shared <head> and nav bar so every
# server-rendered (f-string) page stays consistent. Static HTML files
# (order form, chat/finals UIs) inline the equivalent markup — keep them in sync
# with nav_html() below; DESIGN.md is the canonical reference.

# Nav links: (href, label, key). `key` matches the `active` argument.
_NAV_LINKS = [
    ("/new", "New Order", "new"),
    ("/sprints", "Sprints", "sprints"),
    ("/sync-log", "Sync Log", "sync"),
    ("/learnings", "Learnings", "learnings"),
]


def nav_html(active: str = "") -> str:
    """Shared ADAM nav bar. `active` is one of: new, sprints, sync, learnings."""
    links = "".join(
        '<a href="{}"{}>{}</a>'.format(
            href, ' class="active"' if key == active else "", label
        )
        for href, label, key in _NAV_LINKS
    )
    return (
        '<nav class="adam-nav">'
        '<a class="adam-nav-brand" href="/" aria-label="ADAM home">'
        '<span class="adam-logo">ADAM<b>.</b></span>'
        '<span class="adam-sub">Upwork Paid Acquisition</span>'
        '</a>'
        f'<div class="adam-nav-links">{links}</div>'
        '</nav>'
    )


def page_head(title: str, extra_css: str = "") -> str:
    """Shared <head> + opening <body>. Links the design system; pages add their
    own page-local <style> via `extra_css` (a full <style>…</style> block)."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{title}</title>'
        '<link rel="stylesheet" href="/static/adam-design.css">'
        f'{extra_css}'
        '</head><body><div class="adam-wash" aria-hidden="true"></div>'
    )


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _generate_sprint_id(payload: dict) -> str:
    platform_raw = (payload.get("batches") or [{}])[0].get("platform", "unknown")
    platform_slug = (
        platform_raw.lower()
        .replace(" / ", "-").replace("/", "-").replace(" ", "-").replace("3rd-party", "affiliate")
    )
    now = datetime.now(timezone.utc)
    # 12 hex chars = 48 bits of randomness. Sprint IDs are the bearer token
    # for public chat + download endpoints, so we need them to be hard to
    # guess by external parties. (Existing 4-char IDs remain valid because
    # _SPRINT_ID_RE accepts any length up to 128.)
    uid = uuid.uuid4().hex[:12]
    return f"{now.strftime('%Y-%m')}-{platform_slug}-{uid}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


# ── sprint_id safety + concurrent-safe JSONL append ──────────────────────────
_SPRINT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_JSONL_LOCK = threading.Lock()
_LOG = logging.getLogger("adam.main")


def _validate_sprint_id(sprint_id: str) -> str:
    """Reject sprint IDs that could escape RUNS_DIR. Returns the validated id."""
    if not sprint_id or not _SPRINT_ID_RE.match(sprint_id) or ".." in sprint_id:
        raise HTTPException(status_code=400, detail="Invalid sprint_id format")
    return sprint_id


def _safe_sprint_dir(sprint_id: str) -> Path:
    """Validate sprint_id format AND verify the resolved path stays inside RUNS_DIR."""
    _validate_sprint_id(sprint_id)
    candidate = (RUNS_DIR / sprint_id).resolve()
    runs_resolved = RUNS_DIR.resolve()
    try:
        candidate.relative_to(runs_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="sprint_id escapes runs directory")
    return candidate


def _append_jsonl_safe(path: Path, record: dict) -> bool:
    """Append a JSON record to a JSONL file with a process-level lock. Returns success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _JSONL_LOCK:
            with path.open("a") as f:
                f.write(json.dumps(record) + "\n")
        return True
    except Exception as exc:
        _LOG.warning("jsonl append failed for %s: %s", path, exc)
        return False


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
        # Use the gated pipeline so the run pauses at Gate 2 (Order + Refs)
        # for human approval before spending API credits on copy/image gen.
        result = await loop.run_in_executor(None, run_full_pipeline, payload)
        if result is None:
            # Only flag as error if the pipeline didn't already set a more
            # specific state (e.g. awaiting_gate_2). run_full_pipeline writes
            # awaiting_gate_2 to pipeline_state.json before returning None.
            state_path = sprint_dir / "pipeline_state.json"
            current = ""
            if state_path.exists():
                try:
                    current = json.loads(state_path.read_text()).get("state", "")
                except Exception:
                    current = ""
            if current in ("", "running"):
                _write_state("error", "Pipeline failed at intake — check order payload for validation errors")
    except Exception as exc:
        _write_state("error", str(exc))
    finally:
        # Push a proactive notification into the chat so the user sees the
        # new gate / completion / error without having to ask.
        _record_state_notification(sprint_id)


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
    finally:
        _record_state_notification(sprint_id)


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page — two clear paths: start a new order or revisit past ones."""
    # Pull a small preview of recent sprints so the user has one-click access.
    # Each step is fault-tolerant so one malformed sprint dir cannot blank the homepage.
    recent = []
    if RUNS_DIR.exists():
        dirs = []
        try:
            for d in RUNS_DIR.iterdir():
                try:
                    if d.is_dir():
                        dirs.append((d, d.stat().st_mtime))
                except Exception:
                    continue
            dirs.sort(key=lambda t: t[1], reverse=True)
        except Exception:
            dirs = []
        for d, _ in dirs[:5]:
            try:
                recent.append(_sprint_data(d.name))
            except Exception:
                continue

    import html as _h
    def _state_color(state: str) -> tuple[str, str]:
        s = state or ""
        if "complete" in s: return ("#EAF7E3", "#0F7A00")
        if "error" in s: return ("#FDE7EC", "#BE123C")
        if "interrupted" in s: return ("#FBEAD7", "#B45309")
        if "awaiting" in s: return ("#FBF3D9", "#B45309")
        if "stage_" in s or "resuming_" in s or s == "running": return ("#E9F4E6", "#108700")
        return ("#F4F4F4", "#5C5C5C")

    if recent:
        rows = ""
        for s in recent:
            bg, fg = _state_color(s["state"])
            sid = _h.escape(s["sprint_id"])
            driver = _h.escape(s.get("driver") or "—")
            updated = (s["updated_at"][:16].replace("T", " ") if s.get("updated_at") else "—")
            state_label = _h.escape(s.get("state_label") or s.get("state") or "—")
            rows += f"""
            <a href="/sprints/{sid}/chat" class="recent-row">
              <div class="recent-meta">
                <div class="recent-id">{sid}</div>
                <div class="recent-sub">{driver} · {updated}</div>
              </div>
              <span class="recent-badge" style="background:{bg};color:{fg}">{state_label}</span>
            </a>"""
        recent_block = f"""
        <div class="recent-card">
          <div class="recent-head">
            <h3>Recent sprints</h3>
            <a href="/sprints" class="all-link">View all →</a>
          </div>
          {rows}
        </div>"""
    else:
        recent_block = """
        <div class="recent-card empty">
          <p>No sprints yet. Submit your first order to get started.</p>
        </div>"""

    extra_css = """<style>
  .home-hero{margin:8px 0 40px;}
  .home-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--brand-green);margin-bottom:14px;}
  .home-hero h1{font-size:clamp(2.4rem,5.5vw,3.4rem);line-height:.98;letter-spacing:-.015em;color:var(--ink);}
  .home-hero p{font-size:15px;color:var(--ink-mid);max-width:540px;margin-top:14px;line-height:1.6;}
  .actions{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:32px;}
  @media(max-width:680px){.actions{grid-template-columns:1fr}}
  .action-card{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    padding:28px 26px;color:var(--ink);display:block;box-shadow:var(--shadow-soft-sm);
    transition:border-color .15s,box-shadow .2s,transform .15s;}
  .action-card:hover{border-color:var(--brand-green-soft);box-shadow:var(--shadow-soft);transform:translateY(-2px);}
  .action-card.primary{background:linear-gradient(135deg,var(--brand-green),var(--brand-green-deep));color:#fff;border-color:transparent;}
  .action-card.primary:hover{box-shadow:var(--shadow-pop);border-color:transparent;}
  .action-card.primary h2,.action-card.primary p,.action-card.primary .arrow,.action-card.primary .icon{color:#fff;}
  .action-card .icon{font-size:22px;margin-bottom:14px;display:inline-block;}
  .action-card h2{font-size:19px;letter-spacing:-.01em;margin-bottom:6px;color:var(--ink);}
  .action-card p{font-size:13px;color:var(--ink-mid);line-height:1.55;}
  .action-card.primary p{color:rgba(255,255,255,.86);}
  .action-card .arrow{font-size:13px;margin-top:16px;color:var(--brand-green);}
  .recent-card{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    padding:22px 24px;box-shadow:var(--shadow-soft-sm);}
  .recent-card.empty{text-align:center;color:var(--ink-dim);font-size:14px;padding:40px 24px;}
  .recent-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;}
  .recent-head h3{font-size:11px;color:var(--ink-mid);letter-spacing:.12em;text-transform:uppercase;}
  .all-link{font-size:12px;color:var(--brand-green);}
  .recent-row{display:flex;justify-content:space-between;align-items:center;padding:13px 10px;
    margin:0 -10px;border-radius:var(--radius-lg);color:var(--ink);transition:background .12s;}
  .recent-row:hover{background:var(--hover);}
  .recent-row + .recent-row{border-top:1px solid var(--rule);}
  .recent-id{font-size:13px;font-variant-numeric:tabular-nums;letter-spacing:.01em;}
  .recent-sub{font-size:11px;color:var(--ink-mid);margin-top:3px;}
  .recent-badge{padding:3px 11px;border-radius:var(--radius-pill);font-size:11px;letter-spacing:.04em;white-space:nowrap;}
</style>"""
    return HTMLResponse(
        page_head("ADAM · Paid Acquisition", extra_css)
        + nav_html("")
        + f"""
<main class="adam-main"><div class="adam-container stagger">
  <div class="home-hero">
    <div class="home-eyebrow">ADAM · Upwork Paid Acquisition</div>
    <h1>Ad creative, produced end&#8209;to&#8209;end.</h1>
    <p>Submit a new order or pick up a sprint in progress. ADAM takes the brief and produces copy and assembled creative across every size and style.</p>
  </div>
  <div class="actions">
    <a class="action-card primary" href="/new">
      <span class="icon">＋</span>
      <h2>Start a new order</h2>
      <p>Open the order form. The creative team is notified and can pick it up from the handoff page.</p>
      <div class="arrow">Go to form →</div>
    </a>
    <a class="action-card" href="/sprints">
      <span class="icon">▦</span>
      <h2>Revisit past orders</h2>
      <p>Browse every sprint, resume an in-progress chat, or review what was delivered.</p>
      <div class="arrow">View sprints →</div>
    </a>
  </div>
  {recent_block}
</div></main>
</body></html>""")


@app.get("/new", response_class=HTMLResponse)
@app.get("/adam", response_class=HTMLResponse)
async def order_form_page():
    """The order intake form — moved off of `/` so the root can be a hub."""
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
    _validate_sprint_id(sprint_id)
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


# ── Hightouch inbound integration ────────────────────────────────────────────
# Hightouch (reverse ETL) syncs rows from Upwork's data warehouse to operational
# tools. This exposes ADAM as one such destination: when a warehouse row signals
# "produce creative for this brief", Hightouch POSTs to /integrations/hightouch/
# brief and ADAM creates a sprint and starts the (gated) pipeline — exactly the
# same flow as a form submission to /submit.
#
# Auth: a shared bearer token (HIGHTOUCH_API_KEY secret). If it's unset every
# endpoint returns 503 so the integration fails closed.
# Idempotency: Hightouch delivers at-least-once, so each row carries a stable
# external_id. We keep an external_id → sprint_id index and return the existing
# sprint (200) on a repeat instead of creating a duplicate.

_HIGHTOUCH_INDEX_PATH = RUNS_DIR / "_hightouch_index.json"
_HIGHTOUCH_LOCK = threading.Lock()
_HIGHTOUCH_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_HIGHTOUCH_TARGETING = {"Prospecting", "Retargeting", "Prospecting and Retargeting"}
_HIGHTOUCH_DELIVERABLE = {"images-copy", "images-only", "copy-only"}


def _hightouch_check_auth(request: Request) -> None:
    """Fail closed: 503 if no key configured, 401 if the bearer token is wrong."""
    expected = os.environ.get("HIGHTOUCH_API_KEY") or ""
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Hightouch integration not configured (HIGHTOUCH_API_KEY is unset)",
        )
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


def _hightouch_load_index_unlocked() -> dict:
    if not _HIGHTOUCH_INDEX_PATH.exists():
        return {}
    try:
        data = json.loads(_HIGHTOUCH_INDEX_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _hightouch_save_index_unlocked(index: dict) -> None:
    tmp = _HIGHTOUCH_INDEX_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True))
    tmp.replace(_HIGHTOUCH_INDEX_PATH)


def _hightouch_to_order(body: dict, external_id: str, targeting: str, deliverable: str) -> dict:
    """Map Hightouch's flat warehouse-row payload onto the nested order.json
    shape the ADAM pipeline expects (driver/targeting/platform + batches[])."""
    platform = (str(body.get("platform") or "Meta")).strip()
    fmt = (str(body.get("format") or "Feed")).strip()

    vs = body.get("visual_styles")
    if isinstance(vs, str):
        visual_styles = [s.strip() for s in vs.split(",") if s.strip()]
    elif isinstance(vs, list):
        visual_styles = [str(s).strip() for s in vs if str(s).strip()]
    else:
        visual_styles = []
    if not visual_styles:
        visual_styles = ["Lifestyle Photo"]

    size = (str(body.get("resolution") or body.get("size") or "1:1")).strip()
    try:
        quantity = max(1, int(body.get("quantity") or 1))
    except (TypeError, ValueError):
        quantity = 1

    return {
        "driver": (str(body.get("driver") or "hightouch-auto")).strip(),
        "targeting": targeting,
        "platform": platform,
        "delivery_date": (str(body.get("delivery_date") or "")).strip(),
        "deliverable": deliverable,
        "audience": (str(body.get("audience_segment") or body.get("audience") or "")).strip(),
        "brief": (str(body.get("brief") or "")).strip(),
        "source": "hightouch",
        "external_id": external_id,
        "batches": [{
            "platform": platform,
            "format": fmt,
            "visual_styles": visual_styles,
            "resolutions": [{"size": size}],
            "quantity": quantity,
        }],
    }


@app.post("/integrations/hightouch/brief")
async def hightouch_brief(request: Request):
    """Accept a brief from Hightouch and kick off a sprint.
    Returns 201 (new sprint) / 200 (duplicate external_id) / 400 (invalid) /
    401 (bad token) / 503 (integration not configured)."""
    _hightouch_check_auth(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    external_id = str(body.get("external_id") or "").strip()
    if not external_id or not _HIGHTOUCH_EXTERNAL_ID_RE.match(external_id):
        raise HTTPException(status_code=400, detail="external_id is required (1-128 chars of [A-Za-z0-9._:-])")
    if not str(body.get("delivery_date") or "").strip():
        raise HTTPException(status_code=400, detail="delivery_date is required")
    targeting = str(body.get("targeting") or "Prospecting").strip()
    if targeting not in _HIGHTOUCH_TARGETING:
        raise HTTPException(status_code=400, detail=f"targeting must be one of {sorted(_HIGHTOUCH_TARGETING)}")
    deliverable = str(body.get("deliverable") or "images-copy").strip()
    if deliverable not in _HIGHTOUCH_DELIVERABLE:
        raise HTTPException(status_code=400, detail=f"deliverable must be one of {sorted(_HIGHTOUCH_DELIVERABLE)}")

    # Idempotent create: do the lookup-and-register under one lock so two
    # concurrent deliveries of the same external_id can't both create a sprint.
    order = None
    with _HIGHTOUCH_LOCK:
        index = _hightouch_load_index_unlocked()
        existing = index.get(external_id)
        if existing and (RUNS_DIR / existing).is_dir():
            return JSONResponse({
                "ok": True, "duplicate": True, "external_id": external_id,
                "sprint_id": existing, "status_url": f"/sprints/{existing}",
                "chat_url": f"/sprints/{existing}/chat",
            }, status_code=200)
        order = _hightouch_to_order(body, external_id, targeting, deliverable)
        sprint_id = _generate_sprint_id(order)
        _validate_sprint_id(sprint_id)
        order["sprint_id"] = sprint_id
        sprint_dir = RUNS_DIR / sprint_id
        sprint_dir.mkdir(parents=True, exist_ok=True)
        (sprint_dir / "order.json").write_text(json.dumps(order, indent=2))
        (sprint_dir / "pipeline_state.json").write_text(json.dumps({
            "sprint_id": sprint_id, "state": "queued",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        index[external_id] = sprint_id
        _hightouch_save_index_unlocked(index)

    # Fire the pipeline outside the lock (it only schedules a task).
    asyncio.create_task(_run_pipeline_task(order))
    return JSONResponse({
        "ok": True, "duplicate": False, "external_id": external_id,
        "sprint_id": sprint_id, "status_url": f"/sprints/{sprint_id}",
        "chat_url": f"/sprints/{sprint_id}/chat",
    }, status_code=201)


@app.get("/integrations/hightouch/health")
async def hightouch_health(request: Request):
    """Auth-probe endpoint Hightouch can hit while configuring the destination."""
    _hightouch_check_auth(request)
    return JSONResponse({
        "ok": True, "service": "adam", "integration": "hightouch",
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/integrations/hightouch/by-external-id/{external_id}")
async def hightouch_by_external_id(external_id: str, request: Request):
    """Reconcile from the warehouse side: look up the sprint created for a row."""
    _hightouch_check_auth(request)
    if not _HIGHTOUCH_EXTERNAL_ID_RE.match(external_id):
        raise HTTPException(status_code=400, detail="Invalid external_id")
    with _HIGHTOUCH_LOCK:
        index = _hightouch_load_index_unlocked()
    sprint_id = index.get(external_id)
    if not sprint_id or not (RUNS_DIR / sprint_id).is_dir():
        raise HTTPException(status_code=404, detail="No sprint found for that external_id")
    data = _sprint_data(sprint_id)
    return JSONResponse({
        "ok": True, "external_id": external_id, "sprint_id": sprint_id,
        "state": data.get("state"), "state_label": data.get("state_label"),
        "status_url": f"/sprints/{sprint_id}", "chat_url": f"/sprints/{sprint_id}/chat",
    })


PIPELINE_STATE_MESSAGES = {
    "queued":                  "Order queued. Kicking off intake…",
    "running":                  "Pipeline is running…",
    "stage_01_load_refs":       "Loading brand references and targeting examples from Drive…",
    "stage_02_copy_gen":        "Generating ad copy concepts with Claude (usually ~30s)…",
    "stage_03_image_prompts":   "Building image prompts for each ad slot…",
    "stage_04_generate_images": "Generating images — this is the slow one, can take a few minutes…",
    "stage_05_figma_assembly":  "Assembling the layouts in Figma…",
    "stage_06_deliver":         "Packaging the final delivery (renders + manifest)…",
    "resuming_gate_2":          "Gate 2 approved — kicking off copy generation…",
    "resuming_gate_3":          "Gate 3 approved — kicking off image prompt build…",
    "resuming_gate_4":          "Gate 4 approved — kicking off image generation…",
    "resuming_gate_5":          "Gate 5 approved — kicking off Figma assembly…",
    "resuming_gate_6":          "Gate 6 approved — kicking off final delivery…",
    "awaiting_gate_2":          "Reached Gate 2 — Order + References ready for review.",
    "awaiting_gate_3":          "Reached Gate 3 — Copy concepts ready for review.",
    "awaiting_gate_4":          "Reached Gate 4 — Image prompts ready for review.",
    "awaiting_gate_5":          "Reached Gate 5 — Assembly manifest ready for review.",
    "awaiting_gate_6":          "Reached Gate 6 — Final QA ready for review.",
    "complete":                 "Pipeline complete — everything is rendered and delivered.",
    "error":                    "Pipeline hit an error. Check the sprint detail page for the traceback.",
    "interrupted":              "Pipeline was interrupted. You can retry from the sprint detail page.",
}

PIPELINE_TERMINAL_STATES = {"complete", "error", "interrupted"}

# Templated proactive notifications written to chat.jsonl when the pipeline
# reaches a new "stop" state. These show up in the chat unprompted so the user
# doesn't have to guess when to check in.
PIPELINE_CHAT_NOTIFICATIONS = {
    "awaiting_gate_2": "🔔 Gate 2 is open — your order and references are ready for review. Hit \"Show me what's in it\" to see the brief, or \"Approve gate 2\" to start copy generation.",
    "awaiting_gate_3": "🔔 Copy concepts are ready (Gate 3). Hit \"Show me what's in it\" to read the concepts, or \"Approve gate 3\" to move on to image prompts.",
    "awaiting_gate_4": "🔔 Image prompts are ready (Gate 4). Hit \"Show me what's in it\" to scan the prompts, or \"Approve gate 4\" to start image generation.",
    "awaiting_gate_5": "🔔 Assembly is ready (Gate 5). Hit \"Show me what's in it\" to review images and the manifest, or \"Approve gate 5\" for final QA.",
    "awaiting_gate_6": "🔔 Final QA is ready (Gate 6). Hit \"Show me what's in it\" for the pre-delivery check, or \"Approve gate 6\" to complete the sprint.",
    "complete":        "✅ Sprint complete — all gates approved and outputs are delivered.",
    "error":           "⚠️ The pipeline hit an error. Ask me what went wrong or check the sync log.",
    "interrupted":     "⚠️ The pipeline was interrupted. You can retry it from the sprint detail page.",
}


def _record_state_notification(sprint_id: str) -> None:
    """If the current pipeline state warrants a proactive chat notification
    (gate opened, sprint complete, error, etc.) and we haven't already
    notified about that exact state, append an assistant message to chat.jsonl.

    Dedupe markers live in their own `notified_states.json` to avoid racing
    with concurrent writers of `pipeline_state.json`. Safe to call from
    anywhere — failures are swallowed so they can't break the pipeline."""
    try:
        sprint_dir = RUNS_DIR / sprint_id
        state_path = sprint_dir / "pipeline_state.json"
        if not state_path.exists():
            return
        try:
            ps = json.loads(state_path.read_text())
        except Exception:
            return
        state = str(ps.get("state", ""))
        msg = PIPELINE_CHAT_NOTIFICATIONS.get(state)
        if not msg:
            return
        notified_path = sprint_dir / "notified_states.json"
        notified: list[str] = []
        if notified_path.exists():
            try:
                notified = list(json.loads(notified_path.read_text()) or [])
            except Exception:
                notified = []
        if state in notified:
            return
        chat_log = sprint_dir / "chat.jsonl"
        _append_jsonl_safe(chat_log, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": "assistant",
            "text": msg,
            "auto_notification": True,
        })
        notified.append(state)
        try:
            notified_path.write_text(json.dumps(notified, indent=2))
        except Exception:
            pass
    except Exception:
        pass

# Rough wall-clock estimates per stage (seconds). Image gen scales with qty.
PIPELINE_STAGE_ETAS = {
    "queued":                   5,
    "running":                  10,
    "stage_01_load_refs":       15,
    "stage_02_copy_gen":        60,
    "stage_03_image_prompts":   30,
    "stage_04_generate_images": 180,
    "stage_05_figma_assembly":  30,
    "stage_06_deliver":         15,
    "resuming_gate_2":          5,
    "resuming_gate_3":          5,
    "resuming_gate_4":          5,
    "resuming_gate_5":          5,
    "resuming_gate_6":          5,
}


def _eta_for_state(state: str, order: dict) -> int:
    base = PIPELINE_STAGE_ETAS.get(state, 0)
    if state == "stage_04_generate_images":
        # Image gen scales with total quantity — ~30s per image, min 60s.
        batches = order.get("batches") or []
        qty = sum(int(b.get("quantity", 0)) for b in batches) if batches else 1
        return max(60, qty * 30)
    return base


@app.get("/sprints/{sprint_id}/pipeline-events")
async def pipeline_events(sprint_id: str, request: Request):
    """Server-Sent Events stream that watches pipeline_state.json and pushes
    a human-readable narration whenever the state changes. Closes as soon as
    the pipeline reaches an awaiting_gate_* state or a terminal state, so the
    chat UI knows it's time to re-engage Claude."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")

    async def gen():
        state_path = sprint_dir / "pipeline_state.json"
        order_path = sprint_dir / "order.json"
        try:
            order = json.loads(order_path.read_text())
        except Exception:
            order = {}
        last_state: str | None = None
        # Hard cap: 20 min — image gen can be slow but anything longer is a hang.
        deadline = asyncio.get_event_loop().time() + 1200
        # Heartbeat every ~15s to keep proxies from closing the connection.
        last_heartbeat = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() < deadline:
            if await request.is_disconnected():
                return
            try:
                data = json.loads(state_path.read_text())
                state = str(data.get("state", "unknown"))
            except Exception:
                state = "unknown"

            if state != last_state:
                msg = PIPELINE_STATE_MESSAGES.get(state, f"Pipeline state: {state}")
                eta = _eta_for_state(state, order)
                yield f"data: {json.dumps({'type':'status','state':state,'message':msg,'eta_seconds':eta})}\n\n"
                last_state = state
                # Close stream when we hit a gate or terminal state.
                if state.startswith("awaiting_gate_") or state in PIPELINE_TERMINAL_STATES:
                    yield f"data: {json.dumps({'type':'done','state':state})}\n\n"
                    return

            now = asyncio.get_event_loop().time()
            if now - last_heartbeat > 15:
                yield f": heartbeat\n\n"
                last_heartbeat = now
            await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'type':'done','state':'timeout'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/sprints/{sprint_id}/state")
async def sprint_state_public(sprint_id: str):
    """Public sprint-state lookup for the chat UI. sprint_id is the access
    token, so this is safe to expose without an API key — same posture as the
    chat itself."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    try:
        ps = json.loads((sprint_dir / "pipeline_state.json").read_text())
    except Exception:
        ps = {}
    try:
        order = json.loads((sprint_dir / "order.json").read_text())
    except Exception:
        order = {}
    return JSONResponse({
        "sprint_id": sprint_id,
        "state": ps.get("state", ""),
        "updated_at": ps.get("updated_at", ""),
        "driver": order.get("driver", ""),
        "platform": order.get("platform", ""),
    })


# ── Sprint deliverable downloads ─────────────────────────────────────────────
# Public (sprint_id-as-bearer-token, same posture as chat). Lets reviewers on
# any machine pull the final output locally — either as a single ZIP package
# or as the headline asset_manifest.csv on its own.

# Files at the root of a sprint dir that belong in the downloadable package.
_DELIVERABLE_FILES = {
    "asset_manifest.csv",
    "copy_review.csv",
    "image_prompts.csv",
    "copy_outputs.json",
    "run_summary.json",
    "order.json",
    "context.json",
    "pipeline_state.json",
    "gate_decisions.jsonl",
    "chat.jsonl",
}
# Subdirectories whose entire contents go into the ZIP.
# `finals/` contains designer-uploaded final ads (post-Figma assembly).
_DELIVERABLE_DIRS = ("finals", "exports", "images")
# Hard cap on per-file size we'll stuff into the sprint ZIP. Matches the
# finals upload cap so a 100MB final ad doesn't silently get dropped from
# the download package.
_MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def _safe_under(path: Path, root: Path) -> bool:
    """True iff `path` resolves to a real file under `root` (no symlinks
    escaping the sprint directory)."""
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _write_sprint_zip(sprint_dir: Path, fp) -> None:
    """Write a sprint's deliverable files into an open file-like `fp` as a
    ZIP. Streams through a temp file rather than holding the whole archive
    in memory. Symlinks are rejected to prevent exfiltration."""
    top = sprint_dir.name
    root = sprint_dir.resolve()
    with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(_DELIVERABLE_FILES):
            p = sprint_dir / name
            if (
                p.is_file()
                and not p.is_symlink()
                and _safe_under(p, root)
                and p.stat().st_size <= _MAX_FILE_BYTES
            ):
                zf.write(p, arcname=f"{top}/{name}")
        for dname in _DELIVERABLE_DIRS:
            d = sprint_dir / dname
            if not d.is_dir() or d.is_symlink():
                continue
            for f in sorted(d.rglob("*")):
                if (
                    not f.is_file()
                    or f.is_symlink()
                    or not _safe_under(f, root)
                    or f.stat().st_size > _MAX_FILE_BYTES
                ):
                    continue
                rel = f.relative_to(sprint_dir)
                zf.write(f, arcname=f"{top}/{rel.as_posix()}")


@app.get("/sprints/{sprint_id}/download")
async def sprint_download_zip(sprint_id: str):
    """Download the full sprint deliverable as a ZIP. Public — sprint_id is
    the access token, same as the chat UI. Built into a spooled temp file
    so we don't hold the whole archive in memory."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    # SpooledTemporaryFile keeps small archives in memory and spills larger
    # ones to disk automatically — best of both worlds.
    spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    _write_sprint_zip(sprint_dir, spool)
    size = spool.tell()
    spool.seek(0)

    def _iter():
        try:
            while True:
                chunk = spool.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            spool.close()

    return StreamingResponse(
        _iter(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{sprint_id}.zip"',
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
    )


# ── Final-ad uploads (post-Figma handoff) ────────────────────────────────────
# After the designer assembles ads in Figma and exports them, they upload the
# resulting PNG/JPG/PDF files here so the paid-acquisition team can review
# the final deliverables in one place and download them from any computer.
# Public posture (sprint_id-as-token), same as chat/download — uploads from
# any browser without an API key.

_FINALS_DIR_NAME = "finals"
_FINALS_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".mp4", ".mov"}
_FINALS_MAX_FILE_BYTES = 100 * 1024 * 1024     # 100 MB per file
_FINALS_MAX_DIR_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB per sprint
_FINALS_MAX_FILES = 200                         # per sprint
_FINALS_FILENAME_RE = re.compile(r"^[A-Za-z0-9._ ()\-]{1,200}$")
_FINALS_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
}


def _safe_final_name(raw: str) -> str | None:
    """Strip any path components and return a sanitized filename, or None
    if the name isn't acceptable."""
    if not raw:
        return None
    # Strip directory parts (handles both / and \) so a Windows-style path
    # from a ZIP entry can't escape.
    name = raw.replace("\\", "/").split("/")[-1].strip()
    if not name or name in (".", ".."):
        return None
    if not _FINALS_FILENAME_RE.match(name):
        return None
    if Path(name).suffix.lower() not in _FINALS_ALLOWED_EXTS:
        return None
    return name


def _finals_dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.iterdir() if f.is_file())


_REVIEW_STATUSES = {"pending", "approved", "changes_requested"}
_REVIEWS_FILENAME = "finals_reviews.json"
_REVIEW_MAX_COMMENT_LEN = 2000
_REVIEW_MAX_AUTHOR_LEN = 80
_REVIEW_MAX_COMMENTS_PER_FILE = 200
_REVIEWS_LOCK = threading.Lock()


def _reviews_path(sprint_dir: Path) -> Path:
    return sprint_dir / _REVIEWS_FILENAME


def _load_reviews(sprint_dir: Path) -> dict:
    """Read the per-sprint reviews blob. Tolerant of missing or corrupted
    files — those return an empty dict so the gallery still renders."""
    p = _reviews_path(sprint_dir)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_reviews(sprint_dir: Path, reviews: dict) -> None:
    """Atomic write of the reviews blob (write to .tmp, then rename)."""
    p = _reviews_path(sprint_dir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reviews, indent=2, sort_keys=True))
    tmp.replace(p)


def _blank_review() -> dict:
    return {"status": "pending", "decided_by": None, "decided_at": None, "comments": []}


def _clean_text(s: str | None, max_len: int) -> str:
    """Trim, length-cap, and strip control chars from a free-text field."""
    if not s:
        return ""
    s = str(s).strip()
    s = "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 0x20)
    return s[:max_len]


def _list_finals(sprint_dir: Path) -> list[dict]:
    fdir = sprint_dir / _FINALS_DIR_NAME
    if not fdir.is_dir():
        return []
    reviews = _load_reviews(sprint_dir)
    items = []
    for f in sorted(fdir.iterdir()):
        if not f.is_file() or f.is_symlink():
            continue
        st = f.stat()
        ext = f.suffix.lower()
        rev = reviews.get(f.name) or _blank_review()
        items.append({
            "name": f.name,
            "size": st.st_size,
            "uploaded_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "url": f"/sprints/{sprint_dir.name}/finals/{f.name}",
            "is_image": ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"},
            "mime": _FINALS_MIME.get(ext, "application/octet-stream"),
            "review": {
                "status": rev.get("status", "pending"),
                "decided_by": rev.get("decided_by"),
                "decided_at": rev.get("decided_at"),
                "comment_count": len(rev.get("comments") or []),
            },
        })
    return items


def _review_summary(finals: list[dict]) -> dict:
    out = {"approved": 0, "changes_requested": 0, "pending": 0, "total": len(finals)}
    for f in finals:
        s = (f.get("review") or {}).get("status", "pending")
        if s in out:
            out[s] += 1
    return out


@app.get("/sprints/{sprint_id}/finals")
async def sprint_finals_list(sprint_id: str):
    """JSON list of uploaded finals for this sprint, each with its review
    state and a top-level summary count for the Paid Acquisition team."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    finals = _list_finals(sprint_dir)
    return JSONResponse({
        "sprint_id": sprint_id,
        "finals": finals,
        "summary": _review_summary(finals),
    })


@app.get("/sprints/{sprint_id}/finals/{filename}/review")
async def sprint_finals_review_get(sprint_id: str, filename: str):
    """Return the full review record (status + all comments) for one final."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    safe = _safe_final_name(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    f = sprint_dir / _FINALS_DIR_NAME / safe
    if not f.is_file() or f.is_symlink():
        raise HTTPException(status_code=404, detail="Final not found")
    reviews = _load_reviews(sprint_dir)
    rev = reviews.get(safe) or _blank_review()
    return JSONResponse({"sprint_id": sprint_id, "filename": safe, "review": rev})


@app.post("/sprints/{sprint_id}/finals/{filename}/review")
async def sprint_finals_review_set(sprint_id: str, filename: str, payload: dict = Body(...)):
    """Set the approval status of a single final.
    Body: {"reviewer": "Jane (Paid Acq)", "status": "approved" | "changes_requested" | "pending"}
    The reviewer name is auto-appended as a system comment so the thread shows the audit trail."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    safe = _safe_final_name(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    f = sprint_dir / _FINALS_DIR_NAME / safe
    if not f.is_file() or f.is_symlink():
        raise HTTPException(status_code=404, detail="Final not found")

    status = (payload or {}).get("status")
    if status not in _REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_REVIEW_STATUSES)}")
    reviewer = _clean_text((payload or {}).get("reviewer"), _REVIEW_MAX_AUTHOR_LEN) or "Anonymous"
    note = _clean_text((payload or {}).get("note"), _REVIEW_MAX_COMMENT_LEN)
    now = datetime.now(tz=timezone.utc).isoformat()

    with _REVIEWS_LOCK:
        reviews = _load_reviews(sprint_dir)
        rev = reviews.get(safe) or _blank_review()
        prev_status = rev.get("status", "pending")
        rev["status"] = status
        rev["decided_by"] = reviewer if status != "pending" else None
        rev["decided_at"] = now if status != "pending" else None
        # System comment so the thread tells the story of what happened.
        if status != prev_status or note:
            label = {
                "approved": "✓ Approved",
                "changes_requested": "✗ Requested changes",
                "pending": "↺ Reset to pending",
            }[status]
            text = f"{label}" + (f" — {note}" if note else "")
            rev.setdefault("comments", []).append({
                "author": reviewer, "text": text, "at": now, "kind": "status",
            })
            rev["comments"] = rev["comments"][-_REVIEW_MAX_COMMENTS_PER_FILE:]
        reviews[safe] = rev
        _save_reviews(sprint_dir, reviews)

    return JSONResponse({"sprint_id": sprint_id, "filename": safe, "review": rev})


@app.post("/sprints/{sprint_id}/finals/{filename}/comment")
async def sprint_finals_comment_add(sprint_id: str, filename: str, payload: dict = Body(...)):
    """Append a comment to a final's review thread (no status change).
    Body: {"author": "Jane", "text": "love it, ship it"}"""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    safe = _safe_final_name(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    f = sprint_dir / _FINALS_DIR_NAME / safe
    if not f.is_file() or f.is_symlink():
        raise HTTPException(status_code=404, detail="Final not found")

    author = _clean_text((payload or {}).get("author"), _REVIEW_MAX_AUTHOR_LEN) or "Anonymous"
    text = _clean_text((payload or {}).get("text"), _REVIEW_MAX_COMMENT_LEN)
    if not text:
        raise HTTPException(status_code=400, detail="Comment text is required")
    now = datetime.now(tz=timezone.utc).isoformat()

    with _REVIEWS_LOCK:
        reviews = _load_reviews(sprint_dir)
        rev = reviews.get(safe) or _blank_review()
        rev.setdefault("comments", []).append({
            "author": author, "text": text, "at": now, "kind": "comment",
        })
        rev["comments"] = rev["comments"][-_REVIEW_MAX_COMMENTS_PER_FILE:]
        reviews[safe] = rev
        _save_reviews(sprint_dir, reviews)

    return JSONResponse({"sprint_id": sprint_id, "filename": safe, "review": rev})


from fastapi import UploadFile, File as FFile  # for the upload route below


_FINALS_ZIP_MAX_BYTES = 400 * 1024 * 1024   # 400 MB ceiling on the uploaded zip itself
_STREAM_CHUNK = 1 * 1024 * 1024             # 1 MB read chunks for streaming


def _stream_to_path(src, target: Path, max_bytes: int) -> int | None:
    """Copy `src` (a file-like with .read) to `target` in bounded chunks.
    Returns total bytes written, or None if the size cap was exceeded
    (in which case the partial file is removed)."""
    total = 0
    with target.open("wb") as out:
        while True:
            chunk = src.read(_STREAM_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                try:
                    target.unlink()
                except OSError:
                    pass
                return None
            out.write(chunk)
    return total


@app.post("/sprints/{sprint_id}/finals/upload")
async def sprint_finals_upload(
    sprint_id: str,
    files: list[UploadFile] = FFile(...),
):
    """Accept multipart upload of one or more files. Each file is one of:
      - An image (PNG/JPG/GIF/WebP), PDF, or short video → stored as-is.
      - A ZIP from Figma's "Export selected" batch export → extracted in
        place, with each safe entry stored individually.

    Files are streamed through bounded-chunk copies so a 100MB upload
    doesn't sit in memory all at once; ZIPs are spooled to a temp file
    and then extracted entry-by-entry."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        raise HTTPException(status_code=404, detail="Sprint not found")
    fdir = sprint_dir / _FINALS_DIR_NAME
    fdir.mkdir(exist_ok=True)
    root = sprint_dir.resolve()

    stored: list[str] = []
    skipped: list[dict] = []

    def _check_capacity() -> str | None:
        """Return a reason string if we're at capacity, else None."""
        count = sum(1 for _ in fdir.iterdir() if _.is_file())
        if count + 1 > _FINALS_MAX_FILES:
            return f"sprint already has {_FINALS_MAX_FILES} finals (max)"
        if _finals_dir_size(fdir) >= _FINALS_MAX_DIR_BYTES:
            return "sprint finals directory at 2GB cap"
        return None

    def _unique_target(name: str) -> Path:
        """Return a path inside fdir that doesn't collide with anything
        existing (suffix -1, -2, … on collision)."""
        target = fdir / name
        if not target.exists():
            return target
        stem, ext = target.stem, target.suffix
        i = 1
        while (fdir / f"{stem}-{i}{ext}").exists():
            i += 1
        return fdir / f"{stem}-{i}{ext}"

    def _safe_under_root(p: Path) -> bool:
        try:
            p.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    for upload in (files or []):
        raw_name = upload.filename or ""
        ext = Path(raw_name).suffix.lower()

        # Case A: a ZIP from Figma's batch export.
        if ext == ".zip":
            # Spool the upload to a temp file so we don't hold the full
            # zip in memory, and so zipfile can mmap/seek it efficiently.
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
                copied = _stream_to_path(upload.file, Path(tmp.name), _FINALS_ZIP_MAX_BYTES)
                await upload.close()
                if copied is None:
                    skipped.append({"name": raw_name, "reason": "zip exceeds 400MB cap", "source": "zip"})
                    continue
                try:
                    with zipfile.ZipFile(tmp.name) as zf:
                        infos = zf.infolist()
                        if len(infos) > _FINALS_MAX_FILES:
                            skipped.append({"name": raw_name, "reason": "too many entries in zip", "source": "zip"})
                            continue
                        for info in infos:
                            if info.is_dir():
                                continue
                            # Reject zip-slip outright instead of silently
                            # renaming attacker paths to their basename —
                            # makes operator behaviour explicit/auditable.
                            if (
                                "/" in info.filename
                                or "\\" in info.filename
                                or info.filename.startswith("..")
                            ):
                                skipped.append({"name": info.filename, "reason": "zip entry contains a path (rejected)", "source": "zip"})
                                continue
                            if info.file_size > _FINALS_MAX_FILE_BYTES:
                                skipped.append({"name": info.filename, "reason": "zip entry exceeds 100MB", "source": "zip"})
                                continue
                            safe = _safe_final_name(info.filename)
                            if not safe:
                                skipped.append({"name": info.filename, "reason": "unsupported file type or unsafe name", "source": "zip"})
                                continue
                            cap_reason = _check_capacity()
                            if cap_reason:
                                skipped.append({"name": safe, "reason": cap_reason, "source": "zip"})
                                continue
                            target = _unique_target(safe)
                            if not _safe_under_root(target):
                                skipped.append({"name": safe, "reason": "resolved outside sprint dir", "source": "zip"})
                                continue
                            with zf.open(info) as ef:
                                written = _stream_to_path(ef, target, _FINALS_MAX_FILE_BYTES)
                            if written is None:
                                skipped.append({"name": safe, "reason": "exceeds 100MB cap (stream)", "source": "zip"})
                                continue
                            stored.append(target.name)
                except zipfile.BadZipFile:
                    skipped.append({"name": raw_name, "reason": "not a valid zip", "source": "zip"})
            continue

        # Case B: plain file upload — stream to disk.
        safe = _safe_final_name(raw_name)
        if not safe:
            skipped.append({"name": raw_name, "reason": "unsupported file type or unsafe name", "source": "file"})
            await upload.close()
            continue
        cap_reason = _check_capacity()
        if cap_reason:
            skipped.append({"name": safe, "reason": cap_reason, "source": "file"})
            await upload.close()
            continue
        target = _unique_target(safe)
        if not _safe_under_root(target):
            skipped.append({"name": safe, "reason": "resolved outside sprint dir", "source": "file"})
            await upload.close()
            continue
        written = _stream_to_path(upload.file, target, _FINALS_MAX_FILE_BYTES)
        await upload.close()
        if written is None:
            skipped.append({"name": safe, "reason": "exceeds 100MB cap", "source": "file"})
            continue
        stored.append(target.name)

    return JSONResponse({
        "sprint_id": sprint_id,
        "stored": stored,
        "skipped": skipped,
        "finals_count": sum(1 for _ in fdir.iterdir() if _.is_file()),
    })


@app.get("/sprints/{sprint_id}/finals/{filename}")
async def sprint_finals_get(sprint_id: str, filename: str):
    """Serve a single uploaded final. Public — sprint_id is the access token."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    safe = _safe_final_name(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    f = sprint_dir / _FINALS_DIR_NAME / safe
    if not f.is_file() or f.is_symlink():
        raise HTTPException(status_code=404, detail="Final not found")
    # Defence in depth: confirm we didn't escape the sprint dir.
    try:
        f.resolve().relative_to(sprint_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resolved path escapes sprint dir")
    return FileResponse(f, media_type=_FINALS_MIME.get(f.suffix.lower(), "application/octet-stream"))


@app.delete("/sprints/{sprint_id}/finals/{filename}")
async def sprint_finals_delete(sprint_id: str, filename: str):
    """Remove a previously-uploaded final. Useful for fixing mis-uploads.
    Public, same posture as upload."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    safe = _safe_final_name(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    f = sprint_dir / _FINALS_DIR_NAME / safe
    if not f.is_file() or f.is_symlink():
        raise HTTPException(status_code=404, detail="Final not found")
    try:
        f.resolve().relative_to(sprint_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Resolved path escapes sprint dir")
    f.unlink()
    return JSONResponse({"ok": True, "deleted": safe})


_SPRINT_FINALS_UI = BASE_DIR / "agent" / "sprint_finals_ui.html"


@app.get("/sprints/{sprint_id}/finals-ui", response_class=HTMLResponse)
async def sprint_finals_ui(sprint_id: str):
    """Gallery page for uploading and browsing final ads. Public — sprint_id
    is the access token."""
    _validate_sprint_id(sprint_id)
    if not _SPRINT_FINALS_UI.exists():
        return HTMLResponse("<h1>sprint_finals_ui.html not found</h1>", status_code=500)
    return HTMLResponse(
        _SPRINT_FINALS_UI.read_text().replace("__SPRINT_ID__", sprint_id),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/sprints/{sprint_id}/download/manifest")
async def sprint_download_manifest(sprint_id: str):
    """Download just the headline asset_manifest.csv. Public — sprint_id is
    the access token."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    manifest = sprint_dir / "asset_manifest.csv"
    if not manifest.is_file():
        raise HTTPException(status_code=404, detail="asset_manifest.csv not found for this sprint")
    return FileResponse(
        manifest,
        media_type="text/csv",
        filename=f"{sprint_id}_asset_manifest.csv",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/sprints/{sprint_id}/chat-history")
async def sprint_chat_history(sprint_id: str):
    """Return the persisted chat transcript for a sprint as JSON.
    Used by the chat UI on boot to restore past conversations."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    chat_path = sprint_dir / "chat.jsonl"
    if not chat_path.exists():
        return JSONResponse({"sprint_id": sprint_id, "messages": []})
    messages = []
    try:
        # seq = line index in chat.jsonl — a monotonic, server-issued cursor
        # that the client can use to ask for only-new-messages reliably,
        # independent of any clock skew between client and server.
        for idx, line in enumerate(chat_path.read_text().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            # Filter out the [auto] hidden prompts so users don't see them on revisit.
            text = rec.get("text", "")
            if rec.get("role") == "user" and isinstance(text, str) and text.startswith("[auto]"):
                continue
            messages.append({
                "seq": idx,
                "role": rec.get("role"),
                "text": text,
                "ts": rec.get("ts"),
            })
    except Exception as exc:
        return JSONResponse({"sprint_id": sprint_id, "messages": [], "error": str(exc)})
    return JSONResponse({"sprint_id": sprint_id, "messages": messages, "count": len(messages)})


@app.get("/sprints/{sprint_id}/handoff", response_class=HTMLResponse)
async def sprint_handoff(sprint_id: str):
    """Post-submit confirmation page. Shown to whoever submitted the order so
    they know the creative team has been notified, and so they can grab the
    chat link if they ARE the creative team."""
    _validate_sprint_id(sprint_id)
    sprint_dir = _safe_sprint_dir(sprint_id)
    if not sprint_dir.exists():
        return HTMLResponse("<h1>Sprint not found</h1>", status_code=404)
    import html as _html
    order = _load_json(sprint_dir / "order.json") or {}
    batches = order.get("batches") or []
    qty = sum(int(b.get("quantity", 0)) for b in batches) if batches else order.get("quantity", "?")
    styles: list[str] = []
    formats: list[str] = []
    for b in batches:
        styles.extend((b.get("style_quantities") or {}).keys() or b.get("visual_styles") or [])
        if b.get("format"):
            formats.append(str(b["format"]))
    # Format lives per-batch; fall back to top-level if absent.
    fmts_unique = sorted(set(formats)) if formats else ([str(order["format"])] if order.get("format") else [])
    def esc(v) -> str:
        return _html.escape(str(v if v not in (None, "") else "—"))
    styles_str = esc(", ".join(sorted(set(styles))) or "—")
    driver = esc(order.get("driver"))
    platform = esc(order.get("platform"))
    fmt = esc(", ".join(fmts_unique) or "—")
    targeting = esc(order.get("targeting"))
    delivery = esc(order.get("delivery_date"))
    qty = esc(qty)
    safe_sprint_id = esc(sprint_id)
    chat_url = f"/sprints/{sprint_id}/chat"
    status_url = f"/sprints/{sprint_id}"

    extra_css = """<style>
  .ho-wrap{max-width:660px;}
  .ho-card{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-3xl);
    box-shadow:var(--shadow-soft);padding:38px 40px;}
  .check{width:56px;height:56px;border-radius:999px;background:var(--tint);border:1.5px solid var(--brand-green);
    color:var(--brand-green);display:flex;align-items:center;justify-content:center;font-size:28px;margin-bottom:20px;}
  .ho-card h1{font-size:28px;letter-spacing:-.015em;margin-bottom:8px;color:var(--ink);}
  .sub{color:var(--ink-mid);margin-bottom:28px;font-size:14px;line-height:1.6;}
  .id{font-size:12px;color:var(--ink);background:var(--hover);padding:2px 9px;border-radius:var(--radius-md);
    font-variant-numeric:tabular-nums;letter-spacing:.01em;}
  .summary{background:var(--hover);border:1px solid var(--rule);border-radius:var(--radius-xl);
    padding:18px 22px;margin-bottom:24px;}
  .row{display:flex;justify-content:space-between;gap:16px;padding:8px 0;font-size:13px;border-bottom:1px solid var(--rule);}
  .row:last-child{border-bottom:none;}
  .row .k{color:var(--ink-mid);}
  .row .v{color:var(--ink);text-align:right;max-width:62%;}
  .handoff{background:var(--tint);border:1px solid color-mix(in srgb,var(--brand-green) 24%,transparent);
    border-radius:var(--radius-xl);padding:18px 22px;margin-bottom:26px;font-size:13px;color:var(--ink);line-height:1.6;}
  .handoff strong{display:block;margin-bottom:6px;color:var(--brand-green-deep);}
  .actions{display:flex;gap:10px;flex-wrap:wrap;}
  .link-block{display:flex;gap:8px;align-items:center;margin-top:12px;}
  .link-block input{flex:1;padding:10px 12px;font-size:12px;border:1px solid var(--rule-strong);
    border-radius:var(--radius-md);background:var(--paper);color:var(--ink-mid);font-variant-numeric:tabular-nums;}
  .copy-btn{padding:10px 16px;font-size:12px;}
  .copied{color:var(--brand-green);}
</style>"""
    html = (
        page_head(f"Order submitted — {safe_sprint_id}", extra_css)
        + nav_html("")
        + f"""
<main class="adam-main"><div class="adam-container ho-wrap stagger">
<div class="ho-card">
  <div class="check">✓</div>
  <h1>Order submitted</h1>
  <div class="sub">Sprint <span class="id">{safe_sprint_id}</span> is queued and waiting at Gate 2 (Order + Refs review).</div>

  <div class="summary">
    <div class="row"><span class="k">Driver</span><span class="v">{driver}</span></div>
    <div class="row"><span class="k">Platform / Format</span><span class="v">{platform} · {fmt}</span></div>
    <div class="row"><span class="k">Targeting</span><span class="v">{targeting}</span></div>
    <div class="row"><span class="k">Quantity</span><span class="v font-num">{qty}</span></div>
    <div class="row"><span class="k">Visual styles</span><span class="v">{styles_str}</span></div>
    <div class="row"><span class="k">Delivery date</span><span class="v font-num">{delivery}</span></div>
  </div>

  <div class="handoff">
    <strong>Handoff to creative team</strong>
    The creative team can pick up this sprint from the chat link below and walk it through Gates 2 → 6. Share this link with them (Slack notification coming soon):
    <div class="link-block">
      <input id="chat-link" type="text" readonly value="" />
      <button class="btn btn-secondary copy-btn" onclick="copyLink()">Copy</button>
    </div>
  </div>

  <div class="actions">
    <a class="btn btn-primary" href="{chat_url}">Open chat & take it from here →</a>
    <a class="btn btn-secondary" href="{status_url}">View sprint status</a>
    <a class="btn btn-secondary" href="/adam">Submit another order</a>
  </div>
</div>
</div></main>
<script>
  document.getElementById('chat-link').value = window.location.origin + '{chat_url}';
  function copyLink() {{
    const inp = document.getElementById('chat-link');
    inp.select();
    navigator.clipboard.writeText(inp.value).then(() => {{
      const btn = document.querySelector('.copy-btn');
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {{ btn.textContent = orig; btn.classList.remove('copied'); }}, 1500);
    }});
  }}
</script>
</body></html>""")
    return HTMLResponse(html)


@app.post("/sprints/{sprint_id}/approve/{gate_num}", dependencies=[Depends(require_api_key_or_session)])
async def approve_gate(sprint_id: str, gate_num: int, request: Request):
    if gate_num not in GATE_HANDLERS:
        return JSONResponse({"ok": False, "error": f"Unknown gate {gate_num}. Valid: 2–6"}, status_code=400)
    sprint_dir = _safe_sprint_dir(sprint_id)
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

    # Capture optional rationale note from request body (JSON or form).
    note = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            note = str(body.get("note", "") or "").strip()
    except Exception:
        note = ""

    # Persist the gate decision for cross-sprint memory.
    GATE_NAMES_LOCAL = {2: "Order + Refs Review", 3: "Copy Review", 4: "Image Prompt Scan", 5: "Assembly Review", 6: "Final QA"}
    _append_jsonl_safe(sprint_dir / "gate_decisions.jsonl", {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sprint_id": sprint_id,
        "gate": gate_num,
        "gate_name": GATE_NAMES_LOCAL.get(gate_num, ""),
        "decision": "approved",
        "note": note,
        "source": "http",
    })

    state_path.write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": f"resuming_gate_{gate_num}",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    asyncio.create_task(_run_gate_task(sprint_id, gate_num))
    return JSONResponse({"ok": True, "sprint_id": sprint_id, "gate": gate_num, "note_recorded": bool(note), "message": f"Gate {gate_num} approved, pipeline resuming"})


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
            "complete": ("#EAF7E3", "#0F7A00"),
            "error": ("#FDE7EC", "#BE123C"),
            "interrupted": ("#FBEAD7", "#B45309"),
            "running": ("#E9F4E6", "#108700"),
            "queued": ("#F4F4F4", "#5C5C5C"),
        }
        for key, (bg, fg) in colors.items():
            if key in state:
                return bg, fg
        if "awaiting" in state:
            return ("#FBF3D9", "#B45309")
        return ("#F4F4F4", "#5C5C5C")

    rows = ""
    for s in sprints:
        bg, fg = _badge(s["state"])
        gate_btn = ""
        if s["gate"]:
            gate_btn = f'<a href="/sprints/{s["sprint_id"]}/chat" onclick="event.stopPropagation()" class="row-btn row-btn-primary">Review →</a>'
        chat_btn = f'<a href="/sprints/{s["sprint_id"]}/chat" onclick="event.stopPropagation()" class="row-btn">💬 Chat</a>'
        rows += f"""
        <tr onclick="location.href='/sprints/{s['sprint_id']}/chat'">
          <td class="c-time font-num">{s['updated_at'][:16].replace('T',' ') if s['updated_at'] else '—'}</td>
          <td class="c-id font-num">{s['sprint_id']}</td>
          <td>{s['driver'] or '—'}</td>
          <td>{s['platform'] or '—'}</td>
          <td>
            <span class="status-badge" style="background:{bg};color:{fg}">{s['state_label']}</span>
            {gate_btn}{chat_btn}
          </td>
        </tr>"""

    empty = '<tr><td colspan="5" class="empty-cell">No sprints yet — submit an order to get started</td></tr>' if not sprints else ""

    extra_css = """<style>
  .sprints-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:6px;}
  .sprints-head h1{font-size:clamp(2rem,4vw,2.6rem);letter-spacing:-.015em;color:var(--ink);}
  .sub{font-size:13px;color:var(--ink-mid);margin-bottom:24px;}
  .table-wrap{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    box-shadow:var(--shadow-soft);overflow:hidden;}
  table{width:100%;border-collapse:collapse;}
  thead tr{background:var(--hover);border-bottom:1px solid var(--rule);}
  th{padding:12px 18px;text-align:left;font-size:10px;color:var(--ink-mid);letter-spacing:.12em;text-transform:uppercase;}
  tbody tr{border-bottom:1px solid var(--rule);cursor:pointer;transition:background .12s;}
  tbody tr:last-child{border-bottom:none;}
  tbody tr:hover{background:var(--hover);}
  td{padding:14px 18px;font-size:13px;color:var(--ink);}
  td.c-time{font-size:12px;color:var(--ink-mid);}
  td.c-id{letter-spacing:.01em;}
  .empty-cell{padding:44px;text-align:center;color:var(--ink-dim);font-size:14px;}
  .status-badge{padding:3px 11px;border-radius:var(--radius-pill);font-size:11px;letter-spacing:.04em;white-space:nowrap;}
  .row-btn{display:inline-block;margin-left:8px;padding:5px 12px;background:var(--paper);color:var(--ink-mid);
    border:1px solid var(--rule-strong);border-radius:var(--radius-md);font-size:11px;}
  .row-btn:hover{border-color:var(--ink);color:var(--ink);}
  .row-btn-primary{background:var(--brand-green);color:#fff;border-color:var(--brand-green);}
  .row-btn-primary:hover{background:var(--brand-green-deep);color:#fff;}
</style>"""
    return HTMLResponse(
        page_head("ADAM · Sprints", extra_css)
        + nav_html("sprints")
        + f"""
<main class="adam-main"><div class="adam-container stagger">
  <div class="sprints-head">
    <h1>Sprint Runs</h1>
    <button class="btn btn-secondary" onclick="location.reload()">↻ Refresh</button>
  </div>
  <p class="sub">{len(sprints)} sprint{"s" if len(sprints)!=1 else ""} · click any row to view details</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Time</th><th>Sprint ID</th><th>Driver</th><th>Platform</th><th>Status</th></tr></thead>
      <tbody>{rows}{empty}</tbody>
    </table>
  </div>
  <div id="sync-mini-panel">{_sync_mini_panel()}</div>
</div></main>
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
    return HTMLResponse(
        _SPRINT_CHAT_UI.read_text().replace("__SPRINT_ID__", sprint_id),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


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

    # Validate sprint_id BEFORE any disk activity (prevent path traversal).
    sprint_dir = _safe_sprint_dir(sprint_id)
    chat_log_path = sprint_dir / "chat.jsonl"

    def _append_chat(record: dict):
        # Concurrent-safe; logs warning instead of silently swallowing.
        _append_jsonl_safe(chat_log_path, record)

    if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
        last = messages[-1]
        content = last.get("content", "")
        if isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        else:
            text = str(content)
        if text.strip():
            _append_chat({
                "ts": datetime.now(timezone.utc).isoformat(),
                "role": "user",
                "text": text,
            })

    async def _stream():
        assistant_text_parts: list[str] = []
        tool_events: list[dict] = []
        try:
            async for chunk in run_agent_turn(messages, api_key, sprint_id=sprint_id):
                # Capture for persistence — chunks are SSE strings ('data: {...}\n\n').
                try:
                    if chunk.startswith("data: "):
                        payload = json.loads(chunk[len("data: "):].strip())
                        ptype = payload.get("type")
                        if ptype == "text" and payload.get("text"):
                            assistant_text_parts.append(payload["text"])
                        elif ptype == "tool_call":
                            tool_events.append({"kind": "call", "name": payload.get("name"), "input": payload.get("input")})
                        elif ptype == "tool_result":
                            tool_events.append({"kind": "result", "name": payload.get("name"), "result": payload.get("result")})
                except Exception:
                    pass
                yield chunk
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'
            yield 'data: {"type":"done"}\n\n'
        finally:
            if assistant_text_parts or tool_events:
                _append_chat({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "role": "assistant",
                    "text": "".join(assistant_text_parts),
                    "tool_events": tool_events,
                })

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
        err_msg = '<p style="color:var(--bad-fg);font-size:13px;margin-bottom:12px">Incorrect key — try again.</p>' if auth_error else ""
        extra_css = """<style>
  body{display:flex;align-items:center;justify-content:center;min-height:100dvh;}
  .auth-box{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    box-shadow:var(--shadow-soft);padding:34px;width:100%;max-width:380px;}
  .auth-box .adam-logo{font-size:18px;letter-spacing:.18em;color:var(--ink);}
  .auth-box .adam-logo b{color:var(--brand-green);}
  .auth-box .sub{font-size:13px;color:var(--ink-mid);margin:8px 0 20px;}
  .auth-box input{width:100%;padding:11px 13px;border:1px solid var(--rule-strong);border-radius:var(--radius-lg);
    font-size:14px;margin-bottom:14px;font-family:var(--font-sans);}
  .auth-box input:focus{outline:none;border-color:var(--brand-green);box-shadow:0 0 0 3px color-mix(in srgb,var(--brand-green) 14%,transparent);}
  .auth-box button{width:100%;padding:12px;background:var(--brand-green);color:#fff;border:none;
    border-radius:var(--radius-lg);font-size:14px;cursor:pointer;font-family:var(--font-sans);}
  .auth-box button:hover{background:var(--brand-green-deep);}
</style>"""
        return HTMLResponse(
            page_head(f"ADAM — {sprint_id}", extra_css)
            + f"""<div class="auth-box">
  <div class="adam-logo">ADAM<b>.</b></div>
  <p class="sub">Enter your API key to view this sprint.</p>
  {err_msg}
  <form method="POST" action="/sprints/{sprint_id}/auth">
    <input type="password" name="api_key" placeholder="API key" autofocus required>
    <button type="submit">Continue</button>
  </form>
</div></body></html>""")

    s = _sprint_data(sprint_id)

    def _badge(state):
        if state == "complete": return "#EAF7E3", "#0F7A00"
        if state == "error": return "#FDE7EC", "#BE123C"
        if state == "interrupted": return "#FBEAD7", "#B45309"
        if "awaiting" in state: return "#FBF3D9", "#B45309"
        if state in ("running", "queued") or state.startswith("stage_"): return "#E9F4E6", "#108700"
        return "#F4F4F4", "#5C5C5C"

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
        <div style="display:flex;gap:14px;margin:18px 0">
          <div style="flex:1;padding:16px 20px;background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-xl);box-shadow:var(--shadow-soft-sm);text-align:center">
            <div style="font-size:28px;color:var(--brand-green);font-variant-numeric:tabular-nums;line-height:1">{run_sum.get('total_assets',0)}</div>
            <div style="font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em;margin-top:6px">Assets</div>
          </div>
          <div style="flex:1;padding:16px 20px;background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-xl);box-shadow:var(--shadow-soft-sm);text-align:center">
            <div style="font-size:28px;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1">{run_sum.get('concepts_selected',0)}</div>
            <div style="font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em;margin-top:6px">Concepts</div>
          </div>
          <div style="flex:1;padding:16px 20px;background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-xl);box-shadow:var(--shadow-soft-sm);text-align:center">
            <div style="font-size:28px;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1">{run_sum.get('images_generated',0)}</div>
            <div style="font-size:10px;color:var(--ink-mid);text-transform:uppercase;letter-spacing:.1em;margin-top:6px">Images</div>
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

    extra_css = """<style>
  .detail-head{display:flex;align-items:center;gap:14px;margin-bottom:22px;flex-wrap:wrap;}
  .detail-head h1{font-size:clamp(1.6rem,3.5vw,2.1rem);letter-spacing:-.01em;font-variant-numeric:tabular-nums;color:var(--ink);}
  .detail-head .status-badge{padding:4px 12px;border-radius:var(--radius-pill);font-size:12px;letter-spacing:.04em;}
  .detail-head .log-link{margin-left:auto;font-size:12px;color:var(--ink-mid);}
  .card{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    box-shadow:var(--shadow-soft-sm);margin-bottom:20px;overflow:hidden;}
  .card-head{padding:14px 18px;border-bottom:1px solid var(--rule);font-size:11px;color:var(--ink-mid);
    letter-spacing:.12em;text-transform:uppercase;}
  table{width:100%;border-collapse:collapse;}
  tbody tr:not(:last-child){border-bottom:1px solid var(--rule);}
  td{color:var(--ink);}
</style>"""
    return HTMLResponse(
        page_head(f"ADAM — {sprint_id}", extra_css)
        + nav_html("sprints")
        + f"""
<main class="adam-main"><div class="adam-container stagger">
  <div class="detail-head">
    <h1>{sprint_id}</h1>
    <span class="status-badge" style="background:{bg};color:{fg}">{s['state_label']}</span>
    <a href="/sprints/{sprint_id}/log" target="_blank" class="log-link">View log →</a>
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
</div></main>

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
    return HTMLResponse(f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Log — {sprint_id}</title>
<link rel="stylesheet" href="/static/adam-design.css">
<style>
  body{{padding:28px;}}
  .log-title{{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-mid);margin-bottom:12px;}}
  .log-title b{{color:var(--ink);font-variant-numeric:tabular-nums;}}
  pre{{white-space:pre-wrap;word-break:break-all;font-family:var(--font-sans);font-size:12.5px;line-height:1.7;
    color:var(--ink);background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-xl);
    box-shadow:var(--shadow-soft-sm);padding:20px 22px;}}
</style></head>
<body>
<div class="log-title">Pipeline log · <b>{sprint_id}</b></div>
<pre>{content}</pre></body></html>""")


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
        bg = "#EAF7E3" if status == "ok" else "#FDE7EC"
        fg = "#0F7A00" if status == "ok" else "#BE123C"
        label = "ok" if status == "ok" else "error"
        sha = html.escape(e.get("sha", "—"))
        pusher = html.escape(e.get("pusher", "—"))
        ts = html.escape(e.get("ts", "—").replace("T", " ").replace("+00:00", " UTC"))
        detail = html.escape(e.get("detail", ""))
        detail_cell = f'<span title="{detail}" style="font-size:11px;color:var(--ink-mid)">{detail[:80] + ("…" if len(detail) > 80 else "")}</span>' if detail else "—"
        rows += f"""<tr>
          <td style="padding:12px 16px;font-size:12px;color:var(--ink-mid);white-space:nowrap;font-variant-numeric:tabular-nums">{ts}</td>
          <td style="padding:12px 16px;font-size:13px;color:var(--ink)">{pusher}</td>
          <td style="padding:12px 16px;font-size:12px;letter-spacing:.02em;font-variant-numeric:tabular-nums">{sha}</td>
          <td style="padding:12px 16px"><span style="background:{bg};color:{fg};padding:3px 11px;border-radius:var(--radius-pill);font-size:11px;letter-spacing:.04em">{label}</span></td>
          <td style="padding:12px 16px">{detail_cell}</td>
        </tr>"""

    empty = '<tr><td colspan="5" style="padding:44px;text-align:center;color:var(--ink-dim);font-size:14px">No syncs recorded yet</td></tr>' if not entries else ""

    extra_css = """<style>
  .sync-head h1{font-size:clamp(2rem,4vw,2.6rem);letter-spacing:-.015em;color:var(--ink);}
  .sub{font-size:13px;color:var(--ink-mid);margin:6px 0 24px;}
  .table-wrap{background:var(--paper);border:1px solid var(--rule);border-radius:var(--radius-2xl);
    box-shadow:var(--shadow-soft);overflow:hidden;}
  table{width:100%;border-collapse:collapse;}
  thead tr{background:var(--hover);border-bottom:1px solid var(--rule);}
  th{padding:12px 16px;text-align:left;font-size:10px;color:var(--ink-mid);letter-spacing:.12em;text-transform:uppercase;}
  tbody tr{border-bottom:1px solid var(--rule);}
  tbody tr:last-child{border-bottom:none;}
</style>"""
    return HTMLResponse(
        page_head("ADAM · Sync History", extra_css)
        + nav_html("sync")
        + f"""
<main class="adam-main"><div class="adam-container stagger">
  <div class="sync-head"><h1>GitHub Sync History</h1></div>
  <p class="sub">Showing {len(entries)} of {total} total event{"s" if total != 1 else ""} (capped at {SYNC_LOG_MAX_ENTRIES}) · {ok_count} ok, {err_count} error{"s" if err_count != 1 else ""} · newest first</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Time (UTC)</th><th>Pusher</th><th>Commit SHA</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>{rows}{empty}</tbody>
    </table>
  </div>
</div></main>
</body></html>""")


LEARNINGS_PATH = BASE_DIR / "learnings.md"
LEARNINGS_HEADER = (
    "# ADAM Learnings\n\n"
    "Institutional memory shared across every sprint. Edit this file directly "
    "to add, refine, or remove guidance — Claude reads it at the start of every "
    "chat session.\n\n"
    "## Guidance\n\n"
)


@app.get("/learnings", response_class=HTMLResponse)
async def learnings_editor():
    """Public, manually-editable institutional-memory doc."""
    if not LEARNINGS_PATH.exists():
        LEARNINGS_PATH.write_text(LEARNINGS_HEADER)
    content = LEARNINGS_PATH.read_text()
    # Minimal inline editor — no auth (sprint chat itself is public; this is a peer surface).
    extra_css = """<style>
  .learn-head h1{font-size:clamp(2rem,4vw,2.6rem);letter-spacing:-.015em;color:var(--ink);}
  .sub{color:var(--ink-mid);margin:8px 0 22px;font-size:13px;line-height:1.6;}
  .sub code{background:var(--hover);padding:1px 6px;border-radius:var(--radius-sm);font-size:12px;}
  textarea{width:100%;min-height:58vh;font-family:var(--font-sans);font-size:14px;line-height:1.6;padding:18px;
    border:1px solid var(--rule-strong);border-radius:var(--radius-xl);background:var(--paper);color:var(--ink);
    box-sizing:border-box;box-shadow:var(--shadow-soft-sm);}
  textarea:focus{outline:none;border-color:var(--brand-green);box-shadow:0 0 0 3px color-mix(in srgb,var(--brand-green) 14%,transparent);}
  .row{display:flex;gap:12px;align-items:center;margin-top:14px;}
  .status{color:var(--brand-green);font-size:13px;}
  .err{color:var(--bad-fg);font-size:13px;}
</style>"""
    html = """__HEAD____NAV__
<main class="adam-main"><div class="adam-container stagger">
<div class="learn-head"><h1>ADAM Learnings</h1></div>
<div class="sub">Institutional memory shared across every sprint. Loaded into Claude's context on every chat. Edit freely — saves to <code>learnings.md</code> at the project root, also editable in the Replit file editor.</div>
<form id="f">
  <textarea id="t" name="content">__CONTENT__</textarea>
  <div class="row">
    <button type="submit" class="btn btn-primary">Save</button>
    <span id="s" class="status"></span>
  </div>
</form>
</div></main>
<script>
const f=document.getElementById('f'),t=document.getElementById('t'),s=document.getElementById('s');
f.addEventListener('submit',async e=>{
  e.preventDefault();s.textContent='Saving…';s.className='status';
  try{
    const r=await fetch('/learnings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:t.value})});
    const j=await r.json();
    if(j.ok){s.textContent='Saved '+new Date().toLocaleTimeString();}
    else{s.textContent=j.error||'Save failed';s.className='err';}
  }catch(err){s.textContent=String(err);s.className='err';}
});
</script>
</body></html>"""
    html = (
        html.replace("__HEAD__", page_head("ADAM · Learnings", extra_css))
        .replace("__NAV__", nav_html("learnings"))
        .replace("__CONTENT__", content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    )
    return HTMLResponse(html)


@app.post("/learnings", dependencies=[Depends(require_api_key_or_session)])
async def learnings_save(request: Request):
    try:
        body = await request.json()
        content = body.get("content", "")
        if not isinstance(content, str):
            return JSONResponse({"ok": False, "error": "content must be a string"}, status_code=400)
        LEARNINGS_PATH.write_text(content)
        return JSONResponse({"ok": True, "bytes": len(content)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/learnings")
async def learnings_raw():
    if not LEARNINGS_PATH.exists():
        return JSONResponse({"content": "", "path": str(LEARNINGS_PATH)})
    return JSONResponse({"content": LEARNINGS_PATH.read_text(), "path": str(LEARNINGS_PATH)})


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
