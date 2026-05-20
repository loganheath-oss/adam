"""
agent/orchestrator.py
=====================
Phase 3 Claude tool-use loop for gate orchestration.

Gives Claude access to sprint inspection and gate-approval tools so it can
drive the ADAM pipeline from a chat interface without leaving the browser.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator

BASE_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE_DIR / "runs"

GATE_NAMES = {
    2: "Order + Refs Review",
    3: "Copy Review",
    4: "Image Prompt Scan",
    5: "Assembly Review",
    6: "Final QA",
}

GATE_HANDLERS: dict[int, Any] = {}

def _get_gate_handlers():
    global GATE_HANDLERS
    if not GATE_HANDLERS:
        import sys
        sys.path.insert(0, str(BASE_DIR / "pipeline"))
        from run_pipeline import resume_gate_2, resume_gate_3, resume_gate_4, resume_gate_5, resume_gate_6
        GATE_HANDLERS = {2: resume_gate_2, 3: resume_gate_3, 4: resume_gate_4, 5: resume_gate_5, 6: resume_gate_6}
    return GATE_HANDLERS


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# ── Tool implementations ──────────────────────────────────────────────────────

def tool_list_sprints(limit: int = 20) -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    sprints = []
    for p in sorted(RUNS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_dir():
            continue
        state = _read_json(p / "pipeline_state.json") or {}
        order = _read_json(p / "order.json") or {}
        sprints.append({
            "sprint_id": p.name,
            "state": state.get("state", "unknown"),
            "updated_at": state.get("updated_at", ""),
            "driver": order.get("driver", ""),
            "platform": order.get("platform", ""),
            "delivery_date": order.get("delivery_date", ""),
        })
        if len(sprints) >= limit:
            break
    return sprints


def tool_get_sprint(sprint_id: str) -> dict:
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}
    return {
        "sprint_id": sprint_id,
        "pipeline_state": _read_json(path / "pipeline_state.json"),
        "order": _read_json(path / "order.json"),
        "run_summary": _read_json(path / "run_summary.json"),
        "available_files": sorted(p.name for p in path.iterdir() if p.is_file()),
    }


def tool_get_copy_concepts(sprint_id: str) -> dict:
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}
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
                "Headline_On_Creative": c.get("headline", ""),
                "Primary_Text_Short": c.get("body_short", c.get("body", "")),
                "concept_tag": c.get("concept_tag", ""),
                "review_notes": c.get("review_notes", ""),
            }
            for c in concepts
        ]
    return {
        "sprint_id": sprint_id,
        "copy_outputs": outputs,
        "copy_review": review,
    }


def tool_get_image_prompts(sprint_id: str) -> list[dict]:
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return [{"error": f"Sprint not found: {sprint_id}"}]
    return _read_csv(path / "image_prompts.csv")


def tool_approve_gate(sprint_id: str, gate: int) -> dict:
    if gate not in GATE_NAMES:
        return {"error": f"gate must be one of {sorted(GATE_NAMES)}; got {gate}"}
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}

    state_data = _read_json(path / "pipeline_state.json") or {}
    current = state_data.get("state", "unknown")
    expected = f"awaiting_gate_{gate}"
    if current != expected:
        return {"error": f"Sprint is in state '{current}', expected '{expected}'"}

    try:
        handlers = _get_gate_handlers()
        handlers[gate](sprint_id)
        new_state = _read_json(path / "pipeline_state.json") or {}
        return {
            "ok": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "new_state": new_state.get("state", "unknown"),
        }
    except Exception as exc:
        return {"error": str(exc)}


# ── Tool schema for Claude ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "list_sprints",
        "description": "List recent pipeline sprints with their current state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max sprints to return (default 20)", "default": 20}
            },
        },
    },
    {
        "name": "get_sprint",
        "description": "Get the full state of a single sprint: order details, pipeline state, run summary, and available files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string", "description": "Sprint ID, e.g. '2026-04-meta-6677'"}
            },
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_copy_concepts",
        "description": "Get the generated ad copy concepts and review scores for a sprint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"}
            },
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_image_prompts",
        "description": "Get the image prompts CSV — what each ad slot is asking for visually.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"}
            },
            "required": ["sprint_id"],
        },
    },
    {
        "name": "approve_gate",
        "description": (
            "Approve a pipeline gate and resume the run. "
            "Gates: 2=Order+Refs, 3=Copy, 4=Image Prompts, 5=Assembly, 6=Final QA. "
            "Only call this after reviewing the relevant outputs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"},
                "gate": {"type": "integer", "enum": [2, 3, 4, 5, 6]},
            },
            "required": ["sprint_id", "gate"],
        },
    },
]

TOOL_DISPATCH = {
    "list_sprints": lambda args: tool_list_sprints(**args),
    "get_sprint": lambda args: tool_get_sprint(**args),
    "get_copy_concepts": lambda args: tool_get_copy_concepts(**args),
    "get_image_prompts": lambda args: tool_get_image_prompts(**args),
    "approve_gate": lambda args: tool_approve_gate(**args),
}

SYSTEM_PROMPT = """You are the ADAM Pipeline assistant — a hands-on production coordinator for Upwork's automated ad creative pipeline.

You help the user inspect sprint runs, review copy concepts and image prompts, approve pipeline gates, and troubleshoot issues.

Available tools:
- list_sprints — see all recent runs and their states
- get_sprint — full details for a specific sprint
- get_copy_concepts — ad copy and review scores at gate 3
- get_image_prompts — visual prompts for each ad slot at gate 4
- approve_gate — approve a gate and resume the pipeline

Be concise and action-oriented. When reviewing copy or prompts, summarise what you see before asking for approval. Always confirm gate approvals with the user before calling approve_gate unless they explicitly said to auto-approve."""


# ── Streaming Claude loop ─────────────────────────────────────────────────────

async def run_agent_turn(
    messages: list[dict],
    api_key: str,
) -> AsyncGenerator[str, None]:
    """
    Run one turn of the Claude tool-use loop and yield SSE-formatted chunks.

    Each yielded string is a complete SSE line (e.g. 'data: <text>\n\n').
    The caller should stream these directly to the client.
    """
    import anthropic as _anthropic

    client = _anthropic.Anthropic(api_key=api_key)

    loop_messages = list(messages)

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=loop_messages,
        )

        tool_uses = []
        text_blocks = []

        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_blocks:
            combined = "".join(text_blocks)
            yield f"data: {json.dumps({'type': 'text', 'text': combined})}\n\n"

        if response.stop_reason == "end_turn" or not tool_uses:
            break

        loop_messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tu in tool_uses:
            yield f"data: {json.dumps({'type': 'tool_call', 'name': tu.name, 'input': tu.input})}\n\n"

            try:
                result = TOOL_DISPATCH[tu.name](tu.input)
            except Exception as exc:
                result = {"error": str(exc)}

            yield f"data: {json.dumps({'type': 'tool_result', 'name': tu.name, 'result': result})}\n\n"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result),
            })

        loop_messages.append({"role": "user", "content": tool_results})

    yield "data: {\"type\": \"done\"}\n\n"
