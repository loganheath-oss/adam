"""
agent/orchestrator.py
=====================
Phase 3 Claude tool-use loop for gate orchestration.

Gives Claude access to sprint inspection and gate-approval tools so it can
drive the ADAM pipeline from a chat interface without leaving the browser.
"""
from __future__ import annotations

import asyncio
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
import sys as _sys
if str(BASE_DIR) not in _sys.path:
    _sys.path.insert(0, str(BASE_DIR))
import sprint_state as _sprint_state  # atomic cross-process state (audit 2026-07-30)
# Read sprints from the SAME location main.py writes them. On Railway that's
# the persistent volume (/data/runs via the RUNS_DIR env var), NOT the empty
# runs/ folder baked into the image. Without this the chat's list_sprints /
# get_sprint tools look in the wrong directory and report "no sprints found"
# even while the web UI (which honors RUNS_DIR) shows the sprint at its gate.
RUNS_DIR = Path(os.environ.get("RUNS_DIR", str(BASE_DIR / "runs")))
# LEARNINGS must live on PERSISTENT storage. It used to sit on the container FS
# (BASE_DIR), where every deploy reset it to the git copy — silently wiping every
# operator-appended learning (found 2026-07-29: Adrie's logged items vanished).
# On Railway, RUNS_DIR is on the /data volume — keep learnings beside it; seed the
# volume copy from the repo file on first touch so the baseline content carries over.
_REPO_LEARNINGS = BASE_DIR / "learnings.md"
if str(RUNS_DIR).startswith("/data"):
    LEARNINGS_PATH = RUNS_DIR.parent / "learnings.md"
    try:
        if not LEARNINGS_PATH.exists() and _REPO_LEARNINGS.exists():
            LEARNINGS_PATH.write_text(_REPO_LEARNINGS.read_text())
    except Exception:
        LEARNINGS_PATH = _REPO_LEARNINGS
else:
    LEARNINGS_PATH = _REPO_LEARNINGS

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
    # RECURSIVE inventory (audit 2026-07-30): the old listing showed top-level
    # files only, so everything inside images/ and finals/ was invisible and
    # the Gate-6 "complete inventory" spec was structurally impossible — the
    # model filled the gap by guessing. Facts the model presents must be
    # computed here, never derived by it.
    files = sorted(str(p.relative_to(path)) for p in path.rglob("*")
                   if p.is_file() and not p.name.startswith("."))
    per_dir: dict[str, int] = {}
    for f in files:
        top = f.split("/", 1)[0] if "/" in f else "(root)"
        per_dir[top] = per_dir.get(top, 0) + 1
    truncated = len(files) > 400
    return {
        "sprint_id": sprint_id,
        "pipeline_state": _read_json(path / "pipeline_state.json"),
        "order": _read_json(path / "order.json"),
        "run_summary": _read_json(path / "run_summary.json"),
        "available_files": files[:400],
        "file_total": len(files),
        "files_truncated": truncated,
        "files_per_dir": per_dir,
    }


# The copy PRINTED ON the creative, per style — ordered. Styles with their own
# field set (sticky/poll/us-vs-them/…) print these, NOT creative_headline.
_ON_CREATIVE_FIELDS = [
    "single_headline", "single_bullets",
    "left_headline", "left_bullets", "right_headline", "right_bullets",
    "us_headline", "us_bullets", "them_headline", "them_bullets",
    "poll_question", "poll_option_a", "poll_pct_a", "poll_option_b", "poll_pct_b",
    "testimonial_quote", "testimonial_author",
    "chat_label", "chat_message", "button_text",
    "pie_center", "pie_labels",
    "profile_name", "profile_title", "profile_left", "profile_right",
    "search_results",
]


