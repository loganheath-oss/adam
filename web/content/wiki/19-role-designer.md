# Role guide: Designer (Figma assembly and templates)

**Who this is for:** the designer who turns an approved sprint into finished creatives in Figma,
and who owns the templates ADAM builds from. This is a different job from running the tool.

You own two things. Assembling a sprint, and keeping the template library healthy so assembly keeps
working.

---

## A few terms used throughout

Defined once here so the rest of the page can be direct.

- **The plugin.** "Upwork Pipeline Assembly", run from Figma's Plugins menu. It reads a CSV and
  builds the ads.
- **The manifest.** The `asset_manifest.csv` a sprint produces. One row per ad, carrying the copy
  and which photo to use.
- **Board master.** The frame the plugin clones once per concept to build a board. One per platform,
  for example `Meta - Static Grouped` and `Reddit - Static Grouped`.
- **The checker.** A script an engineer runs that compares the live Figma file against what the
  plugin expects, and lists anything that does not match: missing sizes, containers whose names do
  not line up, photo slots nested inside each other. It changes nothing, it only reports. Asking for
  it to be run takes seconds and costs nothing.
- **Populates.** What the plugin does to a text layer or a photo slot: it writes the copy or the
  image into it.

---

## How a manifest row becomes an ad

Worth reading first, because every failure below is a step in this chain.

1. A row comes in with a visual style and the copy for that ad.
2. The plugin standardizes the style name, lowercasing it and ignoring anything in parentheses, so
   "Pie Chart (data)" and "pie chart" are treated as the same style.
3. It finds the template by looking inside that style's Adtype container first, then widening out.
4. It clones the template.
5. Unless the style keeps its own artwork, it populates the photo slot, either with a library photo
   or a generated one.
6. It populates the named text layers. Headline, subhead, CTA, bullets.
7. It runs any special handling the style needs, like the pie chart's percentage arc.

Steps 3 and 6 are where almost everything goes wrong, and both come down to layer names.

---

## Part 1: Assembling a sprint

### Setting up

**Work inside the ADAM 2026 file, on your own page.**

1. In the ADAM 2026 file, the one holding the template pages, add a page. Call it `Assembly`,
   `Sept sprints`, whatever you want.
2. Run the plugin from your page. Nothing else needs to be on it.

That's the whole setup as of plugin 2026.09.17. If your page has no `Generated Tests` section, the
plugin creates one for you there and says so in its log.

It used to search the whole document instead, find the section on the Template Library page, and
build there, which is why output kept appearing on a page you were not working on. If you already
have a `Generated Tests` section on your page, yours is still used.

### Downloading and keeping the plugin current

1. Go to the `/plugin` page on the ADAM site and download the file.
2. Unzip it. **Put the unzipped folder somewhere permanent**, not in Downloads, since the plugin
   loads from that folder every time you run it. Documents works well if you clear Downloads
   regularly.
3. Back in Figma, open the **Plugins** menu, either from the right-click menu or the top bar.
4. Choose **Development**, then **Import plugin from manifest**, and select the `manifest.json` file
   inside the folder you just unzipped.

If you end up with two entries in the list, delete the older one so you cannot run it by mistake.

**Update before reporting a bug.** The plugin runs from a folder on each person's machine, so
different people can be running different versions without knowing. At one point three different
versions were in use at once and one was missing a fix from the month before.

Every run prints its version on the first line of the log and checks it against the current one. If
yours is out of date, the log ends with a loud line telling you so.

### Running it

1. **Plugins → Development → Upwork Pipeline Assembly.**
2. **Choose CSV file**, then pick the sprint's `asset_manifest.csv`.
3. **Click Assemble.**

### Two output shapes, and what decides which you get

The log tells you which one you got, and they look nothing alike.

**Grouped boards.** The normal case. The plugin finds your platform's board master, clones it once
per concept, and puts the run inside `Generated Tests` as a single `Sprint · <label>` container.
Each board holds the copy panel, the labels at the top, and every size of that concept together.

**Standalone ads.** The fallback. Each ad comes out as its own frame at its native size, arranged in
a grid near where you are looking, not grouped into anything.

