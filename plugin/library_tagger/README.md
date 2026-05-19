# ADAM Library Tagger — Figma plugin

Walks the 8 source shoot frames in the Upwork brand photography library, clones a template once per photo, drops the photo's image into the template, and names hidden rectangles per the corresponding row in `refs/photo_library_tags.csv`.

The output is a grouped set of tagged components ready for the ADAM pipeline's `figma_library.py` query layer.

## Install (one-time)

1. Open Figma desktop (not the browser version)
2. Open the file you want to work in
3. Menu → Plugins → Development → **Import plugin from manifest...**
4. Select: `~/Documents/upwork-creative-pipeline/plugin/library_tagger/manifest.json`
5. The plugin is now available under Plugins → Development → ADAM Library Tagger

## Pre-flight checklist

Before running the plugin, make sure your Figma file has:

- **A template frame** — name it with the word "template" (case-insensitive). The plugin matches on substring. The template must contain:
  - One image-bearing layer (the image placeholder — first one found will be replaced)
  - 0 or more hidden rectangles (will be renamed/duplicated/deleted per CSV row)
- **8 source shoot frames** — one per shoot. Each must be named with one of these keywords (anywhere in the name, case-insensitive):
  - `asian_man_kitchen`
  - `office_women`
  - `blonde_woman`
  - `bookstore`
  - `pink_hair`
  - `curly_hair`
  - `greenhouse`
  - `tech_fintech`
- **Photos inside each shoot frame** — each photo is a node with at least one image fill. Position determines order: top-to-bottom, then left-to-right.
- **Photo order in each shoot must match the CSV order** — within a shoot, the topmost-leftmost photo is row 1 of that shoot's CSV section.

## Run

1. Open the plugin: Plugins → Development → ADAM Library Tagger
2. Paste the contents of `refs/photo_library_tags.csv` into the textarea
3. Click **Scan** first — verify counts match expectations
4. Click **Generate** — the plugin creates a "Tagged Library Output" frame containing the new tagged components, organized by shoot

## Output

The plugin creates (or reuses if it already exists):

- A `Tagged Library Output` frame to the right of the template
- Inside it, 8 sub-frames named `Shoot 1` through `Shoot 8`
- Inside each sub-frame, one cloned-template component per photo in that shoot, with:
  - The image swapped to the source photo
  - Hidden rectangles renamed/created per the CSV row's tag columns
  - Multi-value cells (e.g. `"man_5, woman_8"`) split into multiple rectangles
  - Empty cells produce no rectangle for that dimension

## Tag columns processed

These CSV columns are written as hidden rectangles inside each cloned component:

- `people` (multi-value)
- `demographic` (multi-value)
- `age`
- `device` (multi-value)
- `location`
- `color_palette` (multi-value)
- `style_fit`
- `activity` (multi-value)
- `rights`

`photo_name` and `description` are NOT written as tag rectangles — `photo_name` becomes the component's name, `description` is informational only.

## Troubleshooting

**"Could not find a frame named 'template'"** — Rename your template frame to include the word "template" anywhere in the name.

**"Source shoot frame for 'X' not found"** — Make sure each shoot frame's name contains the matching keyword listed above. The plugin uses `findOne` with a case-insensitive `includes` check, so partial matches work.

**Mismatch warning between source photos and CSV rows** — The plugin processes the smaller of the two counts. If you have 109 CSV rows but only 100 source photos, only the first 100 rows will be processed. Either trim the CSV to match or add the missing photos to the source shoots.

**Tag rectangles aren't being detected by figma_library.py later** — The plugin creates rectangles with `visible: false`. The Python code looks for nodes with type `RECTANGLE` and `visible === false`. If you want to switch to transparent FRAMES instead (per Brandon's earlier preference), let Logan know and the plugin can be updated.

**Generation is slow on large CSVs** — Expect ~1 second per photo for the first run. Subsequent runs reuse existing output frames.
