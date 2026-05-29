"""Hightouch → ADAM integration.

Hightouch (reverse ETL) syncs rows from Upwork's data warehouse to operational
tools. This module exposes ADAM as one of those destinations: when a row in
the warehouse signals "produce creative for this brief," Hightouch POSTs to
/integrations/hightouch/brief and ADAM creates a sprint.

Design choices:
- **Simplified payload shape.** Hightouch users map warehouse columns to
  fields; we keep the schema flat and shallow so column mapping is obvious.
  ADAM translates internally to the canonical order.json the pipeline expects.
- **Idempotent via external_id.** If Hightouch re-syncs the same row, ADAM
  returns the existing sprint instead of creating a duplicate.
- **Bearer-token auth.** Single shared secret in HIGHTOUCH_API_KEY env var.
  Replace with HMAC signatures if Upwork requires per-row signing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
HT_INDEX_PATH = RUNS_DIR / "_hightouch_external_id_index.json"
INTAKE_PATH = REPO_ROOT / "pipeline" / "00_intake.py"
PIPELINE_SCRIPT = REPO_ROOT / "pipeline" / "run_pipeline.py"

router = APIRouter(prefix="/integrations/hightouch", tags=["integrations"])


# ── auth ────────────────────────────────────────────────────────────────────

def _require_token(authorization: Optional[str]) -> None:
    expected = os.environ.get("HIGHTOUCH_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="HIGHTOUCH_API_KEY not configured on the server",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    if authorization[len("Bearer "):].strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


# ── intake helpers ──────────────────────────────────────────────────────────

def _load_intake_module():
    """Load pipeline/00_intake.py despite the leading-digit filename."""
    spec = importlib.util.spec_from_file_location("intake", INTAKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_external_id_index() -> dict[str, str]:
    if not HT_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(HT_INDEX_PATH.read_text())
    except Exception:
        return {}


def _save_external_id_index(index: dict[str, str]) -> None:
    RUNS_DIR.mkdir(exist_ok=True)
    HT_INDEX_PATH.write_text(json.dumps(index, indent=2))


# ── payload translation ────────────────────────────────────────────────────

def _to_canonical_order(brief: dict[str, Any]) -> dict[str, Any]:
    """Map the Hightouch simplified brief to the order.json the pipeline expects.

    Hightouch payload (flat):
      {
        "external_id": "...",
        "audience_segment": "...",
        "platform": "Meta",
        "format": "Static Feed",
        "deliverable": "images-copy",
        "targeting": "Prospecting",
        "visual_styles": ["Lifestyle Photo", ...],
        "resolutions": [{"size": "1440x1440", "ratio": "1:1"}, ...],
        "quantity": 3,
        "delivery_date": "2026-06-15",
        "brief": "...",
        "driver": "hightouch-auto"   (optional)
      }
    """
    # Optional carousel support — Hightouch sends carousel + carousel_slides.
    carousel = bool(brief.get("carousel"))
    batch: dict[str, Any] = {
        "platform": brief.get("platform"),
        "format": brief.get("format"),
        "visual_styles": brief.get("visual_styles") or [],
        "resolutions": brief.get("resolutions") or [],
        "quantity": brief.get("quantity") or 1,
        "carousel": carousel,
    }
    if carousel and brief.get("carousel_slides") is not None:
        batch["carousel_slides"] = brief["carousel_slides"]
    # Required by intake for "Prospecting and Retargeting" orders.
    if brief.get("targeting") == "Prospecting and Retargeting":
        batch["audience"] = brief.get("audience_segment") or "unspecified"

    return {
        "delivery_date": brief.get("delivery_date"),
        "driver": brief.get("driver") or "hightouch-auto",
        "targeting": brief.get("targeting"),
        "deliverable": brief.get("deliverable"),
        "brief": brief.get("brief") or brief.get("audience_segment") or "",
        "batches": [batch],
    }


# ── pipeline launcher (mirrors app.py's pattern) ────────────────────────────

async def _launch_pipeline(sprint_id: str, order_json_path: Path) -> None:
    log_path = RUNS_DIR / sprint_id / "pipeline.log"
    log_handle = log_path.open("a", buffering=1)
    log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] hightouch trigger — starting pipeline for {sprint_id}\n")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(PIPELINE_SCRIPT),
            "--json",
            str(order_json_path),
            cwd=str(REPO_ROOT),
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ},
        )
        log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] pid={proc.pid}\n")
    except Exception as e:
        log_handle.write(f"[{datetime.now(timezone.utc).isoformat()}] FAILED TO LAUNCH: {e}\n")
        log_handle.close()


# ── routes ──────────────────────────────────────────────────────────────────

@router.post("/brief")
async def receive_brief(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Accept a campaign brief from Hightouch, create a sprint, run the pipeline.

    Returns:
      201  — new sprint created. Body: { ok, sprint_id, status_url, chat_url }
      200  — sprint with this external_id already exists (idempotent replay).
             Body: same shape, plus duplicate=true.
      400  — payload validation failed. Body: { error, details: [...] }
      401  — missing/invalid auth
      503  — server missing HIGHTOUCH_API_KEY
    """
    _require_token(authorization)
    brief = await request.json()
    external_id = (brief.get("external_id") or "").strip()

    # ── Idempotency check
    if external_id:
        index = _load_external_id_index()
        if external_id in index:
            existing = index[external_id]
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "duplicate": True,
                    "external_id": external_id,
                    "sprint_id": existing,
                    "status_url": f"/sprints/{existing}",
                    "chat_url": f"/sprints/{existing}/chat",
                },
            )

    # ── Validate using the pipeline's own validator
    canonical = _to_canonical_order(brief)
    intake = _load_intake_module()
    errors = intake.validate_payload(canonical)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"error": "payload_validation_failed", "details": errors},
        )

    # ── Create the sprint
    sprint_id = intake.generate_sprint_id(canonical)
    sprint_dir = RUNS_DIR / sprint_id
    sprint_dir.mkdir(parents=True, exist_ok=True)
    order = intake.build_order(canonical, sprint_id)
    order["_source"] = {
        "via": "hightouch",
        "external_id": external_id or None,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    order_path = sprint_dir / "order.json"
    order_path.write_text(json.dumps(order, indent=2))

    # ── Record idempotency mapping
    if external_id:
        index = _load_external_id_index()
        index[external_id] = sprint_id
        _save_external_id_index(index)

    # ── Fire the pipeline (fire-and-forget; status via /sprints/<id>)
    asyncio.create_task(_launch_pipeline(sprint_id, order_path))

    return JSONResponse(
        status_code=201,
        content={
            "ok": True,
            "duplicate": False,
            "external_id": external_id or None,
            "sprint_id": sprint_id,
            "status_url": f"/sprints/{sprint_id}",
            "chat_url": f"/sprints/{sprint_id}/chat",
        },
    )


@router.get("/health")
async def health(authorization: Optional[str] = Header(default=None)):
    """Health probe for Hightouch's sync configuration UI."""
    _require_token(authorization)
    return {
        "ok": True,
        "service": "adam-pipeline-hightouch",
        "runs_dir_present": RUNS_DIR.exists(),
        "intake_present": INTAKE_PATH.exists(),
        "pipeline_present": PIPELINE_SCRIPT.exists(),
    }


@router.get("/by-external-id/{external_id}")
async def lookup_by_external_id(
    external_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Return the sprint_id associated with a given external_id, or 404."""
    _require_token(authorization)
    index = _load_external_id_index()
    if external_id not in index:
        raise HTTPException(status_code=404, detail=f"no sprint for external_id={external_id!r}")
    sprint_id = index[external_id]
    return {
        "ok": True,
        "external_id": external_id,
        "sprint_id": sprint_id,
        "status_url": f"/sprints/{sprint_id}",
        "chat_url": f"/sprints/{sprint_id}/chat",
    }
