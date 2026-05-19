"""End-to-end smoke test: hit live MCP endpoint, list sprints, approve a gate.

Usage: python mcp_server/test_approve_gate.py [sprint_id] [gate]
       Defaults to listing sprints only (no mutation).
"""
import asyncio
import json
import os
import sys

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

URL = os.environ.get(
    "ADAM_MCP_URL",
    "https://adam-pipeline-cm.fly.dev/mcp?auth=11cToL-yxmRumMilF7FRdcq1uLBStA0nuSpR8W-_fH8",
)


async def main():
    sprint_id = sys.argv[1] if len(sys.argv) > 1 else None
    gate = int(sys.argv[2]) if len(sys.argv) > 2 else None

    async with streamablehttp_client(URL) as (read, write, _close):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Connected. {len(tools.tools)} tools available:")
            for t in tools.tools:
                print(f"  - {t.name}")
            print()

            sprints_result = await session.call_tool("list_sprints", {"limit": 5})
            print("Raw response from list_sprints (debug):")
            for c in sprints_result.content:
                print(repr(c)[:300])
            print()
            # Parse: structuredContent or text JSON.
            sprints = []
            if sprints_result.structuredContent:
                sprints = sprints_result.structuredContent.get("result", [])
            else:
                payload = json.loads(sprints_result.content[0].text)
                sprints = payload.get("result", payload) if isinstance(payload, dict) else payload
            print("Recent sprints:")
            for s in sprints[:5]:
                print(f"  {s['sprint_id']:30s} {s['state']}")
            print()

            if sprint_id and gate is not None:
                print(f"Calling approve_gate(sprint_id={sprint_id}, gate={gate})...")
                result = await session.call_tool(
                    "approve_gate", {"sprint_id": sprint_id, "gate": gate, "timeout_seconds": 120}
                )
                response = result.structuredContent or {}
                if not response and result.content:
                    # Fallback: each content piece may be a separate JSON chunk.
                    pieces = []
                    for c in result.content:
                        try:
                            pieces.append(json.loads(c.text))
                        except Exception:
                            pieces.append({"raw": c.text})
                    response = {"content_pieces": pieces}
                print("=== full response ===")
                print(json.dumps(response, indent=2, default=str)[:6000])
                print("=== stderr_tail ===")
                print(response.get("stderr_tail", "(none)"))
                print("=== stdout_tail ===")
                print(response.get("stdout_tail", "(none)"))
            else:
                print("(skip approve_gate — pass sprint_id and gate as args to actually run it)")


if __name__ == "__main__":
    asyncio.run(main())
