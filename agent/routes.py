"""FastAPI router for the gate orchestrator.

Routes:
  GET  /chat/ui                       — sprint-less playground chat
  GET  /sprints/{sprint_id}/chat      — sprint-bound chat with gate tabs (default UX)
  POST /chat                          — SSE stream of orchestrator events

Plug into whichever entry file exists (app.py / main.py):
    from agent.routes import router as agent_router
    app.include_router(agent_router)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .orchestrator import run_turn

router = APIRouter(tags=["agent"])

_THIS_DIR = Path(__file__).parent
_PLAYGROUND_UI = _THIS_DIR / "chat_ui.html"
_SPRINT_UI = _THIS_DIR / "sprint_chat_ui.html"


@router.get("/chat/ui", response_class=HTMLResponse)
async def chat_ui_playground() -> HTMLResponse:
    """Sprint-less chat (for ad-hoc testing). Sprint-bound chat is the default UX."""
    if not _PLAYGROUND_UI.exists():
        return HTMLResponse("<h1>chat_ui.html missing</h1>", status_code=500)
    return HTMLResponse(_PLAYGROUND_UI.read_text())


@router.get("/sprints/{sprint_id}/chat", response_class=HTMLResponse)
async def sprint_chat(sprint_id: str) -> HTMLResponse:
    """The default post-submission UX: chat bound to a sprint, with gate tabs on the right.

    The form's success screen redirects here. No API-key gate — anyone with the
    sprint URL can drive its gates. Add auth later via middleware if needed.
    """
    if not _SPRINT_UI.exists():
        return HTMLResponse("<h1>sprint_chat_ui.html missing</h1>", status_code=500)
    # Lightweight template substitution — avoid Jinja for a single placeholder.
    html = _SPRINT_UI.read_text().replace("__SPRINT_ID__", sprint_id)
    return HTMLResponse(html)


@router.post("/chat")
async def chat(request: Request):
    """Run one orchestrator turn.

    Request body:
      { "messages": [ {"role": "user", "content": "..."}, ... ],
        "sprint_id": "..."  (optional — when present, orchestrator is bound to this sprint) }
    """
    body = await request.json()
    messages: list[dict[str, Any]] = body.get("messages", [])
    sprint_id = body.get("sprint_id")

    async def event_stream():
        try:
            async for event in run_turn(messages, sprint_id=sprint_id):
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": f"{type(e).__name__}: {e}"})}

    return EventSourceResponse(event_stream())
