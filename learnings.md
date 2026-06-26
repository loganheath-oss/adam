# ADAM Learnings

Institutional memory shared across every sprint. Edit this file directly to add, refine, or remove guidance — Claude reads it at the start of every chat session, and you can also edit it from the `/learnings` page in the browser.

## Project wiki (read this to answer "how is ADAM built / how do I…" questions)

The full ADAM knowledge base lives in `docs/wiki/` (start at `docs/wiki/README.md`). When asked anything
about how the tool works, where things live, how to run it, or how to fix it, ground answers in these pages:

- **What is ADAM** → `docs/wiki/01-what-is-adam.md`
- **Architecture** (5 components, data flow) → `docs/wiki/02-architecture.md`
- **Repo map** (where every file lives) → `docs/wiki/03-repo-map.md`
- **The pipeline** (stages 00–06, gates) → `docs/wiki/04-the-pipeline.md`
- **Figma plugin** (21 styles, auto-discovery) → `docs/wiki/05-figma-plugin.md`
- **Web app & chat** → `docs/wiki/06-the-web-app-and-chat.md`
- **Using ADAM** (operator runbook) → `docs/wiki/07-using-adam.md`
- **Deployment & ops** (Railway, secrets) → `docs/wiki/08-deployment-and-ops.md`
- **Configuration & refs** → `docs/wiki/09-configuration-and-refs.md`
- **Constraints** (hard rules) → `docs/wiki/10-constraints.md`
- **Troubleshooting** → `docs/wiki/11-troubleshooting.md`
- **FAQ** · **Glossary** · **Handoff** · **Decisions log** → `docs/wiki/12`–`15`

Key truths that override older docs: hosting is **Railway** (not Fly/Replit); copy uniqueness comes from the
**copy-gen stage**, not the plugin; the current blocker for live output is a **funded Anthropic key**.

## Guidance

