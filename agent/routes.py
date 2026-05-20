"""
agent/routes.py
===============
FastAPI routes for the /agent chat UI and SSE streaming endpoint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from agent.orchestrator import run_agent_turn

router = APIRouter(prefix="/agent", tags=["agent"])

_CHAT_UI_PATH = Path(__file__).parent / "chat_ui.html"


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def agent_ui():
    if not _CHAT_UI_PATH.exists():
        return HTMLResponse("<h1>Agent UI not found</h1>", status_code=500)
    return HTMLResponse(_CHAT_UI_PATH.read_text())


@router.post("/chat")
async def agent_chat(request: Request):
    """
    Accept {messages: [...]} and stream back SSE events.

    Each event is JSON:
      {"type": "text", "text": "..."}
      {"type": "tool_call", "name": "...", "input": {...}}
      {"type": "tool_result", "name": "...", "result": {...}}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    body = await request.json()
    messages = body.get("messages", [])

    if not messages:
        return StreamingResponse(
            iter([f'data: {{"type": "error", "message": "No messages provided"}}\n\ndata: {{"type": "done"}}\n\n']),
            media_type="text/event-stream",
        )

    if not api_key:
        async def _no_key():
            yield f'data: {json.dumps({"type": "text", "text": "⚠️ ANTHROPIC_API_KEY is not set. Set it as a Replit secret to enable the AI assistant."})}\n\n'
            yield 'data: {"type": "done"}\n\n'
        return StreamingResponse(_no_key(), media_type="text/event-stream")

    async def _stream():
        try:
            async for chunk in run_agent_turn(messages, api_key):
                yield chunk
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