def _enrich_concept_view(c: dict) -> dict:
    """Attach the AUTHORITATIVE presentation data the model must not compute
    itself (audit 2026-07-30: the agent mislabeled fields and repeated an
    invented violation from its own earlier chat message, calling it 'a
    pipeline flag'). `on_creative` = exactly what prints on the template;
    `pipeline_flags` = the ONLY reportable violations, with an explicit
    none:true so 'no flags' is a positive fact, not an absence."""
    c = dict(c)
    on_creative = {f: c[f] for f in _ON_CREATIVE_FIELDS if c.get(f) not in (None, "")}
    if not on_creative:
        for f in ("creative_headline", "creative_subhead"):
            if c.get(f) not in (None, ""):
                on_creative[f] = c[f]
        c["on_creative"] = on_creative
    else:
        c["on_creative"] = on_creative
        c["on_creative_note"] = (
            "This style prints ONLY these fields on the creative; they are shared "
            "across audiences (targeting_copy varies FEED copy only). "
            "creative_headline is an auxiliary concept label, not printed."
        )
    flags = {k: c.get(k) for k in ("legal_flags", "length_flags", "length_warnings")
             if c.get(k)}
    c["pipeline_flags"] = flags if flags else {"none": True}
    return c


def tool_get_copy_concepts(sprint_id: str) -> dict:
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}
    outputs = _read_json(path / "copy_outputs.json")
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
    # Deterministic per-style tallies so counts in presentations are DATA, not
    # model arithmetic (audit 2026-07-30: every fact the model can miscompute,
    # Python computes instead).
    summary: dict[str, dict] = {}
    for c in ((outputs or {}).get("concepts") or []):
        st = c.get("visual_style", "unknown")
        s = summary.setdefault(st, {"generated": 0, "selected": 0, "flagged": 0})
        s["generated"] += 1
        if c.get("selected"):
            s["selected"] += 1
        if c.get("legal_flags") or c.get("length_flags"):
            s["flagged"] += 1
    return {
        "sprint_id": sprint_id,
        "copy_outputs": outputs,
        "copy_review": review,
        "style_summary": summary,
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


def tool_log_issue(description: str, sprint_id: str = "", category: str = "") -> dict:
    """Log an issue to the running admin Issues list (same store the /admin/issues
    page and digest read). Lets the operator file an issue WITHOUT leaving chat."""
    d = (description or "").strip()
    if not d:
        return {"ok": False, "error": "A description is required."}
    try:
        import db as _db
        ok = _db.report_issue(description=d[:4000],
                              user_email="chat-operator",
                              sprint_id=(sprint_id or None),
                              category=(category or None), context=None)
        return {"ok": bool(ok),
                "note": "Logged to the admin Issues list." if ok else "Issue tracking DB unavailable."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


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


# Set by main.py at startup: schedules the SAME background _run_gate_task the
# HTTP Approve button uses, so a chat approval never runs a whole gate stage
# inline on the event loop (it froze every request for minutes — audit
# 2026-07-30). Standalone/no-web use falls back to the inline handler.
APPROVE_HOOK = None


def tool_approve_gate(sprint_id: str, gate: int, note: str = "") -> dict:
    if gate not in GATE_NAMES:
        return {"error": f"gate must be one of {sorted(GATE_NAMES)}; got {gate}"}
    path = RUNS_DIR / sprint_id
    if not path.exists():
        return {"error": f"Sprint not found: {sprint_id}"}

    # Cross-process CAS — the same claim the HTTP route and MCP connector use,
    # so simultaneous approvals on different surfaces can't run a stage twice.
    won, prior = _sprint_state.claim_gate(path, gate)
    if not won:
        return {"error": f"Sprint is in state '{prior}', expected 'awaiting_gate_{gate}'"}

    _append_jsonl(path / "gate_decisions.jsonl", {
        "ts": _now(),
        "sprint_id": sprint_id,
        "gate": gate,
        "gate_name": GATE_NAMES[gate],
        "decision": "approved",
        "note": (note or "").strip(),
        "source": "agent",
    })
    try:
        import db as _db
        _order = _read_json(path / "order.json") or {}
        _db.log_event("gate.approved",
                      user_email=(_order.get("email") or _order.get("driver")),
                      sprint_id=sprint_id,
                      meta={"gate": gate, "gate_name": GATE_NAMES[gate], "source": "agent"})
    except Exception:
        pass

    if APPROVE_HOOK is not None:
        try:
            APPROVE_HOOK(sprint_id, gate)
        except Exception as exc:
            return {"error": f"approved but failed to start the stage: {exc}"}
        return {
            "ok": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "new_state": f"resuming_gate_{gate}",
            "running_in_background": True,
            "note_recorded": bool((note or "").strip()),
            "message": "Stage is running in the background — progress and the "
                       "next gate will appear here when it finishes.",
        }

    # Standalone fallback (no web app): run the stage inline as before.
    try:
        handlers = _get_gate_handlers()
        handlers[gate](sprint_id)
        new_state = _read_json(path / "pipeline_state.json") or {}
        return {
            "ok": True,
            "gate": gate,
            "gate_name": GATE_NAMES[gate],
            "new_state": new_state.get("state", "unknown"),
            "note_recorded": bool((note or "").strip()),
        }
    except Exception as exc:
        return {"error": str(exc)}


def tool_get_chat_history(sprint_id: str, limit: int = 200) -> dict:
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
        "name": "log_issue",
        "description": ("Log an issue the operator reports to the running admin Issues list "
                        "(visible at /admin/issues and counted in the digest). Use whenever the "
                        "user describes a problem, bug, or quality complaint and confirms logging "
                        "— or says 'log this'. Include sprint_id when it relates to this sprint."),
        "input_schema": {"type": "object", "properties": {
            "description": {"type": "string"},
            "sprint_id": {"type": "string"},
            "category": {"type": "string"}},
            "required": ["description"]},
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
    "log_issue": lambda args: tool_log_issue(**args),
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
| 2 | Order + Refs | `get_sprint` + `get_references` | EVERY order field (driver, platform, format, quantity, styles, audience, due date) AND the BRIEF **VERBATIM AND COMPLETE — never paraphrased, never truncated** (it is the creative contract being approved) AND the reference context (refs loaded, brand voice, targeting examples). **If the order has NO brief, lead with a prominent warning and offer `edit_order`.** If the user asks to change anything, apply via `edit_order` and re-show. |
| 3 | Copy Review | `get_copy_concepts` | Every concept with FULL field detail on the FIRST presentation — NEVER a summary view (real operator complaint 2026-07-29: summarizing forced a second ask). For EACH selected concept show: on-creative headline (per audience on P&R orders), Headline long AND short, Body/Primary short AND long, CTA. Mark which ones the auto-reviewer selected/scored highest. **If a concept has `targeting_copy` (a Prospecting+Retargeting order), show BOTH audience versions — a **Prospecting** block and a **Retargeting** block, each with its OWN on-creative headline AND feed copy (headline + short/long body) — clearly labeled. Every audience gets distinct on-creative copy now; if an audience block appears to be missing its on-creative or feed fields, that is a defect to flag, not a variation to gloss over.** Frame it: "Here are the ad copy concepts. Tell me which you want to ship, or approve all and we'll move to images." |
| 4 | Image Prompts | `get_image_prompts` | EVERY ad slot with its visual prompt **IN FULL — never shortened or paraphrased** (the operator is approving these exact words going to the image model). Continue across messages if long. |
| 5 | Assembly | `get_manifest` | EVERY manifest row's copy+image pairing — style, audience, size, on-creative copy, photo/asset per row. **Do not sample or summarize rows**; group by style and continue across messages if long. |
| 6 | Final QA | `get_sprint` (run_summary + available_files) | The COMPLETE list of what was produced (every file, every flag, counts) — nothing elided. |

# OTHER BEHAVIORS

- **Opening a sprint chat**: immediately call `get_sprint` to find the current state, then proceed straight to the gate flow above. Don't say "let me check" — just fetch and show.
- **When state is `running`** (between gates): tell the user what stage is in progress and roughly what to expect next. Don't ask them to approve anything.
- **When state is `done`**: congratulate, summarize what was delivered (use `get_sprint` + `get_manifest`), and offer to capture any learnings via `append_learning`.
- **When state is `error` or `interrupted`**: show the error message clearly, suggest the retry endpoint, and ask if they want to investigate.
- **Learnings**: if the user says "remember this" / "next time" / "always" / "never" — offer to append to learnings. After a gate approval with a substantive note, consider offering to save the rule.
- **Cross-sprint context**: when starting a new sprint, briefly check `search_past_sprints` for the driver name or platform to surface relevant prior decisions, but don't bombard the user with history unless it's relevant.

# OPERATOR TRANSPARENCY — NON-NEGOTIABLE, AT EVERY GATE

The human operator must see ALL of ADAM's work up front, easily, leaving nothing to
assumption (Logan, 2026-07-29). This overrides brevity everywhere:
- At EVERY gate, present the COMPLETE work product on the first message — never a
  summary, never "ask if you want more", never a representative sample. Long messages
  are correct here; hiding work is the failure mode.
- Gate 3 specifically: show EVERY concept generated, not just the selected ones —
  selected concepts first in full field detail (on-creative per audience, headline
  long+short, body short+long, CTA), then every non-selected concept with its copy and
  why it ranked lower. The operator judges the whole body of work, including what the
  auto-reviewer rejected.
- ON-CREATIVE means THE STYLE'S OWN on-image fields. For styles with their own field
  set (Sticky Note: single_headline + single_bullets + left/right headline + bullets;
  Poll: poll_question/options/percentages; Us vs Them, Pie Chart, Chat Bubble,
  Search Results, Social Media Profile: their extra fields), present THOSE fields as
  the on-creative copy — every one of them, verbatim. For those styles
  creative_headline is an auxiliary label that is NOT printed on the template; if you
  show it, label it "concept label", never "On-creative". (2026-07-30: the assistant
  labeled Sticky's auxiliary 12-char label "On-creative" and omitted the real sticky
  copy — the operator concluded ADAM produced two-word ads while the actual on-sticky
  fields were healthy and complete.)
- NEVER invent a violation. Each concept from get_copy_concepts carries
  `pipeline_flags` — the ONLY reportable violations. `pipeline_flags: {"none": true}`
  is a POSITIVE fact: this concept has no violations and you may not mention any —
  not even one asserted in an EARLIER chat message (earlier messages can contain
  since-corrected mistakes; the tool data always supersedes chat history). Do NOT do
  your own character-cap math. (2026-07-30, twice: the assistant announced a "Hard
  violation: 39 vs 26" from its own math, and later repeated it from chat history
  while claiming it was "a pipeline flag" — the concept had NO flags either time.)
- Each concept also carries `on_creative` — the AUTHORITATIVE on-creative copy,
  computed by the pipeline. Present exactly those field names and values; never
  substitute another field's value into an on-creative label. When
  `on_creative_note` says the fields are shared across audiences, say so — do not
  invent per-audience on-creative versions.
- Copy fields are quoted VERBATIM — full text, lead-in sentences, line breaks, emoji —
  never shortened for display (2026-07-30: the assistant trimmed body_long lead-ins in
  chat while the data was complete; the operator noticed. Rendering IS the product here).
- If output is too long for one message, continue in the next message — do NOT truncate
  or summarize to fit.

# DIAGNOSTIC HONESTY — when output looks wrong or missing

This rule exists because of a real incident (2026-07-27): a user asked why most ad styles
had no on-creative copy, and the assistant answered "by design, not a bug" — which was
FALSE (it was a generation defect, later fixed). Never repeat that failure mode.

- When the user reports missing, blank, or incomplete output (empty body copy, missing
  headlines, absent on-creative text, fewer choices than expected): FIRST inspect the
  actual data field-by-field with `get_copy_concepts` (or the relevant tool) and report
  exactly which fields are filled vs empty, per concept.
- NEVER claim missing output is "by design" or intentional unless the wiki or the Ad
  Type Style Guide EXPLICITLY documents that behavior — and cite the page. Every ad
  style is required to produce on-creative copy, long+short headlines, long+short body,
  and (on Prospecting+Retargeting orders) two choices per audience. A gap in any of
  those is a defect, full stop.
- When data looks incomplete: say plainly "this looks like a defect, not intended
  behavior", recommend logging it on the Issues page so the engineer sees it, and offer
  the practical workaround (approve the clean styles, hold the broken one). Do NOT
  invent a reassuring explanation. An honest "this looks broken" preserves trust; a
  confident wrong answer destroys it.

# ANSWERING "HOW DOES THIS WORK?" QUESTIONS

You have a full project wiki covering how ADAM is built, where everything lives, how to run/deploy/operate/fix it, the glossary, and handoff. For ANY question that isn't a specific sprint's gate flow — "how does X work", "where is Y", "why", "what is", "how do I deploy/fix/add" — call `search_wiki` FIRST (and `get_wiki` to read a page in full), then answer in plain English based on what they return. The wiki pages you surface are shown to the user automatically as clickable source previews, so don't paste long quotes — summarize and point them to the right section. If the wiki doesn't cover something, say so plainly instead of guessing.

# TONE

Concise. Friendly. Plain English. Bold the things that matter (headlines, decisions). Use bullets and numbered lists generously — wall-of-text replies are a failure. Never use words like "intake", "payload", "manifest" without an inline plain-English explanation."""


# ── AUTHORITY MAP (generated — authority.py is the single source of truth) ───
# Every task the model performs carries a declared authority level (PRESENT /
# EXPLAIN / JUDGE / CREATE / ACTION). Generated into the prompt so no task can
# reach the agent unclassified; docs/AUTHORITY.md is the human twin and the
# regression suite fails if either drifts (Logan's slider concept, 2026-07-30).
try:
    import authority as _authority
    SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + _authority.render_prompt_section()
except Exception as _ae:  # never let a registry bug take chat down
    _LOG.warning("authority map not appended: %s", _ae)

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

    client = _anthropic.AsyncAnthropic(api_key=api_key)

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

    # Output budget must EXCEED what the transparency law demands. A full Gate-3
    # presentation (12 concepts x 2 audiences x all fields, verbatim) runs 6-8k
    # tokens; the old 2048 cap made "show everything" arithmetically impossible,
    # so the model silently compressed — Adrie's truncated lead-ins, 2026-07-30.
    max_out = int(os.environ.get("ADAM_CHAT_MAX_TOKENS", "16000"))
    continuations = 0

    while True:
        # ASYNC client (audit 2026-07-30): the sync client ran a minutes-long
        # model call ON the event loop, freezing every other request — state
        # polls, other users' chats, /health — for the whole turn. The await
        # yields the loop; the keepalive comments stop edge proxies from
        # idle-killing the otherwise-silent SSE stream (both chat clients skip
        # non-`data:` parts, so the comments are invisible to them).
        _call = asyncio.ensure_future(client.messages.create(
            # Sonnet 5 with thinking explicitly DISABLED: no thinking blocks are emitted,
            # so the tool-use loop sees the same shapes as 4.6 (2026-07-28). Env-tunable.
            model=os.environ.get("ADAM_CHAT_MODEL", "claude-sonnet-5"),
            thinking={"type": "disabled"},
            max_tokens=max_out,
            system=system_prompt,
            tools=active_tools,
            messages=loop_messages,
        ))
        while True:
            _done, _ = await asyncio.wait({_call}, timeout=15)
            if _done:
                break
            yield ": keepalive\n\n"
        response = _call.result()

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

        # Safety net: if the response still hit the output ceiling mid-message
        # (no pending tool calls to naturally continue the loop), auto-continue
        # instead of silently shipping a truncated presentation. Capped so a
        # pathological loop can't run away.
        if response.stop_reason == "max_tokens" and not tool_uses and continuations < 3:
            continuations += 1
            loop_messages.append({"role": "assistant", "content": response.content})
            loop_messages.append({
                "role": "user",
                "content": "[SYSTEM: your message hit the output limit mid-stream. "
                           "Continue EXACTLY where you left off — do not repeat text "
                           "already sent, do not summarize, do not apologize.]",
            })
            continue

        if response.stop_reason == "end_turn" or not tool_uses:
            break

        loop_messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tu in tool_uses:
            yield f"data: {json.dumps({'type': 'tool_call', 'name': tu.name, 'input': tu.input})}\n\n"

            try:
                # Off-loop dispatch (audit 2026-07-30): tool bodies do file and
                # DB I/O — run them in a worker thread so the SSE stream (and
                # every other request) stays live while they work.
                result = await asyncio.to_thread(TOOL_DISPATCH[tu.name], tu.input)
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
