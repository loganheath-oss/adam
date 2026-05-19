"""FastAPI router for the gate orchestrator.

Plug into whichever entry file exists (app.py / main.py):

    from agent.routes import router as agent_router
    app.include_router(agent_router)

After include: GET  /chat/ui   → minimal chat UI (HTML).
               POST /chat      → SSE stream of orchestrator events.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .orchestrator import run_turn

router = APIRouter(prefix="/chat", tags=["agent"])

_THIS_DIR = Path(__file__).parent
_UI_FILE = _THIS_DIR / "chat_ui.html"


@router.get("/ui", response_class=HTMLResponse)
async def chat_ui() -> HTMLResponse:
    if not _UI_FILE.exists():
        return HTMLResponse("<h1>chat_ui.html missing</h1>", status_code=500)
    return HTMLResponse(_UI_FILE.read_text())


@router.post("")
async def chat(request: Request):
    """Run one orchestrator turn against the supplied message history.

    Request body shape:
      { "messages": [ {"role": "user", "content": "..."}, ... ] }

    Response: text/event-stream of JSON events.
    """
    body = await request.json()
    messages: list[dict[str, Any]] = body.get("messages", [])

    async def event_stream():
        try:
            async for event in run_turn(messages):
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": f"{type(e).__name__}: {e}"})}

    return EventSourceResponse(event_stream())