You get the second one when the board master for your platform cannot be found, and the log says so
in as many words. So if you expected grouped boards and got a loose grid, that is the plugin telling
you it could not find your board master, not a layout preference.

### Where the plugin looks for templates

In this order, taking the first thing it finds:

1. **Your current page.** A local copy of a template, on the page you are working from, always
   wins. So you can override any template by dropping a copy of it onto your page.
2. **That platform's own template page**, chosen from the manifest's Platform column.
3. **The Template Library page.**
4. **The whole document**, as a last resort.

Step 2 is doing real work. Five pages hold containers with the same names, so without it a Meta run
could pull a LinkedIn frame.

### Reading the log

The first line is the plugin version. The last lines tell you how the run went.

| What you see | What it means |
|---|---|
| **"Assembly complete… no warnings"** | Clean run. |
| **"Assembly DEGRADED"** | At least one warning. It says this for *any* warning on purpose, after a run where thirteen real problems scrolled past unnoticed. Check the count before worrying. |
| **`failed`** | A board could not be built. Real problem. |
| **`misses`** | A layer or slot the plugin looked for and could not find, almost always a layer name that does not match. Real, worth fixing. |
| **`empty slots`** | Something was left unpopulated. |
| **`name drift`** | A layer or frame name in Figma matched only after the plugin tidied it up, for example a trailing slash, a double space, or different capitalization. This is about names in the layers panel, not anything on the ad itself. **The run was fine.** It is a cleanup list, not a failure. |
| **"THIS PLUGIN IS OUT OF DATE"** | Download the new one. |

`failed` and `misses` are the two to act on.

---

## Part 2: Owning the templates

ADAM finds templates **by name**, so layer and frame names are the contract between Figma and the
tool. That is why naming matters more here than in a normal design file.

The convention was set in July 2026 by auditing both production files and ranking every naming
pattern by how recently it had been used. Older patterns like `Adtype: Style` and
`AdType_CamelCase` still work, but do not use them for anything new.

### Container and frame names

```
Adtype_Style-Name                          the container
  Template_Style-Name_WxH                   the template frames inside it
  Template_Style-Name_Variant_WxH           when a style has variants
```

Real ones: `Adtype_Sticky-Note`, `Adtype_Talent-Profile`,
`Template_Photo-With-Text_Dark_1440x1440`.

- **Hyphenate words inside the style name.** `Sticky-Note`, not `StickyNote`.
- **Underscores separate the parts.** Prefix, style, variant, size.
- **Size is `WxH` with no spaces**, like `1440x1800`.
- **Variants go between the style and the size.** `_Single`, `_Double`, `_Dark`.

Sizes and variant words carry meaning, so those have to be exact. Small inconsistencies like a
trailing slash or a double space are tolerated and reported rather than breaking a style, but they
are still worth cleaning up.

### Reddit uses a different convention

Everything above is the Meta convention. The Reddit Templates page does its own thing and the plugin
was taught both:

- **Containers are `Reddit_Adtype_Style-Name`**, like `Reddit_Adtype_Venn-Diagram`.
- **Size frames are named for their dimensions**, `1080x1350` and `1440x1080`.
- **Two sizes per style**, portrait and landscape.
- **Each container also holds a `Rules` frame.** That is the spec card for the copy team. It is not a
  template and is never assembled.

> **Open question worth settling:** whether to bring Meta and Reddit onto one convention. Raised by
> Elise, September 2026, preferring to match Meta to Reddit. The plugin matches on the convention
> rather than a hardcoded list, so this is feasible, but it needs the rename and the plugin change
> coordinated rather than done separately.

### One board master per platform

Each platform has its own, matched on the whole name:

```
Meta - Static Grouped        Reddit - Static Grouped      Linkedin - Static Grouped
Youtube - Static Grouped     Google - Static Grouped      Third Party - Static Grouped
```

Matching on the whole name is deliberate: it lets a retired copy sit in the file harmlessly, because
a name with anything extra on the end will not match.

**Never leave two masters for one platform with the same name.** The plugin takes the first it finds,
so which one you get depends on page order. If you are retiring one, rename it.

### Text layer names

This is the part that decides whether copy populates. Text layers are `Copy_<Role>`:

