# FAQ

Seed questions for new owners — also the kind of thing the in-app chat should answer once it's wiki-aware
(see [The web app & chat](06-the-web-app-and-chat.md)).

**Q: What is ADAM in one line?**
A: An AI pipeline that turns a brief into Upwork ad copy + assembled Figma creatives across sizes/styles.

**Q: Where does the unique copy come from?**
A: The **copy-gen stage** (`run_pipeline.py` → Claude), not the Figma plugin. The plugin only assembles what
the manifest already contains.

**Q: Why do my assembled ads show placeholder text?**
A: Copy-gen didn't run, or you loaded a hand-made manifest. The two classic causes — a **dead model ID**
(404, now fixed → `claude-sonnet-5`) and a **$0 local key** (HTTP 400) — are why; on the live tool both are
resolved. See [Troubleshooting](11-troubleshooting.md).

**Q: Where is it deployed?**
A: **Railway**, auto-deploying from GitHub `loganheath-oss/adam`. (Older docs say Fly/Replit — that's stale.)

**Q: The run summary says only part of my assets were "delivered" — did the run fail?**
A: Probably not. `delivered` counts only **server-rendered files**. Library-photo styles are finished
**inside Figma** by the plugin and show as `ready_for_figma` (then `assembled_in_figma` once the plugin
reports back); self-contained styles show as `skipped` by design. The only bucket that means "something
is actually missing" is `pending_assembly`. (Before 2026-09-01 everything non-delivered was labeled
`pending_assembly`, which made healthy runs look half-failed — that's fixed.)

**Q: Gate 5 says the manifest is empty and to check back later?**
A: That can no longer happen: a preliminary manifest is written **before** Gate 5. If you ever see an
empty manifest at Gate 5, it's a defect — file it with `log_issue`, don't wait (there is no background
process to wait for).

**Q: Can I change the copy ADAM wrote?**
A: Yes — **at Gate 3**, in chat: tell it which concepts to keep or drop, and ask for wording changes
("shorten that headline", "replace the CTA") — it applies them and they flow into image prompts. After
Gate 3 approval, copy is frozen for the run.

**Q: Are learnings I add in chat actually permanent?**
A: Yes. `learnings.md` lives on the persistent `/data` volume and survives every deploy (since 2026-07-29).
The chat reads it every session.

**Q: The on-ad copy echoes itself — same sentence with a different word swapped in. Why?**
A: Six concepts per style, generated in one call, tend to rhyme. As of 2026-09-03 two things
push back: a craft-bar rule telling the model that two headlines sharing an opening AND closing
pair are one idea in three hats (vary the grammar, not just the noun), and a deterministic pass
that walks every concept in a style best-first and labels any that reuses an earlier one's idea
or frame with **⚠ ECHO** in review notes. If an echoing concept was auto-selected, a distinct
alternate is swapped in when one exists. Measured on 12 past sprints, ~7% of concepts would carry
the label — concentrated in small runs (17-25% at 1-3 styles, ~4% at 12), which is also where the
problem was worst.

**Q: Why does ADAM keep picking the same library photo?**
A: It can't repeat back-to-back anymore (2026-09-02): a photo used in the previous sprint is **excluded
outright** from the next one (unless it's the only photo matching the style's tags), photos from the
last 6 sprints are strongly down-weighted, and picks are sampled rather than always taking the single
top tag-match. Variety is still bounded by the library — more tagged photos in Figma = more variety.
(Engineering knobs: `ADAM_PHOTO_NO_REPEAT_SPRINTS`, `ADAM_PHOTO_TEMPERATURE`,
`ADAM_PHOTO_RECENT_SPRINTS`, `ADAM_PHOTO_RECENT_WEIGHT`.)

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
A: Essentially nothing new — the dead-model-ID bug is fixed and the Railway key clears billing. It just needs
nothing — it was verified end-to-end on the live tool (copy 2026-06-29; full gate flow 2026-07-27). (For local dev, bring your own funded key.)
