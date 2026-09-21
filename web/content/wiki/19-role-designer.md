# Role guide: Designer (Figma assembly and templates)

**Owner:** Natelise Loeb · **Last updated:** 2026-09-21

---

## What is ADAM?

ADAM turns a written brief into finished ad creative. It writes the copy, then hands you a file that
the Figma plugin uses to build the ads against your templates.

```
Paid Acq submits the brief  →  Copywriter reviews the copy  →  ADAM generates the images
      →  YOU build the ads in Figma  →  Paid Acq gets the finished ads
```

### Your role in it

| | |
|---|---|
| **What you get** | An approved sprint and its `asset_manifest.csv` |
| **What you do** | Run the plugin to build the ads, and keep the template library healthy |
| **What you hand off** | Finished ad boards in Figma |
| **Who gets it next** | Paid Acquisition, who requested them |

You own two things: assembling a sprint, and keeping the templates working so assembly keeps working.

---

## Before you start

- **The ADAM 2026 Figma file:** https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026
- **The plugin download:** [LINK: app URL]/plugin
- Figma **desktop app**. The plugin does not run in the browser.
- The sprint link from the copywriter, and its `asset_manifest.csv`.

---

## Quick start: your first assembly

1. **Download the plugin** from the `/plugin` page. Unzip it and put the folder somewhere permanent,
   not Downloads, since the plugin loads from that folder every time.
2. In Figma desktop, open **Plugins → Development → Import plugin from manifest**, and pick
   `manifest.json` from that folder.
3. Open **ADAM 2026** and add a page for your work. Call it whatever you like.
4. Download the sprint's `asset_manifest.csv` from the sprint page.
5. **Plugins → Development → Upwork Pipeline Assembly.**
6. **Choose CSV file**, pick the manifest, then **Click Assemble**.

That's the whole setup. If your page has no `Generated Tests` section, the plugin creates one there
and says so in its log.

### What a good run looks like

The log ends with something like:

```
plugin v2026.09.17
  Image slot frames in board: 2
    slot '1080x1350' -> inner frame '1080x1350' (1080x1350)
  Found template by convention: 'Reddit_Adtype_Testimonial'
  Single copy panel (Frame 15, one-version platform): filled
  Fonts: all 14 available.
Assembly complete... no warnings
```

**"Assembly complete, no warnings"** is what you want. Anything else is covered below.

---

## A few terms used here

- **The plugin.** "Upwork Pipeline Assembly", from Figma's Plugins menu. Reads a CSV, builds ads.
- **The manifest.** The `asset_manifest.csv` a sprint produces. One row per ad.
- **Board master.** The frame the plugin clones once per concept. One per platform.
- **The checker.** A script an engineer runs that compares the live Figma file against what the
  plugin expects and lists what doesn't match. It only reports, it changes nothing.
- **Populates.** What the plugin does to a text layer or photo slot: writes the copy or image in.

Fuller list in the [Glossary](13-glossary.md).

---

## Reading the log

The first line is the plugin version. The last lines say how it went.

| What you see | What it means |
|---|---|
| **"Assembly complete, no warnings"** | Clean run |
| **"Assembly DEGRADED"** | At least one warning. It says this for *any* warning on purpose, after a run where thirteen real problems scrolled past unnoticed. Check the count before worrying |
| **`failed`** | A board couldn't be built. Real problem |
| **`misses`** | A layer or slot it looked for and couldn't find, almost always a name that doesn't match. Real, worth fixing |
| **`empty slots`** | Something was left unpopulated |
| **`name drift`** | A layer or frame name in Figma matched only after the plugin tidied it up: a trailing slash, a double space, different capitalization. About names in the layers panel, not anything on the ad. **The run was fine.** A cleanup list, not a failure |
| **"THIS PLUGIN IS OUT OF DATE"** | Download the new one |

`failed` and `misses` are the two to act on.

---

## Visual QA before you hand off

Spot-check a few boards rather than every one:

- [ ] **No placeholder text.** No "Lorem Ipsum", no "Headline goes here", no leftover sample copy
- [ ] **The photo is the real one**, not the template's built-in stock image
- [ ] **Prospecting and Retargeting have different photos** on "Both" orders
- [ ] **Copy fits.** Nothing clipped, overflowing, or overlapping
- [ ] **The labels at the top read correctly**, naming the concept and the ad type
- [ ] **Every size you expected is present**, and none are hidden
- [ ] **The log said no warnings**, or you have checked each one

