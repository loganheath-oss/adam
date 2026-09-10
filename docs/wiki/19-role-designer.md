# Role guide: Designer (Figma assembly and templates)

**Who this is for:** the designer who turns an approved sprint into finished creatives in Figma, and
who owns the templates ADAM builds from. Different job from running the tool.

You own two things. Assembling a sprint, and keeping the template library healthy so assembly keeps
working.

---

## How a manifest row becomes an ad

Worth reading first, because every failure below is a step in this chain.

1. A row comes in with a visual style and the copy fields for that ad.
2. The plugin normalizes the style name. It lowercases it and strips anything in parentheses, so
   "Pie Chart (data)" becomes "pie chart".
3. It finds the template by looking inside that style's Adtype container first, then widening out.
4. It clones the template.
5. Unless the style keeps its own artwork, it drops in the image, either a library photo or a
   generated one.
6. It fills the named text layers. Headline, subhead, CTA, bullets.
7. It runs any special fills the style needs, like the pie percentage arc.

Steps 3 and 6 are where almost everything goes wrong, and both of them come down to names.

---

## Part 1: Assembling a sprint

### One time setup

**Work inside the ADAM 2026 file, on your own page.**

1. In the ADAM 2026 file, the one holding the template pages, add a page. Call it `Assembly`,
   `Sept sprints`, whatever you want.
2. Put a `Generated Tests` **section** on that page with one frame inside it. The plugin clones that
   frame every run, so your output stacks up on your page instead of landing in the section over on
   the Template Library page.
3. Run the plugin from your page. Nothing else needs to be on it.

**Step 2 isn't really optional.** If your page doesn't have a `Generated Tests` section, the plugin
falls back to searching the whole document, finds the one on the Template Library page, and builds
there. So you'll be working on your own page and watching the output land somewhere else. That's the
fix if you've seen that happen.

**Don't keep a separate working file with copied templates in it.** Those copies rot. The August test
file was missing Lifestyle Photo's 4:5 size and the Us vs Them container entirely, and that run came
back with one failure and twenty five misses. The plugin can't reach into another *file*, only other
*pages* of the same file, so a separate file always means a hand copied set drifting out of date.

### Running it

1. **Plugins → Development → Upwork Pipeline Assembly.**
2. **Choose CSV file**, then the sprint's `asset_manifest.csv`.
3. **Assemble.**

Each ad comes out as a standalone frame at its native size, laid out in a grid near your viewport.
They don't get nested into a parent frame unless you capture a destination first.

The plugin finds what it needs across the whole file. A copy on your current page always wins, so you
can override a template locally just by putting one on your page.

Where it looks, in order:

1. **Your current page.** A local copy wins, so nothing regresses and you can override in place.
2. **That platform's own template page**, like `-> Meta Templates` or `-> Reddit Templates`, picked
   off the manifest's Platform column. This step is doing real work. Five pages carry containers with
   the same names, so a blind document wide search could pull a LinkedIn frame into a Meta run.
3. **The generic Template Library page.**
4. **The whole document**, last resort.

The log prints the search order at the start of a run and tells you when a template got found
somewhere other than your working page.

### Reading the log

First line tells you the plugin version. The last lines tell you how it went.

| What you see | What it means |
|---|---|
| **"Assembly complete… no warnings"** | Clean run. |
| **"Assembly DEGRADED"** | At least one warning. It fires on *any* warning on purpose, after a run where thirteen real problems hid in the scrollback. Check the count before you worry. |
| **`failed`** | A board couldn't be built. Real problem. |
| **`misses`** | A slot or layer it looked for and couldn't find. Usually a naming mismatch. Real, worth fixing. |
| **`empty slots`** | Something got left unfilled. |
| **`name drift`** | A name only matched after normalizing, like a trailing slash or a stray space or different capitalization. The run was fine, it self healed. Worth tidying so it doesn't pile up. |
| **"THIS PLUGIN IS OUT OF DATE"** | Grab the new one. See below. |

`failed` and `misses` are the ones to look at. Name drift is a tidy up list, not a failure.

### Keeping the plugin current

Get it from **`/plugin`** on the ADAM site. Download, unzip, then **Plugins → Development → Import
plugin from manifest…** and pick `manifest.json`. Importing over an old copy is fine. Delete the
previous entry if you end up with two.

**Do this before you report an assembly bug.** The plugin runs off files on each person's machine, so
copies drift. At one point three different builds were in use at once and one of them was missing a
fix from the month before, and the only way to find out was diffing files by hand.

Every assembly logs its version on the first line and reports it back, and the backend answers with
the version the repo ships. If they don't match, the log ends with a loud out of date line naming
both.

---

## Part 2: Owning the templates

ADAM matches templates by name. Names are the contract between Figma and the tool, which is why
naming matters more here than it would in a normal design file.

The convention got set in July 2026 by auditing both production files and ranking every naming
pattern by how recent it was. It's the pattern in the newest work and it's also the most common by
count. Older ones like `Adtype: Style` and `AdType_CamelCase` are legacy. The plugin still matches
them as a fallback, but don't use them for anything new.

### Container and frame names

```
Adtype_Style-Name                          the container
  Template_Style-Name_WxH                   the template frames inside it
  Template_Style-Name_Variant_WxH           when a style has variants
```

Real ones: `Adtype_Sticky-Note`, `Adtype_Talent-Profile`,
`Template_Photo-With-Text_Dark_1440x1440`, `Template_Lifestyle-Photo-Full-Bleed_1440x1440`.

- **Hyphenate words inside the style name.** `Sticky-Note`, not `StickyNote`.
- **Underscores separate the segments.** Prefix, style, variant, size.
- **Size is `WxH`, no spaces.** Like `1440x1800`.
- **Variants go between the style and the size.** `_Single`, `_Double`, `_Dark`.

