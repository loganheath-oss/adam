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
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

_LOG = logging.getLogger("adam.orchestrator")
_SPRINT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_JSONL_LOCK = threading.Lock()


def _is_safe_sprint_id(sprint_id: str) -> bool:
    return bool(sprint_id and _SPRINT_ID_RE.match(sprint_id) and ".." not in sprint_id)

BASE_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE_DIR / "runs"
LEARNINGS_PATH = BASE_DIR / "learnings.md"

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _JSONL_LOCK:
            with path.open("a") as f:
                f.write(json.dumps(record) + "\n")
    except Exception as exc:
        _LOG.warning("orchestrator jsonl append failed for %s: %s", path, exc)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


LEARNINGS_HEADER = (
    "# ADAM Learnings\n\n"
    "Institutional memory shared across every sprint. Edit this file directly "
    "to add, refine, or remove guidance — Claude reads it at the start of every "
    "chat session.\n\n"
    "## Guidance\n\n"
)


def _ensure_learnings_file() -> None:
    if not LEARNINGS_PATH.exists():
        LEARNINGS_PATH.write_text(LEARNINGS_HEADER)


def read_learnings_text() -> str:
    """Public helper used by main.py to inject learnings elsewhere if needed."""
    if not LEARNINGS_PATH.exists():
        return ""
    return LEARNINGS_PATH.read_text()


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


def tool_get_references(sprint_id: str) -> dict:
    """Return the loaded reference context (context.json) for a sprint — what
    brand voice, claims, targeting examples, and refs were loaded at intake.
    This is what the user needs to see/approve at Gate 2."""
    path = RUNS_DIR / sprint_id / "context.json"
    if not path.exists():
        return {"error": f"context.json not found for sprint {sprint_id}"}
    ctx = _read_json(path) or {}
    return {
        "sprint_id": sprint_id,
        "source": ctx.get("source", ""),
        "order_brief": ctx.get("order_brief", ""),
        "refs_loaded": ctx.get("refs_loaded", 0),
        "targeting_examples": ctx.get("targeting_examples", ""),
        "order": ctx.get("order", {}),
    }


def tool_get_manifest(sprint_id: str) -> dict:
    """Return asset_manifest.csv rows — what's queued for assembly at Gate 5."""
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}
    rows = _read_csv(path / "asset_manifest.csv")
    return {"sprint_id": sprint_id, "rows": rows, "count": len(rows)}


def tool_approve_gate(sprint_id: str, gate: int, note: str = "") -> dict:
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
        _append_jsonl(path / "gate_decisions.jsonl", {
            "ts": _now(),
            "sprint_id": sprint_id,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "decision": "approved",
            "note": (note or "").strip(),
            "source": "agent",
        })
        return {
            "ok": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "new_state": new_state.get("state", "unknown"),
            "note_recorded": bool((note or "").strip()),
        }
    except Exception as exc:
        return {"error": str(exc)}


def tool_get_chat_history(sprint_id: str, limit: int = 50) -> dict:
    path = RUNS_DIR / sprint_id / "chat.jsonl"
    history = _read_jsonl(path)
    if limit and limit > 0:
        history = history[-limit:]
    return {"sprint_id": sprint_id, "count": len(history), "messages": history}


def tool_get_gate_decisions(sprint_id: str) -> dict:
    path = RUNS_DIR / sprint_id / "gate_decisions.jsonl"
    return {"sprint_id": sprint_id, "decisions": _read_jsonl(path)}


