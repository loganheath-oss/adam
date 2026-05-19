"""ADAM gate orchestrator (Phase 3).

Replaces the claude.ai + MCP server flow with a local Anthropic API
integration so the entire pipeline drive loop lives inside the Replit
app. Tools mirror the MCP server's 7 functions but read/write the local
filesystem directly.
"""
