"""Local Python ports of the MCP server's 7 tools.

Each function reads/writes the project's runs/<sprint_id>/ directory
directly — no MCP transport, no Fly hop. The Claude API tool schemas at
the bottom mirror these function signatures so the model can call them.

Source of truth: mcp_server/server.py. If that changes, mirror here.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
PIPELINE_SCRIPT = REPO_ROOT / "pipeline" / "run_pipeline.py"

GATE_NAMES = {
    2: "order + refs confirmed",
    3: "copy approved",
    4: "image prompts approved",
    5: "images approved",
    6: "final QA approved",
}


# ── filesystem helpers ──────────────────────────────────────────────────────

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


# ── tool implementations (mirror mcp_server/server.py) ──────────────────────

def list_sprints(limit: int = 20) -> list[dict[str, Any]]:
    if not RUNS_DIR.exists():
        return []
    sprints = []
    for path in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        state = _read_json(path / "pipeline_state.json") or {}
        order = _read_json(path / "order.json") or {}
        sprints.append({
            "sprint_id": path.name,
            "state": state.get("state", "unknown"),
            "updated_at": state.get("updated_at"),
            "driver": order.get("driver"),
            "platform": order.get("platform"),
            "delivery_date": order.get("delivery_date"),
        })
        if len(sprints) >= limit:
            break
    return sprints


def get_sprint(sprint_id: str) -> dict[str, Any]:
    path = _sprint_dir(sprint_id)
    return {
        "sprint_id": sprint_id,
        "order": _read_json(path / "order.json"),
        "pipeline_state": _read_json(path / "pipeline_state.json"),
        "run_summary": _read_json(path / "run_summary.json"),
        "available_files": sorted(p.name for p in path.iterdir() if p.is_file()),
    }


def get_copy_concepts(sprint_id: str) -> dict[str, Any]:
    path = _sprint_dir(sprint_id)
    outputs = _read_json(path / "copy_outputs.json")
    review = _read_csv(path / "copy_review.csv")
    if not review and outputs:
        concepts = outputs.get("concepts") or []
        review = [{
            "Visual_Style": c.get("visual_style", ""),
            "rank": str(c.get("rank", "")),
            "selected": "YES" if c.get("selected") else "NO",
            "score": str(c.get("score", "")),
            "Headline_On_Creative": c.get("headline", ""),
            "Primary_Text_Short": c.get("body_short", c.get("body", "")),
            "Primary_Text_Long": c.get("body_long", ""),
            "Description": c.get("description", ""),
            "CTA": c.get("cta", ""),
            "concept_tag": c.get("concept_tag", ""),
            "review_notes": c.get("review_notes", ""),
        } for c in concepts]
    return {
        "sprint_id": sprint_id,
        "copy_outputs": outputs,
        "copy_review": review,
        "copy_review_source": (
            "csv" if (path / "copy_review.csv").exists() else "synthesized_from_copy_outputs"
        ),
    }


def get_image_prompts(sprint_id: str) -> list[dict[str, str]]:
    return _read_csv(_sprint_dir(sprint_id) / "image_prompts.csv")


def get_manifest(sprint_id: str) -> dict[str, Any]:
    path = _sprint_dir(sprint_id)
    return {
        "sprint_id": sprint_id,
        "asset_manifest": _read_csv(path / "asset_manifest.csv"),
        "plugin_manifest": _read_csv(path / "plugin_manifest.csv"),
    }


def get_generation_log(sprint_id: str) -> Any:
    return _read_json(_sprint_dir(sprint_id) / "generation_log.json")


def approve_gate(sprint_id: str, gate: int, timeout_seconds: int = 600) -> dict[str, Any]:
    if gate not in GATE_NAMES:
        raise ValueError(f"gate must be one of {sorted(GATE_NAMES)}; got {gate}")
    _sprint_dir(sprint_id)
    proc = subprocess.run(
        [sys.executable, str(PIPELINE_SCRIPT), "--resume", sprint_id, "--gate", str(gate)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=str(REPO_ROOT),
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


# ── Claude API tool schemas ─────────────────────────────────────────────────
# These define what the orchestrator can call. Names and parameters match
# the function names above so dispatch is a direct lookup.

CLAUDE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_sprints",
        "description": "List recent sprints with their current pipeline state. Use to find a sprint by date, driver, or platform when the user references one indirectly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max sprints to return (default 20, newest first)."}
            },
            "required": [],
        },
    },
    {
        "name": "get_sprint",
        "description": "Full state of one sprint: order, pipeline state, run summary, file list. Always call this first when starting a gate review.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_copy_concepts",
        "description": "Copy concepts + review scores. Call before approving Gate 3 (copy).",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_image_prompts",
        "description": "Image prompts CSV — one row per ad slot. Call before approving Gate 4 (prompts).",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_manifest",
        "description": "Asset manifest used by the Figma assembly plugin. Call before approving Gate 6 (final QA).",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_generation_log",
        "description": "Stage timings, model calls, errors. Use when debugging a stuck or failed sprint.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "approve_gate",
        "description": (
            "Approve a gate and resume the pipeline. This runs real LLM and Figma calls "
            "and can take several minutes. Only call after the human reviewer has explicitly "
            "approved the artifact for this gate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"},
                "gate": {
                    "type": "integer",
                    "enum": [2, 3, 4, 5, 6],
                    "description": "2=order+refs, 3=copy, 4=prompts, 5=images, 6=final QA",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Max wait before killing subprocess (default 600).",
                },
            },
            "required": ["sprint_id", "gate"],
        },
    },
]


# ── dispatch ────────────────────────────────────────────────────────────────

TOOL_DISPATCH = {
    "list_sprints": list_sprints,
    "get_sprint": get_sprint,
    "get_copy_concepts": get_copy_concepts,
    "get_image_prompts": get_image_prompts,
    "get_manifest": get_manifest,
    "get_generation_log": get_generation_log,
    "approve_gate": approve_gate,
}


def call_tool(name: str, args: dict[str, Any]) -> Any:
    """Look up and invoke a tool by name. Used by the orchestrator loop."""
    if name not in TOOL_DISPATCH:
        raise ValueError(f"unknown tool: {name}")
    return TOOL_DISPATCH[name](**args)
