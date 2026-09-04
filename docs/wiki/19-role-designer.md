# Role guide — Designer (Figma assembly and templates)

**Who this is for:** the designer who turns an approved sprint into finished creatives in Figma,
and who owns the templates ADAM builds from. This is a different job from running the tool.

You own two things: **assembling a sprint**, and **keeping the template library healthy** so
assembly keeps working.

---

## Part 1 — Assembling a sprint

### One-time setup

**Work inside the ADAM 2026 file, on your own page.**

1. In the ADAM 2026 file (the one holding the template pages), add a page — `Assembly`,
   `Sept sprints`, whatever you like.
2. Optional: put a `Generated Tests` **section** on that page containing one frame. The plugin
   clones that frame per run, so output stacks neatly on your page rather than landing in the
   section on the Template Library page.
3. Run the plugin from that page. **Nothing else needs to be on it.**

**Do not keep a separate working file with copied templates.** Those copies rot. The August test
file was missing Lifestyle Photo's 4:5 size and the Us vs Them container entirely, which produced a
run with one failure and twenty-five misses. The plugin cannot reach into another *file* — only
other *pages* of the same file — so a separate file always means a hand-copied set drifting out of
date.

### Running it

1. **Plugins → Development → Upwork Pipeline Assembly.**
2. **Choose CSV file** → the sprint's `asset_manifest.csv`.
3. **Assemble.**

The plugin finds everything it needs across the file. In every case **a copy on your current page
wins**, so you can always override a template locally by putting one on your page.

Where it looks for templates, in order: your page → that platform's template page (`-> Meta
Templates`, `-> Reddit Templates`, …) → the Template Library page → the whole file. The platform
step matters: several pages hold containers with identical names, so this is what stops a Meta run
pulling a LinkedIn frame.

### Reading the log when it finishes

The first line tells you the plugin version. The last lines tell you how it went.

| What you see | What it means |
|---|---|
| **"Assembly complete… no warnings"** | Clean run. |
| **"Assembly DEGRADED"** | At least one warning. It fires on *any* warning by design, after a case where thirteen real problems hid in the scrollback. Read the count before worrying. |
| **`failed`** | A board could not be built. Real problem. |
| **`misses`** | A slot or layer the plugin looked for and could not find. Usually a naming mismatch — real, worth fixing. |
| **`empty slots`** | Something was left unfilled. |
| **`name drift`** | A name matched only after normalising — a trailing slash, a stray space, a capitalisation change. **The run was unaffected**; it self-healed. Worth tidying so it does not accumulate. |
| **"THIS PLUGIN IS OUT OF DATE"** | Download the new one. See below. |

`failed` and `misses` deserve attention. `name drift` is a tidy-up list, not a failure.

### Keeping the plugin current

Get it from **`/plugin`** on the ADAM site: download, unzip, then **Plugins → Development → Import
plugin from manifest…** and pick `manifest.json`. Importing over an old copy is fine; delete the
previous entry if you end up with two.

Every assembly reports its version and checks it against the current one, so an out-of-date copy
will tell you in its own log. This exists because three different builds were once running at once
and nobody could tell.

---

## Part 2 — Owning the templates

ADAM matches templates **by name**. Names are the contract between Figma and the tool, which is why
naming discipline matters more here than in a normal design file.

### The naming convention

```
Adtype_<Style-Name>                          the container
  Template_<Style-Name>_<width>x<height>      the template frames inside it
  Template_<Style-Name>_<Variant>_<w>x<h>     when a style has variants (Dark/Light)
```

Sizes are meaning-bearing (`1440x1800`), as are variant words (`Dark`, `Light`). Those must be
exact. Cosmetic drift — a trailing slash, doubled spaces, different capitalisation — is now
tolerated and reported rather than silently breaking a style, but it should still be cleaned up.

### Adding a new template

1. Build the frames in Figma following the convention above, in all three sizes.
2. Name the text and image layers to match what the plugin fills.
3. Tell the engineer, so the style is added to the tool's registry and the order form.
4. Run a test sprint using only that style and check the log for misses.

### Checking your work without running a sprint

There is a lint that compares the live Figma file against what the plugin expects and reports
mismatches — missing sizes, containers that do not match, and nested image placeholders where a
photo would land underneath the template's default art. Ask the engineer to run it after a batch of
template edits; it takes seconds and costs nothing.

### The photo library

People photos come from the tagged Upwork brand library in Figma. **ADAM never generates images of
people** — this is a hard rule, not a preference. Photos are chosen by their tags, and the tool
avoids reusing a photo from the previous sprint. Variety is bounded by the library: more tagged
photos means more variety.

---

## Things that will bite you

**A photo lands under the default art.** The template has an image placeholder nested inside
another image placeholder. The plugin fills the outer one, so nothing looks broken — the ad just
shows the template's stock image. Nine templates had this in the August test file. The lint finds
them.

**A style silently borrows another's template.** If a container is misnamed, the plugin can fall
through to a name-matched template from a different style. This is why several styles share base
template names and are kept apart only by their container.

**Copies of templates in another file go stale.** Covered above, and it is the single most common
cause of a run that half-works.
