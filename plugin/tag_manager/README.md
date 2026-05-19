# ADAM Tag Manager

A Figma plugin that gives Brandon a live view of every tag in the photo library and lets him jump to any photo by tag.

## What it does

When you open the plugin in the Figma file with the photo library, it scans the current page, finds every tagged photo, and shows you:

- **Total count** of tagged photos and unique tag values
- **Tags grouped by dimension** (People, Demographic, Age, Device, Location, Color Palette, Style Fit, Activity)
- **Photo count per tag** so you can see which tags are common and which are rare
- **A hint section** if the scan finds tags it doesn't know how to classify, or tags that collide between dimensions

Click any tag → the plugin selects every photo using that tag in the canvas and zooms to them.

## What it does NOT do (deliberately, for v1)

- It does not edit tags. Use your existing tagging workflow (hidden rectangles inside photo frames).
- It does not sync with the CSV. The plugin reads the live Figma file as the source of truth.
- It does not show photo thumbnails inside the plugin. The plugin selects photos in the canvas and zooms; Figma shows you the actual photos.

## How to install (one-time setup, takes 30 seconds)

1. Open the Upwork Figma file in the Figma desktop app
2. Top menu: `Plugins` → `Development` → `Import plugin from manifest...`
3. Navigate to `/Users/loganheath/Documents/upwork-creative-pipeline/plugin/tag_manager/manifest.json`
4. Click Open

The plugin is now installed for this Figma account.

## How to run

1. Open the Upwork Figma file
2. Make sure the page with the photo library is the active page
3. Right-click anywhere → `Plugins` → `Development` → `ADAM Tag Manager`
4. The plugin window opens and starts scanning

## How tagging works (so the plugin can find tags)

A "tagged photo" is a Figma frame, component, or instance that:

1. Has at least one image fill on the parent or a descendant
2. Is at least 100 px wide and 100 px tall (filters out tiny tag-marker rectangles)
3. Contains hidden zero-size rectangles whose layer names ARE the tags

Example: a frame named `coding_together_kv` containing a hidden rectangle named `man_1`, another named `corporate_office`, another named `warm`, etc. The plugin reads those rectangle names as tags.

## Tag dimensions

The plugin classifies each tag into one of these dimensions:

- **People** — `man_N`, `woman_N`, `hands_only`
- **Demographic** — white, black, asian, south_asian, latino
- **Age** — young_adult, adult, mature
- **Device** — laptop, desktop_monitor, tablet, phone, headphones, notebook, coffee, none
- **Location** — corporate_office, studio, warehouse, greenhouse, hotel, home_office
- **Color Palette** — warm, cool, dark, bright, green, neutral
- **Style Fit** — lifestyle_photo, photo_with_text, testimonial (plus future: notification, chat_bubble)
- **Activity** — working, meeting, facing_camera, on_phone, etc.

If Brandon adds a new tag the plugin doesn't recognize, it lands in the **Uncategorized** section (highlighted in orange). To make it land in the right dimension, edit `code.js` and add the new tag value to the appropriate array in the `TAG_DIMENSIONS` constant.

## When to refresh

The plugin scans once when it opens. If you tag new photos while the plugin is open, click **Refresh** to rescan.

## Known limitations

- The plugin scans the **current page only**. If photos are spread across multiple pages, run it on each page separately.
- The `mixed` tag is ambiguous (it means "multiple ethnicities" in the demographic column AND "multiple ages" in the age column). The plugin lands it in an Ambiguous section and recommends renaming to `mixed_demographic` and `mixed_age` to fix.
- The plugin reads the file structure. If the tagging convention changes (e.g., tags stored as plugin metadata instead of hidden rectangles), the scan logic needs updating.

## Future work

If Brandon wants more, these are the natural extensions:

- **Tag editing inside the plugin** (select a photo, click tags to add/remove, plugin creates/deletes the rectangles)
- **CSV export** (one button to dump the current tag data as `photo_library_tags.csv`)
- **Multi-page scan** (walk all pages instead of just the current one)
- **Inconsistency detection** (flag photos missing required dimensions, e.g., a photo with people tags but no demographic)

Each is roughly 1-2 hours of additional work if there's demand.
