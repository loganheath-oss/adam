# FAQ

Seed questions for new owners — also the kind of thing the in-app chat should answer once it's wiki-aware
(see [The web app & chat](06-the-web-app-and-chat.md)).

**Q: What is ADAM in one line?**
A: An AI pipeline that turns a brief into Upwork ad copy + assembled Figma creatives across sizes/styles.

**Q: Where does the unique copy come from?**
A: The **copy-gen stage** (`run_pipeline.py` → Claude), not the Figma plugin. The plugin only assembles what
the manifest already contains.

**Q: Why do my assembled ads show placeholder text?**
A: Copy-gen didn't run — almost always because the **Anthropic key has $0 credits** (HTTP 400 "credit balance
too low"), or you loaded a hand-made manifest. See [Troubleshooting](11-troubleshooting.md).

**Q: Where is it deployed?**
A: **Railway**, auto-deploying from GitHub `loganheath-oss/adam`. (Older docs say Fly/Replit — that's stale.)

**Q: How do I run a batch?**
A: Web app order form → approve gates, **or** CLI `run_pipeline.py --json/--csv/--test` then `--resume --gate N`.
Then assemble in Figma. Full steps: [Using ADAM](07-using-adam.md).

**Q: How do I add a new visual style / template?**
A: Build the template in Figma, then add the style to the `STYLE_*` lookup tables in `plugin/code.js`
(prefix, container, headline/bullet/subhead layers, skip-image/cta flags). For multi-field styles also add
the copy-gen fields in `run_pipeline.py`. See [Figma plugin](05-figma-plugin.md).

**Q: Can the tool generate photos of people?**
A: **No** — hard rule. People photos come only from the rights-cleared Upwork Figma library. Gemini does
illustrations/abstracts/backgrounds. See [Constraints](10-constraints.md).

**Q: How do I change the brand voice or approved claims?**
A: Edit `refs/*.txt`, run `pipeline/build_refs.py` to recompile `configs/refs_context.json`. Never hand-edit
the compiled file.

**Q: What's the difference between `run_pipeline.py` and the `00_…06_` files?**
A: `run_pipeline.py` is the live source of truth. The numbered modules are an older AWS-bound scaffold that
lags it.

**Q: How do I teach ADAM a lesson that should persist across sprints?**
A: Add it to `learnings.md` (or the `/learnings` page). The chat reads it every session.

**Q: What's blocking "make it live with unique output" right now?**
A: A **funded Anthropic API key**. Everything else is wired.

> TODO: grow this from real questions the team asks during handoff sessions.
