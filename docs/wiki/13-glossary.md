# Glossary

| Term | Meaning |
|---|---|
| **ADAM** | The tool/project: the AI creative production pipeline for Upwork Paid Acquisition |
| **Sprint** | One pipeline run. State lives in `runs/{sprint_id}/` |
| **Gate** | A human approval checkpoint between pipeline stages (1–6) |
| **Manifest** | `asset_manifest.csv` — the per-asset handoff from pipeline to Figma plugin |
| **Visual style** | The ad type/layout (e.g. Pie Chart, Us vs Them, Lifestyle Photo) — 24 on the order form (21 have plugin template mappings) |
| **Template** | A `Template_*` Figma frame the plugin clones for a given style |
| **Adtype container** | The `Adtype:` frame grouping a style's templates; used to disambiguate shared skeletons |
| **Concept** | One generated copy option. Copy-gen makes 6/style, keeps the top picks (min 2 per style, quantity-driven, diversity-filtered) |
| **Multi-field style** | A style needing structured copy beyond headline/body/cta (Us vs Them, Sticky Note, Pie Chart) |
| **Skip-image style** | A style that keeps template imagery / has none — no Gemini or library lookup |
| **Library photo** | A rights-cleared, tagged people photo pulled from the Upwork Figma brand library |
| **Rights / `rights_YYYY_MM`** | Usage-rights marker on library photos, validated before use |
| **KOTH** | "King of the Hill" — the ad-performance ranking that prioritizes which templates/styles to build |
| **Refs / refs_context** | Brand/legal/voice source docs (`refs/`) compiled into `configs/refs_context.json` |
| **Learnings** | `learnings.md` — institutional memory the chat reads every session |
| **Gate orchestration** | The chat driving a sprint through gates via the `approve_gate` tool |
| **MCP server** | `mcp_server/server.py` — exposes sprint data as MCP tools (live — mounted in the web app at /mcp; only the standalone Fly host is retired) |
| **The plugin** | `plugin/` "Upwork Pipeline Assembly" — runs in Figma desktop |