| Layer name | What goes in it |
|---|---|
| `Copy_Headline` | The main headline |
| `Copy_Subhead` | Subhead or a supporting stat |
| `Copy_Body` | Body copy |
| `Copy_CTA` | The call to action on the image |
| `Copy_Headline-Left` / `Copy_Headline-Right` | Paired headlines, as in Us vs Them |
| `Copy_Testimonial` | The quote in a testimonial ad |
| `Copy_Author` | The attribution under a quote |

Name a text layer anything else and the plugin cannot find it, so that slot keeps its placeholder
text. This is the most common reason ads come out with placeholder copy still on them, and it is
fixed in Figma, not in code.

### Photo slots, and the one rule about nesting

A photo slot is named `Image-Placeholder`. Dual-photo styles use `Left-Image-Placeholder` and
`Right-Image-Placeholder`.

Hyphen, underscore and capitalization do not matter here. `Image_Placeholder` and
`image_placeholder` both work, because the plugin standardizes the name before matching. No need to
rename any of those.

**The one rule that does matter: a photo slot must not contain another photo slot.** If a frame
named `Image-Placeholder` holds a rectangle with the same name, the plugin fills the outer frame and
the inner one keeps the photo already sitting in it, so the template's own stock photo ships on the
finished ad. Nothing appears wrong in the log, which is what makes this one expensive.

Name the wrapper frame `Image` and keep `Image-Placeholder` for the rectangle that actually holds
the fill. The checker finds every instance of this. **As of September 2026 there are none left in the
file.**

### Styles that need more than text swapping

- **Pie Chart.** Sets the centre callout and draws the value arc from a percentage field. The arc is
  data, not decoration.
- **Us vs Them.** Two headlines plus three bullets on each side.
- **Sticky Note.** Two columns, each with a headline and two bullets.
- **Reminder and Tweet/Post Mockup.** These two share a base template.

---

## Adding a new template

1. Build the frames following the convention above, in all three sizes. **Cloning an existing
   template as a starting point is fine and usually faster.**
2. Name the text layers using the `Copy_<Role>` names above, and the photo slot per the nesting rule.
3. Tell your producer, who will get the style added to the tool's registry and the order form. That
   is a code change, so it does not happen the same day.
4. Run a test sprint using only that style and check the log for misses.

**A style cannot be ordered before its template exists.** The order form and the template library are
deliberately kept in step.

---

## Checking your work without running a sprint

Ask for the checker to be run after any batch of template work. It compares the live file against
what the plugin expects and lists what does not match. It takes seconds, costs nothing, and changes
nothing.

**Known open items live in `docs/figma-punchlist.md`**, regenerated from the live file, with a link
to every affected node. That is the list to work from, rather than hunting through this page.

---

## Things that will bite you

**A photo ends up behind the template's own artwork.** The nesting rule above. The ad looks plausible at
a glance because it shows the template's stock photo rather than an empty slot.

**A style quietly uses another style's template.** If a container name is wrong, the plugin can reach
a similarly named template belonging to a different style and use that instead. It is why several
styles share base template names and are kept apart only by their container.

**A style assembles but nothing populates.** The frame it found is probably one with no text layers
in it, rather than the one that has them. Open the container, check which frame actually contains the
`Copy_*` layers, and confirm the container name matches the style.

**One size of a style is missing layers the others have.** Check every size, not just the one you
built first. The run half-fills and looks correct until you compare them.

**A copy of a template kept in another file falls out of date.** The plugin can reach other *pages*
of the ADAM 2026 file but not other *files*, so a separate working file means a hand-copied set that
stops matching the originals. One such file was missing a size and a whole container, and the run
came back with one failure and twenty-five misses.

**The plugin does not pick up changes on its own.** If an engineer updates it, re-download and
re-import. Re-running it in Figma uses whatever version is in your folder.

---

## A note on file ownership

Everything here assumes one Figma file, ADAM 2026, as the single source of truth. The Creative team
does not hold Figma Admin, so if access to that file ever changes, assembly stops until it is
restored. Worth knowing rather than discovering.

---

## Who to ask

- **Copy rules, character caps, approved claims.** Adrie.
- **A sprint that errored before it reached you.** The copywriter who ran it.
- **Anything needing a code change**, including adding a style or running the checker. Your producer,
  who will route it.
