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
# Read sprints from the SAME location main.py writes them. On Railway that's
# the persistent volume (/data/runs via the RUNS_DIR env var), NOT the empty
# runs/ folder baked into the image. Without this the chat's list_sprints /
# get_sprint tools look in the wrong directory and report "no sprints found"
# even while the web UI (which honors RUNS_DIR) shows the sprint at its gate.
RUNS_DIR = Path(os.environ.get("RUNS_DIR", str(BASE_DIR / "runs")))
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
                # Per-audience feed copy for Prospecting+Retargeting concepts, so the
                # operator can review BOTH versions (not just the prospecting mirror).
                "targeting_copy": c.get("targeting_copy") or {},
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


EDITABLE_TOP_LEVEL_FIELDS = ("brief", "delivery_date", "driver", "targeting")


def tool_edit_order(sprint_id: str, updates: dict) -> dict:
    """Modify the order BEFORE Gate 2 is approved. Supports changing:
      - brief (str)
      - delivery_date (YYYY-MM-DD)
      - driver (str)
      - targeting ("Prospecting" | "Retargeting" | "Both")
      - quantity (int) — total ads in the (single) batch; updates batches[0].quantity
        and rebalances style_quantities

    Only allowed while state == 'awaiting_gate_2' (before any AI generation).
    If brief or targeting changes, references are re-loaded automatically so the
    user sees the updated context at Gate 2.
    """
    if not isinstance(updates, dict) or not updates:
        return {"error": "updates must be a non-empty dict"}

    sprint_dir = RUNS_DIR / sprint_id
    if not sprint_dir.exists():
        return {"error": f"Sprint not found: {sprint_id}"}

    state_data = _read_json(sprint_dir / "pipeline_state.json") or {}
    current = state_data.get("state", "unknown")
    if current not in ("awaiting_gate_2", "queued"):
        return {
            "error": (
                f"Cannot edit order while sprint is in state '{current}'. "
                "Edits are only safe before Gate 2 is approved. Tell the user "
                "they would need to start a new order to change anything now."
            )
        }

    order_path = sprint_dir / "order.json"
    order = _read_json(order_path) or {}
    if not order:
        return {"error": "order.json not found or empty"}

    applied: dict = {}
    rejected: dict = {}

    # Top-level field updates
    for field in EDITABLE_TOP_LEVEL_FIELDS:
        if field in updates:
            new_val = updates[field]
            if not isinstance(new_val, str):
                rejected[field] = f"must be a string, got {type(new_val).__name__}"
                continue
            order[field] = new_val
            applied[field] = new_val

    # Quantity edit — single-batch only for v1
    if "quantity" in updates:
        try:
            qty = int(updates["quantity"])
            if qty < 1 or qty > 50:
                raise ValueError("quantity must be between 1 and 50")
        except (TypeError, ValueError) as exc:
            rejected["quantity"] = str(exc)
        else:
            batches = order.get("batches") or []
            if len(batches) != 1:
                rejected["quantity"] = (
                    f"quantity edits only supported for single-batch orders "
                    f"(this order has {len(batches)} batches); start a new order instead"
                )
            else:
                b = batches[0]
                old_qty = b.get("quantity", 0)
                b["quantity"] = qty
                # Rebalance style_quantities — distribute new total across existing styles.
                styles = list((b.get("style_quantities") or {}).keys()) or list(b.get("visual_styles") or [])
                if len(styles) == 1:
                    b["style_quantities"] = {styles[0]: qty}
                elif len(styles) > 1:
                    # Even split, remainder on first style.
                    base, extra = divmod(qty, len(styles))
                    sq = {s: base for s in styles}
                    sq[styles[0]] += extra
                    b["style_quantities"] = sq
                applied["quantity"] = {"old": old_qty, "new": qty, "rebalanced_styles": b.get("style_quantities")}

    # Reject any unsupported keys explicitly
    for k in updates:
        if k not in (*EDITABLE_TOP_LEVEL_FIELDS, "quantity") and k not in applied and k not in rejected:
            rejected[k] = "unsupported field — only brief, delivery_date, driver, targeting, quantity are editable"

    if not applied:
        return {"error": "no valid updates were applied", "rejected": rejected}

    # Write the order back.
    order_path.write_text(json.dumps(order, indent=2))

    # If brief or targeting changed, refresh references so context.json matches.
    refs_reloaded = False
    refs_error = ""
    if any(k in applied for k in ("brief", "targeting")):
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "pipeline"))
            from run_pipeline import stage_01_load_refs  # type: ignore
            context = stage_01_load_refs(sprint_id, order)
            (sprint_dir / "context.json").write_text(json.dumps(context, indent=2))
            refs_reloaded = True
        except Exception as exc:
            refs_error = f"refs reload failed: {exc}"

    # Audit trail in gate_decisions.jsonl so the edit shows up in memory.
    _append_jsonl(sprint_dir / "gate_decisions.jsonl", {
        "ts": _now(),
        "sprint_id": sprint_id,
        "gate": 2,
        "decision": "order_edited",
        "applied": applied,
        "rejected": rejected,
        "refs_reloaded": refs_reloaded,
        "source": "agent",
    })

    return {
        "ok": True,
        "sprint_id": sprint_id,
        "applied": applied,
        "rejected": rejected,
        "refs_reloaded": refs_reloaded,
        "refs_error": refs_error,
        "note": "Order updated. Show the user the new order summary and ask if they'd like to approve Gate 2 now, edit further, or cancel.",
    }


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