### You're done when

- [ ] Every board passes the checks above
- [ ] The log is clean, or every warning is explained
- [ ] The finished boards are where Paid Acquisition can find them
- [ ] Anything you had to fix by hand is reported, so it gets fixed at the source

---

## What you can fix yourself, and what you can't

**You can do these yourself:**

- Rename a layer so copy populates
- Delete a duplicate frame or a stale Rules card
- Restyle a layer to the house font
- Build or fix a template
- Add a `Generated Tests` section

**These need engineering:**

- A style missing from the order form
- Running the checker
- Copy that's wrong rather than misplaced
- Anything where the plugin itself misbehaves
- A new size or platform

---

## Template Rules

ADAM finds templates **by name**, so layer and frame names are the contract between Figma and the
tool. That's why naming matters more here than in a normal design file.

### Container and frame names

```
Adtype_Style-Name                          the container
  Template_Style-Name_WxH                   the template frames inside it
  Template_Style-Name_Variant_WxH           when a style has variants
```

Real ones: `Adtype_Sticky-Note`, `Template_Photo-With-Text_Dark_1440x1440`.

- **Hyphenate words inside the style name.** `Sticky-Note`, not `StickyNote`
- **Underscores separate the parts.** Prefix, style, variant, size
- **Size is `WxH` with no spaces**, like `1440x1800`
- **Variants go between the style and the size.** `_Single`, `_Double`, `_Dark`

Sizes and variant words carry meaning, so those must be exact. Small inconsistencies like a trailing
slash are tolerated and reported rather than breaking a style, but still worth cleaning up.

### Sizes are different per platform

This trips people up. There is no single set of sizes.

| Platform | Sizes |
|---|---|
| **Meta** | 1440x1440 (1:1), 1440x1800 (4:5), 1080x1920 (9:16) |
| **Reddit** | 1080x1350 (4:5), 1440x1080 (4:3) |
| LinkedIn, YouTube, Google, Third Party | Board masters exist; sizes not yet defined |

Build every size a platform uses. A style with one size missing half-fills and looks correct until
someone compares them.

### Text layer names

This decides whether copy populates. Text layers are `Copy_<Role>`:

| Layer name | What goes in it |
|---|---|
| `Copy_Headline` | The main headline |
| `Copy_Subhead` | Subhead or a supporting stat |
| `Copy_Body` | Body copy |
| `Copy_CTA` | The call to action on the image |
| `Copy_Headline-Left` / `Copy_Headline-Right` | Paired headlines, as in Us vs Them |
| `Copy_Testimonial` | The quote in a testimonial ad |
| `Copy_Author` | The attribution under a quote |

Name a text layer anything else and the plugin can't find it, so that slot keeps its placeholder
text. Fixed in Figma, not in code.

Which fields each ad type carries is in `docs/adtype-field-reference.md`, generated from the copy
rules so it can't go stale.

### Photo slots

A photo slot is named `Image-Placeholder`. Dual-photo styles use `Left-Image-Placeholder` and
`Right-Image-Placeholder`.

Hyphen, underscore and capitalization don't matter. `Image_Placeholder` and `image_placeholder` both
work, because the plugin standardizes the name before matching. **No need to rename any of those.**

**The one rule that does matter: a photo slot must not contain another photo slot.** If a frame
named `Image-Placeholder` holds a rectangle with the same name, the plugin fills the outer frame and
the inner keeps the photo already in it, so the template's own stock photo ships on the finished ad.
Nothing looks wrong in the log, which is what makes this expensive.

Name the wrapper frame `Image` and keep `Image-Placeholder` for the rectangle that holds the fill.
**As of September 2026 there are none left in the file.**

### One board master per platform

Matched on the whole name: `Meta - Static Grouped`, `Reddit - Static Grouped`, and so on. Matching
the whole name lets a retired copy sit in the file harmlessly, since a name with anything extra
won't match.

**Never leave two masters for one platform with the same name.** The plugin takes the first it
finds, so which one you get depends on page order. Rename one if you're retiring it.

### Reddit uses a different convention

