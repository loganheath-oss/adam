# Upwork Pipeline Assembly — Figma Plugin

This plugin takes the pipeline's generated images and ad copy,
fills them into Brandon's Figma templates, and exports the
assembled frames as final production PNGs.

## How to install

1. Open Figma desktop app
2. Go to **Plugins > Development > Import plugin from manifest...**
3. Select the `manifest.json` file from this folder
4. The plugin appears under **Plugins > Development > Upwork Pipeline Assembly**

## How to use

1. Run the pipeline: `python3 pipeline/run_pipeline.py --csv order.csv`
2. The pipeline saves images to `runs/{sprint_id}/images/` and a manifest to `runs/{sprint_id}/asset_manifest.csv`
3. Open the Figma template file (Paid Acquisition 2026)
4. Run the plugin: **Plugins > Development > Upwork Pipeline Assembly**
5. Load the `asset_manifest.csv` from the pipeline run
6. Select all `.png` files from the `runs/{sprint_id}/images/` folder
7. Click **Assemble All Assets**
8. The plugin clones each template, fills `image_placeholder` with the AI image, updates `headline_text` and `cta_text` with the generated copy
9. Click **Export Assembled Frames** to export final PNGs
10. Use Figma's File > Export to save the assembled frames

## What the plugin does

For each row in the manifest CSV:

1. Finds the right template frame based on visual style
2. Clones it (so the original template stays clean)
3. Fills every `image_placeholder` layer with the generated image
4. Updates `headline_text`, `body_text`, and `cta_text` with the ad copy
5. Names the clone `ASSEMBLED_{asset_id}` for easy identification

## Layer naming convention

These layer names must exist in the templates:

- `image_placeholder` — background image layer (RECTANGLE or ELLIPSE)
- `headline_text` — headline text layer
- `body_text` — body copy text layer (optional)
- `cta_text` — call-to-action text layer (optional)
- `upwork_logo` — logo layer (not modified by the plugin)

## Template mapping

| Visual Style | Template Frame |
|---|---|
| Photo with Text | PhotowithText_1440x1440 |
| Lifestyle Photo | LifestylePhoto_1440x1440 |
| Testimonial | Quote_1080x1080 |
| Hybrid, Split Screen, Device UI, Meme, Us vs Them | LifestylePhoto_1440x1440 |
| Graphic with Text, Sticky Note | PhotowithText_1440x1440 |
| Social Media Profile, Talent Profile | Quote_1080x1080 |

As Brandon builds more templates, add their frame IDs to `TEMPLATE_MAP` in `code.js`.
