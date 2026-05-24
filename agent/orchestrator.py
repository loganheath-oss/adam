"""Claude API orchestrator loop.

Takes a user message + conversation history, drives a tool-use loop with
Claude (calling functions in `tools.py`), and yields streaming events
that the chat UI / SSE route can forward to the browser.

Designed to plug into a FastAPI route like:

    @app.post("/chat")
    async def chat(req: ChatRequest):
        return EventSourceResponse(
            run_turn(req.messages, req.sprint_id_hint)
        )

Uses prompt caching on the system prompt + tool definitions so the
per-turn cost stays low even with many gate iterations on the same
sprint.
"""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from .system_prompt import SYSTEM_PROMPT
from .tools import CLAUDE_TOOLS, call_tool

DEFAULT_MODEL = os.environ.get("ADAM_AGENT_MODEL", "claude-sonnet-4-6")
MAX_TURNS = 16  # safety cap on tool-use back-and-forth per user message


def _client() -> AsyncAnthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it via Replit Secrets."
        )
    return AsyncAnthropic()


async def run_turn(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    sprint_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run a single user turn, yielding events as they happen.

    When `sprint_id` is set, the orchestrator is told it's bound to that sprint
    and should not ask for one — used by the per-sprint chat UI.

    Event shapes (consumer can forward to SSE):
      {"type": "text_delta", "text": "..."}
      {"type": "tool_use", "name": "...", "input": {...}, "id": "..."}
      {"type": "tool_result", "tool_use_id": "...", "content": <json>}
      {"type": "turn_complete"}
      {"type": "error", "error": "..."}
    """
    client = _client()
    convo = list(messages)
    system_prompt = SYSTEM_PROMPT
    if sprint_id:
        system_prompt = (
            SYSTEM_PROMPT
            + f"\n\n# Sprint binding\n\nThis session is bound to sprint `{sprint_id}`. "
            "Do not ask the user which sprint to work on. Default every tool call "
            f"to `sprint_id=\"{sprint_id}\"` unless they explicitly reference a different one."
        )

    for _ in range(MAX_TURNS):
        # Prompt-cached system + tools — the first turn pays full cost, every
        # subsequent turn on the same sprint hits the 5-minute cache.
        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[
                {**tool, "cache_control": {"type": "ephemeral"}} if i == len(CLAUDE_TOOLS) - 1 else tool
                for i, tool in enumerate(CLAUDE_TOOLS)
            ],
            messages=convo,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield {"type": "text_delta", "text": event.delta.text}

            final_message = await stream.get_final_message()

        # Append the assistant's full response to history.
        convo.append({"role": "assistant", "content": final_message.content})

        # If Claude wants to call tools, execute them and feed results back.
        tool_uses = [b for b in final_message.content if b.type == "tool_use"]
        if not tool_uses:
            yield {"type": "turn_complete"}
            return

        tool_results = []
        for tu in tool_uses:
            yield {
                "type": "tool_use",
                "name": tu.name,
                "input": tu.input,
                "id": tu.id,
            }
            try:
                result = call_tool(tu.name, tu.input)
                result_str = json.dumps(result, default=str)
                is_error = False
            except Exception as e:
                result_str = f"{type(e).__name__}: {e}"
                is_error = True
            yield {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_str,
                "is_error": is_error,
            }
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_str,
                "is_error": is_error,
            })

        # Feed tool results back as the next user message.
        convo.append({"role": "user", "content": tool_results})

    yield {"type": "error", "error": f"hit MAX_TURNS={MAX_TURNS} without completing"}