# ── Project wiki (docs/wiki) — powers grounded Q&A with clickable sources ─────
WIKI_DIR = BASE_DIR / "docs" / "wiki"


def _wiki_files() -> list[Path]:
    return sorted(WIKI_DIR.glob("*.md")) if WIKI_DIR.exists() else []


def _wiki_title(text: str, slug: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slug


def _wiki_anchor(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def tool_search_wiki(query: str, limit: int = 5) -> list[dict]:
    """Search the ADAM project wiki and return best-matching pages with the most
    relevant section + a snippet. Surfaced pages are shown to the user as
    clickable source previews automatically."""
    if not query or not WIKI_DIR.exists():
        return []
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if len(t) > 1]
    if not terms:
        return []
    results = []
    for p in _wiki_files():
        text = p.read_text()
        low = text.lower()
        page_score = sum(low.count(t) for t in terms)
        if page_score == 0:
            continue
        title = _wiki_title(text, p.stem)
        cur_head, cur_anchor, best = title, "", None
        for line in text.splitlines():
            hm = re.match(r"(#{1,6})\s+(.*)", line)
            if hm:
                cur_head = hm.group(2).strip()
                cur_anchor = _wiki_anchor(cur_head)
                continue
            s = sum(line.lower().count(t) for t in terms)
            if s and (best is None or s > best["score"]):
                best = {"score": s, "section": cur_head, "anchor": cur_anchor,
                        "snippet": line.strip()[:240]}
        anchor = best["anchor"] if best else ""
        results.append({
            "slug": p.stem,
            "title": title,
            "section": best["section"] if best else title,
            "anchor": anchor,
            "snippet": best["snippet"] if best else "",
            "url": f"/wiki/{p.stem}" + (f"#{anchor}" if anchor else ""),
            "_score": page_score + (best["score"] * 3 if best else 0),
        })
    results.sort(key=lambda r: r["_score"], reverse=True)
    for r in results:
        r.pop("_score", None)
    return results[:limit]


def tool_get_wiki(page: str) -> dict:
    """Read a full ADAM wiki page by slug (e.g. '02-architecture')."""
    slug = re.sub(r"[^A-Za-z0-9_-]", "", page or "")
    p = WIKI_DIR / f"{slug}.md"
    if not p.exists():
        return {"error": f"wiki page not found: {page}",
                "available_pages": [f.stem for f in _wiki_files()]}
    text = p.read_text()
    return {"slug": slug, "title": _wiki_title(text, slug),
            "url": f"/wiki/{slug}", "content": text}


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
        "name": "edit_order",
        "description": (
            "Modify the order while a sprint is still at Gate 2 (before any AI generation). "
            "Use this when the user wants to change the brief, delivery date, driver, targeting, "
            "or total ad quantity. Editable keys: brief, delivery_date (YYYY-MM-DD), driver, "
            "targeting (Prospecting|Retargeting|Both), quantity (int). If brief or targeting "
            "changes, references are auto-reloaded. After calling, always re-fetch the order "
            "(get_sprint / get_references) and show the updated summary to the user. Errors "
            "out cleanly if the sprint has already passed Gate 2 — in that case tell the user "
            "they need to start a new order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_id": {"type": "string"},
                "updates": {
                    "type": "object",
                    "description": "Dict of {field: new_value}. Only listed fields are accepted.",
                    "properties": {
                        "brief": {"type": "string"},
                        "delivery_date": {"type": "string"},
                        "driver": {"type": "string"},
                        "targeting": {"type": "string"},
                        "quantity": {"type": "integer"},
                    },
                },
            },
            "required": ["sprint_id", "updates"],
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
    {
        "name": "search_wiki",
        "description": (
            "Search the ADAM project wiki — how the tool is built, where things "
            "live, how to run/deploy/operate/fix it, the glossary, and handoff. "
            "Call this BEFORE answering any 'how does this work / where is / why / "
            "what is / how do I' question. The pages you surface are shown to the "
            "user as clickable source previews automatically, so don't paste long "
            "quotes — answer in your own words and reference the section."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look up, e.g. 'how is copy generated' or 'railway deploy'."},
                "limit": {"type": "integer", "description": "Max pages to return (default 5).", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_wiki",
        "description": "Read a full ADAM wiki page by slug (e.g. '02-architecture', '11-troubleshooting'). Use after search_wiki to read a page in full before answering in detail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {"type": "string", "description": "Wiki page slug, e.g. '04-the-pipeline'."},
            },
            "required": ["page"],
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
    "edit_order": lambda args: tool_edit_order(**args),
    "approve_gate": lambda args: tool_approve_gate(**args),
    "get_chat_history": lambda args: tool_get_chat_history(**args),
    "get_gate_decisions": lambda args: tool_get_gate_decisions(**args),
    "search_past_sprints": lambda args: tool_search_past_sprints(**args),
    "get_learnings": lambda args: tool_get_learnings(),
    "append_learning": lambda args: tool_append_learning(**args),
    "search_wiki": lambda args: tool_search_wiki(**args),
    "get_wiki": lambda args: tool_get_wiki(**args),
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
| 2 | Order + Refs | `get_sprint` + `get_references` | The order summary (driver, platform, format, quantity, styles, audience, due date) AND the reference context (how many refs were loaded, brand voice, targeting examples). Frame it: "Before we spend any AI credits, let's make sure I got the order right and loaded the right references." **If the user asks to change the brief, quantity, delivery date, driver, or targeting at this gate, call `edit_order` to apply the change, then re-show the updated summary. Do NOT tell them you can't change it — you can.** |
| 3 | Copy Review | `get_copy_concepts` | Every concept as a numbered list with **Headline** and **Body** in bold. Mark which ones the auto-reviewer selected/scored highest. **If a concept has `targeting_copy` (a Prospecting+Retargeting order), show BOTH audience versions of the feed copy — a **Prospecting** block and a **Retargeting** block (headline + short/long body each) — clearly labeled, since they genuinely differ; the on-creative headline is shared.** Frame it: "Here are the ad copy concepts. Tell me which you want to ship, or approve all and we'll move to images." |
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

# ANSWERING "HOW DOES THIS WORK?" QUESTIONS

You have a full project wiki covering how ADAM is built, where everything lives, how to run/deploy/operate/fix it, the glossary, and handoff. For ANY question that isn't a specific sprint's gate flow — "how does X work", "where is Y", "why", "what is", "how do I deploy/fix/add" — call `search_wiki` FIRST (and `get_wiki` to read a page in full), then answer in plain English based on what they return. The wiki pages you surface are shown to the user automatically as clickable source previews, so don't paste long quotes — summarize and point them to the right section. If the wiki doesn't cover something, say so plainly instead of guessing.

# TONE

Concise. Friendly. Plain English. Bold the things that matter (headlines, decisions). Use bullets and numbered lists generously — wall-of-text replies are a failure. Never use words like "intake", "payload", "manifest" without an inline plain-English explanation."""


# ── "Ask ADAM" wiki helper: a separate, restricted, read-only assistant ───────
# Used for the public standalone chat. It can ONLY read the wiki — no access to
# orders, sprints, gates, or learnings — so it's safe to expose without a login.
WIKI_TOOLS = [t for t in TOOLS if t["name"] in ("search_wiki", "get_wiki")]

WIKI_SYSTEM_PROMPT = """You are "Ask ADAM" — a friendly help assistant for the ADAM ad-creative tool. Your ONLY job is to help people understand and navigate the tool by answering questions from the project wiki.

# HOW TO ANSWER
- For ANY question, call `search_wiki` FIRST (and `get_wiki` to read a page in full), then answer in plain English based on what you find. The pages you surface appear to the user as clickable source previews, so don't paste long quotes — summarize and point them to the right page/section.
- If the wiki doesn't cover something, say so plainly instead of guessing.

# WHAT YOU CANNOT DO
- You do NOT run, change, or approve anything. You cannot submit orders, generate copy or images, inspect a specific sprint, or approve gates — you have no tools for any of that, on purpose.
- If someone asks you to DO something operational ("approve gate 3", "start an order", "show me sprint X"), explain that Ask ADAM only answers questions about how the tool works, and point them to the right place — "Start a new order" on the home page, or the **Sprints** page — then offer to explain how that part works using the wiki.

# TONE
Concise and friendly. Short paragraphs and bullets. Plain English — define any jargon inline."""


# ── Streaming Claude loop ─────────────────────────────────────────────────────

async def run_agent_turn(
    messages: list[dict],
    api_key: str,
    sprint_id: str | None = None,
    wiki_only: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Run one turn of the Claude tool-use loop and yield SSE-formatted chunks.

    Each yielded string is a complete SSE line (e.g. 'data: <text>\n\n').
    The caller should stream these directly to the client.

    When sprint_id is set the system prompt is extended to bind the session to
    that sprint so Claude doesn't ask the user which sprint to work on.

    When wiki_only is True this becomes the public "Ask ADAM" helper: only the
    read-only wiki tools are exposed (no orders/sprints/gates/learnings).
    """
    import anthropic as _anthropic

    client = _anthropic.Anthropic(api_key=api_key)

    loop_messages = list(messages)

    if wiki_only:
        active_tools = WIKI_TOOLS
        system_prompt = WIKI_SYSTEM_PROMPT
    else:
        active_tools = TOOLS
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

    wiki_sources: dict = {}

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            tools=active_tools,
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

            # Track wiki pages surfaced this turn → emitted as clickable sources.
            if tu.name == "search_wiki" and isinstance(result, list):
                for hit in result:
                    if hit.get("slug"):
                        wiki_sources[(hit["slug"], hit.get("anchor", ""))] = {
                            "slug": hit["slug"], "title": hit.get("title", ""),
                            "section": hit.get("section", ""), "anchor": hit.get("anchor", ""),
                            "url": hit.get("url"), "snippet": hit.get("snippet", ""),
                        }
            elif tu.name == "get_wiki" and isinstance(result, dict) and result.get("slug"):
                wiki_sources.setdefault((result["slug"], ""), {
                    "slug": result["slug"], "title": result.get("title", ""),
                    "section": "", "anchor": "", "url": result.get("url"), "snippet": "",
                })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result),
            })

        loop_messages.append({"role": "user", "content": tool_results})

    if wiki_sources:
        yield f"data: {json.dumps({'type': 'sources', 'sources': list(wiki_sources.values())})}\n\n"

    yield "data: {\"type\": \"done\"}\n\n"