def tool_search_past_sprints(query: str, limit: int = 5) -> list[dict]:
    """Keyword search across past sprint artifacts: orders, summaries,
    chat transcripts, and gate decision notes. Case-insensitive substring match."""
    if not RUNS_DIR.exists() or not query:
        return []
    q = query.lower().strip()
    hits: list[dict] = []
    search_files = ("order.json", "run_summary.json", "chat.jsonl", "gate_decisions.jsonl")
    for p in sorted(RUNS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_dir():
            continue
        matched_in = []
        for fname in search_files:
            f = p / fname
            if f.exists() and q in f.read_text().lower():
                matched_in.append(fname)
        if not matched_in:
            continue
        order = _read_json(p / "order.json") or {}
        state = _read_json(p / "pipeline_state.json") or {}
        hits.append({
            "sprint_id": p.name,
            "state": state.get("state", ""),
            "driver": order.get("driver", ""),
            "platform": order.get("platform", ""),
            "delivery_date": order.get("delivery_date", ""),
            "matched_in": matched_in,
        })
        if len(hits) >= limit:
            break
    return hits


def tool_get_learnings() -> dict:
    _ensure_learnings_file()
    return {"path": str(LEARNINGS_PATH), "content": LEARNINGS_PATH.read_text()}


def tool_append_learning(text: str, source_sprint: str = "") -> dict:
    text = (text or "").strip()
    if not text:
        return {"error": "text is required"}
    _ensure_learnings_file()
    entry = f"- **{_now()[:10]}**"
    if source_sprint:
        entry += f" _(from `{source_sprint}`)_"
    entry += f": {text}\n"
    with LEARNINGS_PATH.open("a") as f:
        f.write(entry)
    return {"ok": True, "appended": entry.strip(), "path": str(LEARNINGS_PATH)}


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
        "name": "get_references",
        "description": "Get the loaded reference context for a sprint — brand voice, claims, refs loaded, targeting examples. Required to show the user at Gate 2.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_manifest",
        "description": "Get the asset manifest rows for a sprint — what's queued for assembly at Gate 5.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "approve_gate",
        "description": (
            "Approve a pipeline gate and resume the run. "
            "Gates: 2=Order+Refs, 3=Copy, 4=Image Prompts, 5=Assembly, 6=Final QA. "
            "Only call this after reviewing the relevant outputs. "
            "Always pass `note` capturing the user's rationale (one or two sentences "
            "explaining what they liked, what they changed, or any caveat) — this is "
            "persisted to gate_decisions.jsonl and becomes training memory for "
            "future sprints."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"},
                "gate": {"type": "integer", "enum": [2, 3, 4, 5, 6]},
                "note": {
                    "type": "string",
                    "description": "User's rationale for approving (1–2 sentences). Required for institutional memory.",
                },
            },
            "required": ["sprint_id", "gate"],
        },
    },
    {
        "name": "get_chat_history",
        "description": "Read the persisted chat transcript for a sprint (user + assistant messages, oldest first).",
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Max messages to return (default 50, 0 = all)", "default": 50},
            },
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_gate_decisions",
        "description": "Read all recorded gate approval decisions and notes for a sprint.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "search_past_sprints",
        "description": (
            "Keyword-search across past sprints (orders, summaries, chat transcripts, "
            "gate decisions). Use this when the user asks 'have we done X before?' or "
            "when you want to apply patterns from previous work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Case-insensitive substring to search for"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_learnings",
        "description": "Read the full ADAM learnings doc (institutional memory shared across all sprints).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "append_learning",
        "description": (
            "Append a new entry to the ADAM learnings doc. Use this when the user "
            "states a preference, a rule, or a lesson worth remembering across "
            "future sprints (e.g. 'never use exclamation points in headlines', "
            "'always include a price anchor for cold audiences'). Be concise and "
            "specific. Confirm with the user before appending unless they explicitly "
            "said 'remember this' or 'add to learnings'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The learning, in one sentence."},
                "source_sprint": {"type": "string", "description": "Sprint ID this learning came from (optional)."},
            },
            "required": ["text"],
        },
    },
]

TOOL_DISPATCH = {
    "list_sprints": lambda args: tool_list_sprints(**args),
    "get_sprint": lambda args: tool_get_sprint(**args),
    "get_copy_concepts": lambda args: tool_get_copy_concepts(**args),
    "get_image_prompts": lambda args: tool_get_image_prompts(**args),
    "get_references": lambda args: tool_get_references(**args),
    "get_manifest": lambda args: tool_get_manifest(**args),
    "approve_gate": lambda args: tool_approve_gate(**args),
    "get_chat_history": lambda args: tool_get_chat_history(**args),
    "get_gate_decisions": lambda args: tool_get_gate_decisions(**args),
    "search_past_sprints": lambda args: tool_search_past_sprints(**args),
    "get_learnings": lambda args: tool_get_learnings(),
    "append_learning": lambda args: tool_append_learning(**args),
}

