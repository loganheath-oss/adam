# Role guide: Designer (Figma assembly and templates)

**Who this is for:** the designer who turns an approved sprint into finished creatives in Figma,
and who owns the templates ADAM builds from. This is a different job from running the tool.

You own two things: **assembling a sprint**, and **keeping the template library healthy** so
assembly keeps working.

---

## How one manifest row becomes an ad

Worth understanding before anything else, because every failure mode below is a step in this chain.

1. A manifest row arrives carrying a **visual style** and the copy fields for that ad.
2. The plugin normalizes the style name (lowercases it, strips anything in parentheses, so
   "Pie Chart (data)" becomes "pie chart").
3. It finds the matching template by looking for the style's **Adtype container** first, then
   widening the search.
4. It clones that template.
5. Unless the style is one that keeps its own artwork, it applies the image, either a library photo
   or a generated one.
6. It fills the **named text layers**: headline, subhead, CTA, bullets.
7. It runs any special fills the style needs, such as the pie percentage arc.

Steps 3 and 6 are where nearly everything goes wrong, and both are about **names**.

---

## Part 1: Assembling a sprint

### One-time setup

**Work inside the ADAM 2026 file, on your own page.**

1. In the ADAM 2026 file (the one holding the template pages), add a page called `Assembly`,
   `Sept sprints`, or whatever you like.
2. Optional: put a `Generated Tests` **section** on that page containing one frame. The plugin
   clones that frame per run, so output stacks neatly on your page rather than landing in the
   section on the Template Library page.
3. Run the plugin from that page. **Nothing else needs to be on it.**

**Do not keep a separate working file with copied templates.** Those copies rot. The August test
file was missing Lifestyle Photo's 4:5 size and the Us vs Them container entirely, which produced a
run with one failure and twenty-five misses. The plugin cannot reach into another *file*, only
other *pages* of the same file, so a separate file always means a hand-copied set drifting out of
date.

### Running it

1. **Plugins → Development → Upwork Pipeline Assembly.**
2. **Choose CSV file** → the sprint's `asset_manifest.csv`.
3. **Assemble.**

Each assembled ad is a **standalone frame at its native size**, laid out in a grid near your
viewport. They are not nested into a parent frame unless you capture a destination first.

The plugin finds everything it needs across the file. In every case **a copy on your current page
wins**, so you can always override a template locally by putting one on your page.

Where it looks for templates, in order:

1. **Your current page.** A local copy still wins, so nothing regresses and you can override a
   template in place.
2. **That platform's own template page** (`-> Meta Templates`, `-> Reddit Templates`, and so on),
   chosen from the manifest's Platform column. **This step is required, not a nicety.** Five pages
   carry containers with identical names, so a blind document-wide search could assemble a LinkedIn
   frame into a Meta run.
3. **The generic Template Library page.**
4. **The whole document**, as a last resort.

The log prints the search order at the start of a run, and says when a template was found somewhere
other than your working page.

### Reading the log when it finishes

The first line tells you the plugin version. The last lines tell you how it went.

| What you see | What it means |
|---|---|
| **"Assembly complete… no warnings"** | Clean run. |
| **"Assembly DEGRADED"** | At least one warning. It fires on *any* warning by design, after a case where thirteen real problems hid in the scrollback. Read the count before worrying. |
| **`failed`** | A board could not be built. Real problem. |
| **`misses`** | A slot or layer the plugin looked for and could not find. Usually a naming mismatch, real, worth fixing. |
| **`empty slots`** | Something was left unfilled. |
| **`name drift`** | A name matched only after normalizing: a trailing slash, a stray space, a capitalization change. The run was unaffected; it self-healed. Worth tidying so it does not accumulate. |
| **"THIS PLUGIN IS OUT OF DATE"** | Download the new one. See below. |

`failed` and `misses` deserve attention. `name drift` is a tidy-up list, not a failure.

### Keeping the plugin current

Get it from **`/plugin`** on the ADAM site: download, unzip, then **Plugins → Development → Import
plugin from manifest…** and pick `manifest.json`. Importing over an old copy is fine; delete the
previous entry if you end up with two.

**Do this before reporting an assembly bug.** The plugin runs from files on each person's machine,
so copies drift. On one occasion three different builds were in use at once, one of them missing a
fix from the month before, and the only way to find out was diffing files by hand.

Every assembly logs its version on the first line and reports it to the backend, which answers with
the version the repo ships. If they differ, the log ends with a loud out-of-date line naming both.

---

## Part 2: Owning the templates

ADAM matches templates **by name**. Names are the contract between Figma and the tool, which is why
naming discipline matters more here than in a normal design file.

This convention was set in July 2026 by auditing both production files and ranking every naming
pattern by how recent it was. It is the pattern in the newest work and also the most common by count.
Older patterns such as `Adtype: Style` and `AdType_CamelCase` are **legacy**. The plugin still
matches them as a fallback, but never use them for new work.

### Container and frame names

```
Adtype_Style-Name                          the container (a section)
  Template_Style-Name_WxH                   the template frames inside it
  Template_Style-Name_Variant_WxH           when a style has variants
```

Real examples: `Adtype_Sticky-Note`, `Adtype_Talent-Profile`, `Template_Photo-With-Text_Dark_1440x1440`,
`Template_Lifestyle-Photo-Full-Bleed_1440x1440`.

Rules of thumb:

- **Hyphenate words inside the style name.** `Sticky-Note`, not `StickyNote`.
- **Underscore separates segments**, meaning prefix, style, variant, size.
- **Size is `WxH` with no spaces**, for example `1440x1800`.
- **Layout or theme variants sit between the style and the size**, such as `_Single`, `_Double`, `_Dark`.

