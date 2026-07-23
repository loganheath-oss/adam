"""ADAM pipeline MCP server.

Exposes ADAM pipeline tools to MCP clients (Claude Code locally; claude.ai
once deployed as an Enterprise connector).

Two transports:
  * stdio (default) — for Claude Code on Logan's laptop. Run: `python server.py`
  * http  (Streamable HTTP on $PORT) — for Fly/Cloud Run deployment. Set
    MCP_TRANSPORT=http to enable. Optional auth via MCP_AUTH_TOKEN.

Wire into Claude Code (stdio):
    claude mcp add --scope user adam-pipeline \\
        /path/to/.venv/bin/python /path/to/mcp_server/server.py
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
PIPELINE_SCRIPT = REPO_ROOT / "pipeline" / "run_pipeline.py"
INTAKE_PATH = REPO_ROOT / "pipeline" / "00_intake.py"


def _load_intake_module():
    """Load pipeline/00_intake.py — leading digit forbids regular import."""
    spec = importlib.util.spec_from_file_location("intake", INTAKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_run_pipeline_module():
    """Load pipeline/run_pipeline.py so we can call stage_01_load_refs directly.

    run_pipeline.py is importable but lives outside any package; importlib gets
    us at it without polluting sys.path.
    """
    rp_path = REPO_ROOT / "pipeline" / "run_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_pipeline", rp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

GATE_NAMES = {
    2: "order + refs confirmed",
    3: "copy approved",
    4: "image prompts approved",
    5: "images approved",
    6: "final QA approved",
}

# Allowed Host header values for DNS rebinding protection. We add the public
# Fly hostname so claude.ai can reach us; localhost stays for local testing.
# Override via MCP_ALLOWED_HOSTS env var (comma-separated) when deploying elsewhere.
_default_hosts = "adam-pipeline-cm.fly.dev,localhost,127.0.0.1"
_allowed_hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", _default_hosts).split(",") if h.strip()]
_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=_allowed_hosts,
)

mcp = FastMCP("adam-pipeline", transport_security=_security)


def _sprint_dir(sprint_id: str) -> Path:
    path = RUNS_DIR / sprint_id
    if not path.exists():
        raise FileNotFoundError(f"Sprint not found: {sprint_id}")
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


@mcp.tool()
def list_sprints(limit: int = 20) -> list[dict[str, Any]]:
    """List recent sprints with their current pipeline state.

    Args:
        limit: Maximum number of sprints to return (default 20, newest first).
    """
    if not RUNS_DIR.exists():
        return []
    sprints = []
    for path in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        state = _read_json(path / "pipeline_state.json") or {}
        order = _read_json(path / "order.json") or {}
        sprints.append(
            {
                "sprint_id": path.name,
                "state": state.get("state", "unknown"),
                "updated_at": state.get("updated_at"),
                "driver": order.get("driver"),
                "platform": order.get("platform"),
                "delivery_date": order.get("delivery_date"),
            }
        )
        if len(sprints) >= limit:
            break
    return sprints


@mcp.tool()
def get_sprint(sprint_id: str) -> dict[str, Any]:
    """Get the full state of a single sprint: order, pipeline state, and run summary."""
    path = _sprint_dir(sprint_id)
    return {
        "sprint_id": sprint_id,
        "order": _read_json(path / "order.json"),
        "pipeline_state": _read_json(path / "pipeline_state.json"),
        "run_summary": _read_json(path / "run_summary.json"),
        "available_files": sorted(p.name for p in path.iterdir() if p.is_file()),
    }


@mcp.tool()
def get_copy_concepts(sprint_id: str) -> dict[str, Any]:
    """Get the generated copy concepts and review scores for a sprint.

    `copy_review` is normally written by stage_06_deliver, which means it
    doesn't exist between gate 3 and gate 6. When that's the case, we
    synthesize the same row shape from copy_outputs.json so reviewers always
    get the full ranked table regardless of how far the sprint has progressed.
    """
    path = _sprint_dir(sprint_id)
    outputs = _read_json(path / "copy_outputs.json")
    review = _read_csv(path / "copy_review.csv")
    if not review and outputs:
        concepts = outputs.get("concepts") or []
        review = [
            {
                "Visual_Style": c.get("visual_style", ""),
                "rank": str(c.get("rank", "")),
                "selected": "YES" if c.get("selected") else "NO",
                "score": str(c.get("score", "")),
                "Text_On_Visual": c.get("creative_headline", c.get("headline", "")),
                "Primary_Text_Short": c.get("body_short", c.get("body", "")),
                "Primary_Text_Long": c.get("body_long", ""),
                "Description": c.get("description", ""),
                "CTA": c.get("cta", ""),
                "concept_tag": c.get("concept_tag", ""),
                "review_notes": c.get("review_notes", ""),
            }
            for c in concepts
        ]
    return {
        "sprint_id": sprint_id,
        "copy_outputs": outputs,
        "copy_review": review,
        "copy_review_source": "csv" if (path / "copy_review.csv").exists() else "synthesized_from_copy_outputs",
    }


@mcp.tool()
def get_image_prompts(sprint_id: str) -> list[dict[str, str]]:
    """Get the image prompts CSV — what each ad slot is asking for visually."""
    return _read_csv(_sprint_dir(sprint_id) / "image_prompts.csv")


@mcp.tool()
def get_manifest(sprint_id: str) -> dict[str, Any]:
    """Get the asset manifest used by the Figma assembly plugin."""
    path = _sprint_dir(sprint_id)
    return {
        "sprint_id": sprint_id,
        "asset_manifest": _read_csv(path / "asset_manifest.csv"),
        "plugin_manifest": _read_csv(path / "plugin_manifest.csv"),
    }


@mcp.tool()
def get_generation_log(sprint_id: str) -> Any:
    """Get the generation log — stage timings, model calls, errors."""
    return _read_json(_sprint_dir(sprint_id) / "generation_log.json")


@mcp.tool()
def approve_gate(sprint_id: str, gate: int, timeout_seconds: int = 600) -> dict[str, Any]:
    """Approve a pipeline gate and resume the run.

    Shells out to `pipeline/run_pipeline.py --resume <sprint_id> --gate <gate>`.
    This will run real LLM and Figma calls and may take several minutes —
    the timeout defaults to 10 minutes.

    Args:
        sprint_id: e.g. "2026-04-meta-6677".
        gate: 2 (order+refs), 3 (copy), 4 (prompts), 5 (images), 6 (final QA).
        timeout_seconds: max wait before killing the subprocess.

    Returns: {success, gate, gate_name, exit_code, stdout_tail, stderr_tail, new_state}
    """
    if gate not in GATE_NAMES:
        raise ValueError(f"gate must be one of {sorted(GATE_NAMES)}; got {gate}")
    _sprint_dir(sprint_id)  # validate sprint exists

    proc = subprocess.run(
        [sys.executable, str(PIPELINE_SCRIPT), "--resume", sprint_id, "--gate", str(gate)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=REPO_ROOT,
    )

    new_state = _read_json(_sprint_dir(sprint_id) / "pipeline_state.json")
    return {
        "success": proc.returncode == 0,
        "gate": gate,
        "gate_name": GATE_NAMES[gate],
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
        "new_state": new_state,
    }


# Form labels → canonical pipeline visual_style names. The order form uses
# descriptive labels (e.g. "Lifestyle Photo (full bleed)"); the pipeline's
# validator demands exact canonical strings. This map translates one to the other.
VISUAL_STYLE_NORMALIZATION = {
    "Lifestyle Photo (full bleed)": "Lifestyle Photo",
    "Photo with Text (Upwork shell)": "Photo with Text",
    "Us Vs Them": "Us vs Them",
    "Device UI (Photo)": "Device UI",
    # Older order forms may say "Text with Button and Cursor" — the canonical
    # name aligns with Brandon's Figma adtype container ("Adtype: Text with Button").
    "Text with Button and Cursor": "Text with Button",
}


def _normalize_payload(payload: dict) -> None:
    """Translate form-friendly labels to pipeline-canonical values in place."""
    for batch in payload.get("batches", []) or []:
        styles = batch.get("visual_styles") or []
        batch["visual_styles"] = [VISUAL_STYLE_NORMALIZATION.get(s, s) for s in styles]
        sq = batch.get("style_quantities") or {}
        if sq:
            batch["style_quantities"] = {
                VISUAL_STYLE_NORMALIZATION.get(k, k): v for k, v in sq.items()
            }


async def _submit_order_handler(request):
    """Accept an order payload from the form and create a new sprint.

    Body: JSON in the canonical pipeline payload shape (delivery_date, driver,
    targeting, deliverable, batches, brief). Returns 201 + {sprint_id}.

    Auth: shares the bearer/query auth with the rest of the app.
    """
    from starlette.responses import JSONResponse

    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse({"error": "invalid json", "detail": str(exc)}, status_code=400)

    _normalize_payload(payload)

    intake = _load_intake_module()
    errors = intake.validate_payload(payload)
    if errors:
        return JSONResponse({"error": "validation failed", "details": errors}, status_code=422)

    sprint_id = intake.generate_sprint_id(payload)
    order = intake.build_order(payload, sprint_id)

    run_dir = RUNS_DIR / sprint_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "order.json").write_text(json.dumps(order, indent=2))

    # Run stage_01_load_refs immediately so context.json exists before anyone
    # tries to approve gate 2. Without this, --resume --gate 2 fails with
    # FileNotFoundError on context.json. Failure here is non-fatal; the order
    # is still saved and approve_gate will surface the issue with a clear msg.
    refs_warning = None
    try:
        rp = _load_run_pipeline_module()
        rp.stage_01_load_refs(sprint_id, order)
    except Exception as exc:  # pragma: no cover — defensive
        refs_warning = f"stage_01_load_refs failed: {exc!s}"

    (run_dir / "pipeline_state.json").write_text(json.dumps({
        "sprint_id": sprint_id,
        "state": "awaiting_gate_2",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    response = {
        "sprint_id": sprint_id,
        "state": "awaiting_gate_2",
        "submitted_at": order["submitted_at"],
        "next_step": "Open ADAM Pipeline in Claude and ask to drive this sprint through gate 2.",
    }
    if refs_warning:
        response["warning"] = refs_warning
    return JSONResponse(response, status_code=201)


async def _cors_preflight_handler(_request):
    """OPTIONS preflight for the order form submission."""
    from starlette.responses import Response
    return Response(status_code=204)


def _run_http() -> None:
    """Run as Streamable HTTP for hosted deployment.

    Adds optional bearer-token auth via the MCP_AUTH_TOKEN env var. If set,
    every request must include `Authorization: Bearer <token>`.
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    auth_token = os.environ.get("MCP_AUTH_TOKEN")

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/healthz" or request.method == "OPTIONS":
                response = await call_next(request)
            elif auth_token:
                header = request.headers.get("authorization", "")
                query_token = request.query_params.get("auth", "")
                bearer_ok = header == f"Bearer {auth_token}"
                query_ok = query_token == auth_token
                if not (bearer_ok or query_ok):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                response = await call_next(request)
            else:
                response = await call_next(request)
            response.headers["access-control-allow-origin"] = "*"
            response.headers["access-control-allow-methods"] = "GET, POST, OPTIONS"
            response.headers["access-control-allow-headers"] = "content-type, authorization"
            return response

    async def healthz(_request):
        return JSONResponse({"status": "ok"})

    middleware = [Middleware(BearerAuthMiddleware)]
    mcp_app = mcp.streamable_http_app()
    app = Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/submit-order", _submit_order_handler, methods=["POST"]),
            Route("/submit-order", _cors_preflight_handler, methods=["OPTIONS"]),
            Mount("/", app=mcp_app),
        ],
        middleware=middleware,
        lifespan=mcp_app.router.lifespan_context,
    )

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        _run_http()
    else:
        mcp.run()