Containers are `Reddit_Adtype_Style-Name`, and size frames are named for their dimensions rather
than `Template_*`. Each container also holds a `Rules` frame, which is the spec card for the copy
team, not a template.

> **Open question:** whether to bring Meta onto Reddit's convention. Raised by Elise, September 2026.
> Feasible, since the plugin matches on the convention rather than a fixed list, but the rename and
> the plugin change have to be coordinated.

---

## Adding a new template

1. Build the frames following the rules above, in **every size that platform uses**. Cloning an
   existing template as a starting point is fine and usually faster.
2. Name the text layers with the `Copy_<Role>` names, and the photo slot per the nesting rule.
3. Tell your producer, who will get the style added to the tool's registry and the order form. That
   is a code change, so not the same day.
4. Run a test sprint using only that style and check the log for misses.

**A style can't be ordered before its template exists.** The order form and the template library are
deliberately kept in step.

---

## The four problems that cause most bad runs

**1. Old copied templates in another file.** The plugin reaches other *pages* of ADAM 2026 but not
other *files*, so a separate working file means a hand-copied set that stops matching. One such file
was missing a size and a whole container, and the run came back with one failure and twenty-five
misses. **Work in ADAM 2026.**

**2. Renamed text layers.** Copy only populates a layer named `Copy_<Role>`. Rename one and that
slot keeps its placeholder. This is the number one cause of ads shipping with placeholder copy.

**3. A photo slot inside a photo slot.** Covered above. The ad looks plausible because it shows the
template's stock photo rather than an empty slot.

**4. Duplicate Reddit frames.** Several containers hold two frames with the same name and size. The
plugin takes the first it finds, so if they differ, which one ships is a coin flip. Current list
with a link to each is in `docs/figma-punchlist.md`.

---

## Other things that will bite you

**A style uses another style's template.** If a container name is wrong, the plugin can reach a
similarly named template belonging to a different style. It is why several styles share base
template names and are kept apart only by their container.

**A style assembles but nothing populates.** The frame it found is probably one with no text layers,
rather than the one that has them. Open the container and check which frame actually contains the
`Copy_*` layers.

**The plugin doesn't pick up changes on its own.** If an engineer updates it, re-download and
re-import. Re-running uses whatever version is in your folder.

**Update before reporting a bug.** The plugin runs from a folder on each person's machine, so people
can be on different versions without knowing. Three versions were in use at once at one point.

---

## How the plugin finds a template

You don't need this to run an assembly. It's here for when a template isn't being found.

1. A manifest row arrives with a visual style and its copy.
2. The plugin standardizes the style name, lowercasing it and ignoring anything in parentheses.
3. It looks for the style's Adtype container, then widens out.
4. It clones the template, populates the photo slot, then the named text layers.

Where it looks, taking the first hit:

1. **Your current page.** A local copy of a template on the page you're working from always wins, so
   you can override any template by dropping a copy onto your page.
2. **That platform's own template page**, chosen from the manifest's Platform column. This step does
   real work: five pages hold containers with the same names, so without it a Meta run could pull a
   LinkedIn frame.
3. **The Template Library page.**
4. **The whole document**, last resort.

### Two output shapes

**Grouped boards**, the normal case: the plugin finds the platform's board master and puts the run
inside `Generated Tests` as one `Sprint` container.

**Standalone ads**, the fallback: each ad as its own frame in a grid. You get this when the board
master can't be found, and the log says so. So a loose grid means a missing board master, not a
layout preference.

---

## Checking your work without running a sprint

Ask for the checker to be run after any batch of template work. It compares the live file against
what the plugin expects and lists what doesn't match. Seconds, costs nothing, changes nothing.

**Open items are in `docs/figma-punchlist.md`**, regenerated from the live file with a link to every
affected node. Work from that rather than hunting through this page.

---

## A note on file ownership

Everything here assumes one Figma file, ADAM 2026, as the single source of truth. The Creative team
does not hold Figma Admin, so if access to that file changes, assembly stops until it's restored.
Worth knowing rather than discovering.

---

## Who to ask

- **Copy rules, character caps, approved claims** → the creative lead
- **A sprint that errored before it reached you** → the copywriter who ran it
- **Anything needing a code change**, including adding a style or running the checker → your producer