Sizes and variant words carry meaning, so those have to be exact. Cosmetic drift like a trailing
slash or doubled spaces or different capitalization gets tolerated and reported now instead of
quietly breaking a style, but it's still worth cleaning up.

### Reddit doesn't follow that convention

Everything above is the Meta convention. The Reddit Templates page does its own thing and the plugin
was taught both back in September 2026. If you're working on Reddit:

- **Containers are `Reddit_Adtype_Style-Name`**, like `Reddit_Adtype_Venn-Diagram`. That `Reddit_`
  prefix means a search for containers starting with "Adtype" never finds them.
- **Size frames are named for their dimensions**, `1080x1350` and `1440x1080`, not `Template_*`. When
  a container has no `Template_` named children the plugin falls back to matching on the frame's
  actual size, which is what makes this work.
- **Two sizes per style.** Portrait `1080x1350` and landscape `1440x1080`.
- **Each container also has a `Rules` frame.** That's the spec card for the copy team. It's not a
  template and it doesn't get assembled.

A couple of things to keep clean over there.

**Never leave two `Rules` cards in one container.** `Reddit_Adtype_Split-Screen` has a stale unfilled
stub sitting next to the finished card right now. Whichever gets read first wins, and in September a
harvest read the stub and wrote off the whole ad type as blocked when it wasn't.

**Don't leave duplicate size frames.** Several Reddit containers have two frames with the same name
and the same size. The plugin takes the first one it finds, so if they're different, which one ships
is a coin flip.

### Text layer names

This is the part that decides whether copy actually lands. Text layers are `Copy_<Role>`:

| Layer name | What goes in it |
|---|---|
| `Copy_Headline` | The main headline |
| `Copy_Subhead` | Subhead or a supporting stat |
| `Copy_Body` | Body copy |
| `Copy_CTA` | The on image call to action |
| `Copy_Headline-Left` / `Copy_Headline-Right` | Paired headlines, like Us vs Them |
| `Copy_Testimonial` | The quote in a testimonial ad |
| `Copy_Author` | The attribution under a quote |

Name a text layer anything else and the plugin can't find it, so the ad ships with placeholder text
in that slot. This is the number one cause of "the ads came out with Lorem Ipsum in them," and it's a
Figma side fix, not a code fix.

### The image placeholder leaf rule

**Only the actual fill rectangle gets named `Image-Placeholder`. Its wrapper frame is named `Image`.**

Never name a frame `Image-Placeholder` when it's got a child with the same name. The plugin fills the
parent, the child keeps its baked in photo, and that stock photo ships on the ad. Nothing looks broken
in the log either, which is what makes this one nasty. Back in July every Notification 4:5 shipped the
template's stock photo this way.

The lint catches every one of these.

### Special fills

A few styles need more than swapping text, so their layers matter in particular ways:

- **Pie Chart.** Sets the center callout and drives the value arc on the ellipse off a percentage
  field. That arc is data, not decoration.
- **Us vs Them.** Fills two headlines plus three bullets on each side.
- **Sticky Note.** Fills two structured columns, each with a headline and two bullets.
- **Reminder and Tweet/Post Mockup.** These two share a base template.

### Known gaps

Tracked, cosmetic, not recognition failures. Listed so you don't go chasing them as bugs:

- **Pie Chart** quadrant labels all share one layer name. They need distinct names and four separate
  copy fields before all four quadrants can fill independently.
- **Photo with Text** doesn't fill its subhead on the Light Mode variant, because that variant is
  missing the layer.
- A few other styles need Figma side renames before they hit full field coverage.

---

## Adding a new template

1. Build the frames following the convention above, in all three sizes.
2. Name the text layers with the `Copy_<Role>` names, and the image slot per the leaf rule.
3. Tell the engineer so the style gets added to the registry and the order form.
4. Run a test sprint with just that style and check the log for misses.

**A style can't be ordered before its template exists.** The order form and the template library are
kept in step on purpose, so adding one is a two person job between you and the engineer.

---

## Checking your work without running a sprint

There's a lint that compares the live Figma file against what the plugin expects. It reports per style
template resolution, missing sizes, containers that don't match, and nested image placeholders. Ask
the engineer to run it after any batch of template work lands. Takes seconds, costs nothing.

---

## Things that'll bite you

**A photo lands under the default art.** The nested placeholder thing above. The ad looks fine at a
glance because it's showing the template's stock image instead of an empty slot. Nine templates had
this in the August test file. The lint finds them.

**A style quietly borrows another one's template.** If a container is misnamed the plugin can fall
through to a name matched template from a different style. That's why several styles share base
template names and only stay apart because of their container, and it's why the platform page step in
the search order exists.

**A style assembles but fills nothing.** The frame it found is probably an empty skeleton instead of
the one with the text layers in it, or the container name is off. Check which frame actually has the
text layers.

**One size is missing its copy layers.** Check both sizes of a style, not just one. Right now the
Reddit Graphic-With-Text landscape has only `Copy_Subhead` when it needs two headlines, and the
Text-with-Icons landscape is missing its three list layers. Both portrait versions are correct, so you
won't see it unless you look at both.

**Copies of templates in another file go stale.** Covered up top, and it's the single most common
reason a run half works.

**The plugin doesn't pick up changes on its own.** No hot reload. Re run it in Figma desktop, and if
it got relinked, re import the manifest.

---

## Who to ask

- **Copy rules, character caps, approved claims.** Adrie.
- **A sprint that errored before it got to you.** The copywriter who ran it.
- **Adding a style to the order form, or running the lint.** The engineer.