Sizes and variant words are meaning-bearing and must be exact. Cosmetic drift, such as a trailing
slash, doubled spaces, or different capitalization, is now tolerated and reported rather than
silently breaking a style, but it should still be cleaned up.

### Reddit templates use a different convention

Everything above describes the Meta convention. **The Reddit Templates page does not follow it**, and
the plugin was taught both (September 2026). If you are working on Reddit, this is the shape:

- **Containers are named `Reddit_Adtype_Style-Name`**, for example `Reddit_Adtype_Venn-Diagram`. Note
  the `Reddit_` prefix, which means a search for containers starting with `Adtype` never finds them.
- **Size frames are named for their dimensions**, `1080x1350` and `1440x1080`, rather than
  `Template_Style_WxH`. The plugin falls back to matching on the frame's actual size when a container
  holds no `Template_`-named children, which is what this convention relies on.
- **Two sizes per style**, portrait `1080x1350` and landscape `1440x1080`.
- **Each container also holds a `Rules` frame.** That is the spec card, meaning documentation for the
  copy team. It is not a template and is not assembled.

Two things to keep clean here:

**Never leave two `Rules` cards in one container.** `Reddit_Adtype_Split-Screen` currently holds a
stale unfilled stub alongside the completed card. Whichever is read first wins, and in September 2026
a harvest read the stub and recorded the whole ad type as blocked when it was not.

**Do not leave duplicate size frames.** Several Reddit containers hold two frames with the same name
and the same size. The plugin takes the first match, so if the two differ, which one ships is
arbitrary.

### Text layer names

**This is the part that decides whether copy lands.** Text layers follow `Copy_<Role>`:

| Layer name | Holds |
|---|---|
| `Copy_Headline` | The main headline |
| `Copy_Subhead` | Subhead or supporting stat |
| `Copy_Body` | Body copy |
| `Copy_CTA` | The on-image call to action |
| `Copy_Headline-Left` / `Copy_Headline-Right` | Paired headlines, as in Us vs Them |
| `Copy_Testimonial` | The quote in a testimonial ad |
| `Copy_Author` | The attribution under a quote |

If a text layer is named anything else, the plugin cannot find it and the ad ships with placeholder
text in that slot. This is the single most common cause of "the ads came out with Lorem Ipsum in
them", and it is a Figma-side fix, not a code fix.

### The image placeholder leaf rule

**Only the actual fill rectangle may be named `Image-Placeholder`. Its wrapper frame is named
`Image`.**

Never name a frame `Image-Placeholder` when it has a child of the same name. The plugin fills the
parent, the child keeps its baked-in photo, and that stock photo ships on the finished ad. Nothing
looks broken in the log, which is what makes this one dangerous. In July 2026 every Notification 4:5
shipped the template's stock photo this way.

The lint flags every violation of this rule.

### Special fills to be aware of

A few styles need more than text substitution, so their layers matter in specific ways:

- **Pie Chart.** The plugin sets the center callout text and drives the value arc on the ellipse from
  a percentage field. The arc is data, not decoration.
- **Us vs Them.** Fills two headlines plus three bullets on each side.
- **Sticky Note.** Fills two structured columns, each with a headline and two bullets.
- **Reminder and Tweet/Post Mockup.** These share a base template.

### Known field-coverage gaps

These are tracked, cosmetic, and not recognition failures. Worth knowing so you do not chase them as
bugs:

- **Pie Chart** quadrant labels currently share one layer name. They need distinct names and four
  separate copy fields before all four quadrants can be filled independently.
- **Photo with Text** does not fill its subhead in the Light Mode variant, because that variant is
  missing the layer.
- A few other styles need Figma-side layer renames before they reach full field coverage.

---

## Adding a new template

1. Build the frames in Figma following the convention above, in all three sizes.
2. Name the text layers using the `Copy_<Role>` names above, and the image slot following the leaf
   rule.
3. Tell the engineer, so the style is added to the tool's registry and the order form.
4. Run a test sprint using only that style and check the log for misses.

**A style cannot be ordered before its template exists.** The order form and the template library are
kept in step deliberately, so new styles are a two-person job, not a same-day request.

---

## Checking your work without running a sprint

There is a lint that compares the live Figma file against what the plugin expects. It reports
per-style template resolution, missing sizes, containers that do not match, and nested image
placeholders. Ask the engineer to run it after any batch of template work lands. It takes seconds and
costs nothing.

---

## Things that will bite you

**A photo lands under the default art.** The nested placeholder problem described above. The ad looks
fine at a glance because it shows the template's stock image rather than an empty slot. Nine
templates had this in the August test file. The lint finds them.

**A style silently borrows another's template.** If a container is misnamed, the plugin can fall
through to a name-matched template from a different style. This is why several styles share base
template names and are kept apart only by their container, and why the platform-page step in the
search order exists.

**A style assembles but fills nothing.** The template frame it found is probably an empty skeleton
rather than the one carrying the text layers, or the container name is wrong. Confirm which frame
actually has the text layers in it.

**Copies of templates in another file go stale.** Covered above, and it is the single most common
cause of a run that half-works.

**The plugin does not pick up changes on its own.** There is no hot reload. Re-run it in Figma
desktop, and if it was relinked, re-import the manifest.

---

## Who to ask about what

- **Copy rules, character caps, approved claims:** Adrie.
- **A sprint that errored before it reached you:** the copywriter who ran it.
- **Adding a style to the order form, or the lint:** the engineer.