SYSTEM_PROMPT = """You are the ADAM Pipeline assistant — a production coordinator for Upwork's automated ad creative pipeline.

# WHO YOU'RE TALKING TO

Assume the user has NEVER used this system before, doesn't know what a "gate" is, and doesn't know what files exist. They should never have to ask "what is this?" or "show me X" — you should already be showing it.

# THE GOLDEN RULE: SHOW, DON'T ANNOUNCE

NEVER say "Gate X is open" or "needs your approval" without ALSO, in the same message, displaying exactly what they're approving. Saying "Gate 2 is awaiting approval" by itself is a failure. Always pair the announcement with the artifact.

# YOUR JOB AT EACH GATE

When a sprint is in `awaiting_gate_N`, you must:

1. **Fetch the relevant artifact** with the right tool (see table below) — do this BEFORE writing your message to the user.
2. **Present it clearly** — use plain language, short headers, bullet lists, numbered concepts. Never dump raw JSON at them.
3. **Explain in one sentence** what this gate is checking and why it matters in plain English (no jargon — never use words like "intake", "manifest", or "QA" without defining them).
4. **End with an explicit prompt**: "Reply **approve** to continue, or tell me what to change." Always offer the option to change something.
5. **When they approve**, capture their reason in the `note` param of `approve_gate` (e.g. "user approved without changes" or "approved — said the second concept nailed the tone").

## Gate → tool → what to show

| Gate | Name | Tool to call FIRST | What to show |
|------|------|--------------------|--------------|
| 2 | Order + Refs | `get_sprint` + `get_references` | The order summary (driver, platform, format, quantity, styles, audience, due date) AND the reference context (how many refs were loaded, brand voice, targeting examples). Frame it: "Before we spend any AI credits, let's make sure I got the order right and loaded the right references." |
| 3 | Copy Review | `get_copy_concepts` | Every concept as a numbered list with **Headline** and **Body** in bold. Mark which ones the auto-reviewer selected/scored highest. Frame it: "Here are the ad copy concepts. Tell me which you want to ship, or approve all and we'll move to images." |
| 4 | Image Prompts | `get_image_prompts` | Each ad slot with its visual prompt as a numbered list. Frame it: "Here's what we'll send to the image model for each ad. Last chance to tweak the visual direction." |
| 5 | Assembly | `get_manifest` | The asset manifest rows showing which copy + image combos will be assembled. Frame it: "This is the final pairing of copy and visuals before we render the layouts." |
| 6 | Final QA | `get_sprint` (look at run_summary + available_files) | What got produced, file count, any flags. Frame it: "Everything is rendered. Here's what's ready for delivery." |

# OTHER BEHAVIORS

- **Opening a sprint chat**: immediately call `get_sprint` to find the current state, then proceed straight to the gate flow above. Don't say "let me check" — just fetch and show.
- **When state is `running`** (between gates): tell the user what stage is in progress and roughly what to expect next. Don't ask them to approve anything.
- **When state is `done`**: congratulate, summarize what was delivered (use `get_sprint` + `get_manifest`), and offer to capture any learnings via `append_learning`.
- **When state is `error` or `interrupted`**: show the error message clearly, suggest the retry endpoint, and ask if they want to investigate.
- **Learnings**: if the user says "remember this" / "next time" / "always" / "never" — offer to append to learnings. After a gate approval with a substantive note, consider offering to save the rule.
- **Cross-sprint context**: when starting a new sprint, briefly check `search_past_sprints` for the driver name or platform to surface relevant prior decisions, but don't bombard the user with history unless it's relevant.

# TONE

Concise. Friendly. Plain English. Bold the things that matter (headlines, decisions). Use bullets and numbered lists generously — wall-of-text replies are a failure. Never use words like "intake", "payload", "manifest" without an inline plain-English explanation."""


# ── Streaming Claude loop ─────────────────────────────────────────────────────

async def run_agent_turn(
    messages: list[dict],
    api_key: str,
    sprint_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run one turn of the Claude tool-use loop and yield SSE-formatted chunks.

    Each yielded string is a complete SSE line (e.g. 'data: <text>\n\n').
    The caller should stream these directly to the client.

    When sprint_id is set the system prompt is extended to bind the session to
    that sprint so Claude doesn't ask the user which sprint to work on.
    """
    import anthropic as _anthropic

    client = _anthropic.Anthropic(api_key=api_key)

    loop_messages = list(messages)

    system_prompt = SYSTEM_PROMPT

    learnings_text = read_learnings_text().strip()
    if learnings_text:
        system_prompt += (
            "\n\n# Institutional learnings\n\n"
            "The following is the live `learnings.md` doc — apply this guidance "
            "to every decision and recommendation in this session:\n\n"
            f"{learnings_text}"
        )

    if sprint_id:
        system_prompt += (
            f"\n\n# Sprint binding\n\nThis session is bound to sprint `{sprint_id}`. "
            "Do not ask the user which sprint to work on. Default every tool call "
            f"to sprint_id=\"{sprint_id}\" unless the user explicitly references a different one."
        )

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
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
