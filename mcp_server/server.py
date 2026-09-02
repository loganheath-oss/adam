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
# Env-overridable so the same tools can read the deployment's live runs dir.
# On Railway the backend sets RUNS_DIR=/data/runs (the persistent volume); when
# this module is imported into main.py the MCP tools then see live sprints.
# Unset (Fly / local stdio) falls back to the repo-baked runs/ dir as before.
RUNS_DIR = Path(os.environ.get("RUNS_DIR", str(REPO_ROOT / "runs")))
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
_default_hosts = "adam-pipeline-cm.fly.dev,adam-production-9618.up.railway.app,localhost,127.0.0.1"
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
def list_sprints(limit: int = 20) -> dict[str, Any]:
    """List recent sprints with their current pipeline state.

    Returns {sprints, total, truncated} — `total` is the real sprint count, so
    a capped page can never read as "all sprints" (audit 2026-07-30).

    Args:
        limit: Maximum number of sprints to return (default 20, newest first).
    """
    if not RUNS_DIR.exists():
        return {"sprints": [], "total": 0, "truncated": False}
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
    total = sum(1 for p in RUNS_DIR.iterdir() if p.is_dir()) if RUNS_DIR.exists() else 0
    return {"sprints": sprints, "total": total, "truncated": total > len(sprints)}


@mcp.tool()
def get_sprint(sprint_id: str) -> dict[str, Any]:
    """Get the full state of a single sprint: order, pipeline state, and run summary."""
    path = _sprint_dir(sprint_id)
    # Recursive inventory with explicit totals (audit 2026-07-30): top-level-only
    # listing hid images/ and finals/, making "complete inventory" claims
    # impossible — the model filled the gap by guessing.
    files = sorted(str(p.relative_to(path)) for p in path.rglob("*")
                   if p.is_file() and not p.name.startswith("."))
    per_dir: dict[str, int] = {}
    for f in files:
        top = f.split("/", 1)[0] if "/" in f else "(root)"
        per_dir[top] = per_dir.get(top, 0) + 1
    return {
        "sprint_id": sprint_id,
        "order": _read_json(path / "order.json"),
        "pipeline_state": _read_json(path / "pipeline_state.json"),
        "run_summary": _read_json(path / "run_summary.json"),
        "available_files": files[:400],
        "file_total": len(files),
        "files_truncated": len(files) > 400,
        "files_per_dir": per_dir,
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
    # Authoritative presentation fields (audit 2026-07-30): on_creative =
    # exactly what prints on the template; pipeline_flags with an explicit
    # none:true. Shared with the chat agent so claude.ai reviewers see the
    # same ground truth (this synth previously omitted the per-audience
    # copy at exactly the gate where it must be reviewed).
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from agent.orchestrator import _enrich_concept_view
    if isinstance(outputs, dict) and isinstance(outputs.get("concepts"), list):
        outputs = dict(outputs)
        outputs["concepts"] = [_enrich_concept_view(c) if isinstance(c, dict) else c
                               for c in outputs["concepts"]]
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
                "On_Creative_Fields": c.get("on_creative") or {},
                "Primary_Text_Short": c.get("body_short", c.get("body", "")),
                "Primary_Text_Long": c.get("body_long", ""),
                "Description": c.get("description", ""),
                "CTA": c.get("cta", ""),
                "targeting_copy": c.get("targeting_copy") or {},
                "pipeline_flags": c.get("pipeline_flags") or {"none": True},
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
    }


@mcp.tool()
def get_generation_log(sprint_id: str) -> Any:
    """Get the generation log — stage timings, model calls, errors."""
    return _read_json(_sprint_dir(sprint_id) / "generation_log.json")


@mcp.tool()
def approve_gate(sprint_id: str, gate: int, timeout_seconds: int = 600,
                 acknowledge_open_issues: bool = False) -> dict[str, Any]:
    """Approve a pipeline gate and resume the run.

    Shells out to `pipeline/run_pipeline.py --resume <sprint_id> --gate <gate>`.
    This will run real LLM and Figma calls and may take several minutes —
    the timeout defaults to 10 minutes.

    Args:
        sprint_id: e.g. "2026-04-meta-6677".
        gate: 2 (order+refs), 3 (copy), 4 (prompts), 5 (images), 6 (final QA).
        timeout_seconds: max wait before killing the subprocess.
        acknowledge_open_issues: sprints with OPEN issue tickets refuse a silent
            approval; pass True only after the human has seen the issues and
            explicitly chosen to proceed.

    Returns: {success, gate, gate_name, exit_code, stdout_tail, stderr_tail, new_state}
    """
    if gate not in GATE_NAMES:
        raise ValueError(f"gate must be one of {sorted(GATE_NAMES)}; got {gate}")
    sprint_dir = _sprint_dir(sprint_id)  # validate sprint exists

    # FLAG-TO-FIX LOOP (2026-09-01), same contract as the HTTP route and chat
    # tool. Fail-open: if the issues DB is unreachable from this process the
    # check returns [] and approval proceeds.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        import db as _db
        _open_issues = _db.open_issues_for(sprint_id)
    except Exception:
        _open_issues = []
    if _open_issues and not acknowledge_open_issues:
        return {
            "success": False,
            "requires_ack": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "open_issues": _open_issues,
            "error": (f"{len(_open_issues)} open issue(s) are filed against this sprint. "
                      "Surface them to the human; re-call with "
                      "acknowledge_open_issues=True only on their explicit go-ahead."),
        }

    # Cross-process CAS shared with the HTTP route and chat tool (audit
    # 2026-07-30): this path used to have NO state check at all — a retried
    # connector call ran the same stage twice in parallel processes.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import sprint_state
    won, prior = sprint_state.claim_gate(sprint_dir, gate)
    if not won:
        return {
            "success": False,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "error": f"Sprint is in state '{prior}', expected 'awaiting_gate_{gate}' — "
                     "the gate was already approved (possibly on another surface) or "
                     "isn't ready.",
            "new_state": sprint_state.read_state(sprint_dir),
        }

    proc = subprocess.Popen(
        [sys.executable, str(PIPELINE_SCRIPT), "--resume", sprint_id,
         "--gate", str(gate), "--claimed"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        # Do NOT kill the child: a SIGKILL mid-stage used to leave half-written
        # artifacts with the state still claiming the old gate. The stage keeps
        # running; the caller polls get_sprint for the outcome.
        return {
            "success": None,
            "still_running": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "message": f"The stage is still running after {timeout_seconds}s — it was "
                       "NOT interrupted. Check get_sprint for the new state; do not "
                       "re-approve.",
            "new_state": sprint_state.read_state(sprint_dir),
        }

    return {
        "success": proc.returncode == 0,
        "gate": gate,
        "gate_name": GATE_NAMES[gate],
        "exit_code": proc.returncode,
        "stdout_tail": stdout[-2000:] if stdout else "",
        "stderr_tail": stderr[-2000:] if stderr else "",
        "new_state": sprint_state.read_state(sprint_dir),
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
