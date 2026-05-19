# Photo Library Tag Reference — Figma Panel Spec

This document specifies a structured reference panel that lives inside the Upwork Figma file. The panel catalogs every tag currently in use across the 120-photo brand library, organized by dimension, so Brandon and the team can reference it during shoot tagging, template design, and copy work.

The panel is designed to live in the Template Library section of the file, near the existing Adtype containers, so it shows up next to the templates that consume the tags.

---

## Panel layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHOTO LIBRARY TAG REFERENCE                                        │
│  120 photos · 67 unique tags · last updated May 6, 2026             │
│  Source: refs/photo_library_tags.csv                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layout: 9 sections in a 3-column grid                              │
│                                                                     │
│  Column 1                Column 2              Column 3             │
│  ┌──────────────┐        ┌──────────────┐      ┌──────────────┐    │
│  │ PEOPLE       │        │ DEMOGRAPHIC  │      │ AGE          │    │
│  │ (16 actors + │        │ (6 tags)     │      │ (4 tags)     │    │
│  │ hands_only)  │        │              │      │              │    │
│  └──────────────┘        └──────────────┘      └──────────────┘    │
│                                                                     │
│  ┌──────────────┐        ┌──────────────┐      ┌──────────────┐    │
│  │ DEVICE       │        │ LOCATION     │      │ COLOR PALETTE│    │
│  │ (8 tags)     │        │ (6 tags)     │      │ (6 tags)     │    │
│  └──────────────┘        └──────────────┘      └──────────────┘    │
│                                                                     │
│  ┌──────────────┐        ┌──────────────┐      ┌──────────────┐    │
│  │ STYLE FIT    │        │ ACTIVITY     │      │ RIGHTS       │    │
│  │ (3 tags)     │        │ (18 tags)    │      │ (empty)      │    │
│  └──────────────┘        └──────────────┘      └──────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Each section is a Figma frame containing:
- A header (the dimension name in bold)
- A one-line subhead (what the dimension means)
- Tag chips listed as text or visual pills

The PEOPLE section is taller than the rest because it has profile cards instead of plain chips. The other 8 sections are similar size and can sit in a clean grid.

---

## Section 1: PEOPLE

**Header:** PEOPLE
**Subhead:** Identifies who is in the photo. Each `man_N` and `woman_N` is a unique recurring actor across shoots. Use `hands_only` when no face is visible.

**Format as profile cards (one per actor) plus a special chip for `hands_only`.**

Each card has 4 lines:

```
man_1
asian · young adult
13 photos
Sample: Asian man at desktop in modern dev office smiling
```

Full content for the 16 actor cards plus hands_only chip:

| ID | Demographic | Age | Photo count | Sample description |
|---|---|---|---|---|
| man_1 | asian | young adult | 13 | Asian man at desktop in modern dev office smiling |
| man_2 | asian | young adult | 5 | Asian man with bun close-up gesturing while talking |
| man_3 | latino | adult | 9 (multi-actor) | Latino man with beard, warehouse settings |
| man_4 | white | young adult | 21 | White man with curly red hair, headphones, evening desk |
| man_5 | latino | adult | 4 | Latino man with mustard shirt, on phone facing camera |
| man_6 | black | mature | 7 | Mature Black man with grey hair at desktop monitor |
| man_7 | south asian | adult | 6 | South Asian man with beard, testimonial portrait |
| woman_1 | white | young adult | 9 | White woman in vest at desk, fashion sketches background |
| woman_2 | white | mature | 5 | Mature white woman, hotel lobby, with another woman |
| woman_3 | white | mature | 12 | Mature white silver-haired woman with laptop, hotel lobby |
| woman_4 | asian | adult | 10 | Asian woman, warehouse, holding tablet |
| woman_5 | black | young adult | 10 | Black woman with afro at laptop, warehouse |
| woman_6 | white | young adult | 13 | White woman at desktop with phone and headphones |
| woman_7 | black | young adult | 11 | Black woman with afro, music studio |
| woman_8 | asian | adult | 7 | Asian woman, greenhouse, smiling |
| woman_9 | south asian | young adult | 9 | South Asian woman with glasses, desktop |

**Special tag chip:** `hands_only` (17 photos) — used when no face is visible.

---

## Section 2: DEMOGRAPHIC

**Header:** DEMOGRAPHIC
**Subhead:** Ethnicity of the primary person in the photo. `mixed` is used when multiple ethnicities are visible together.

**Tags (alphabetized):**

```
asian
black
latino
mixed
south_asian
white
```

---

## Section 3: AGE

**Header:** AGE
**Subhead:** Approximate age range of the primary person. `mixed` is used when multiple ages are visible together.

**Tags (alphabetized):**

```
adult
mature
mixed
young_adult
```

---

## Section 4: DEVICE

**Header:** DEVICE
**Subhead:** Visible device or object in the photo. Use `none` when no device is present. Note: `coffee` is currently in this dimension but is technically a prop, not a device.

**Tags (alphabetized):**

```
coffee
desktop_monitor
headphones
laptop
none
notebook
phone
tablet
```

---

## Section 5: LOCATION

**Header:** LOCATION
**Subhead:** Setting or environment where the photo was shot.

**Tags (alphabetized):**

```
corporate_office
greenhouse
home_office
hotel
studio
warehouse
```

---

## Section 6: COLOR PALETTE

**Header:** COLOR PALETTE
**Subhead:** Dominant color tone of the photo.

**Tags (alphabetized):**

```
bright
cool
dark
green
neutral
warm
```

---

## Section 7: STYLE FIT

**Header:** STYLE FIT
**Subhead:** Which ad templates this photo works well in. A photo can be marked suitable for one or more styles.

**Tags (alphabetized):**

```
lifestyle_photo
photo_with_text
testimonial
```

**Note:** Brandon, as you build new ad styles, this is the dimension that grows. Add new values like `notification` (if photos are needed for the new Notification style) or any other style-specific value here.

---

## Section 8: ACTIVITY

**Header:** ACTIVITY
**Subhead:** What the person in the photo is doing.

**Tags (alphabetized):**

```
browsing
drawing
facing_camera
gesturing
holding_coffee
listening
meeting
on_call
on_phone
presenting
reading
sitting
standing
thinking
typing
waving
working
writing
```

---

## Section 9: RIGHTS

**Header:** RIGHTS
**Subhead:** Usage rights and licensing status for the photo.

**Tags:** (currently empty — no values populated across the 120 photos in the library)

**Note:** The `rights` column exists in the CSV schema but has not been populated. If we want to track rights status (e.g., expiration dates, restricted-use flags), every photo needs a value here. Otherwise this column should be removed from the schema.

---

## Step-by-step build instructions

For Brandon (or whoever sets this up in Figma):

1. Open the Upwork Figma file. Navigate to the Template Library section where the Adtype containers live.

2. Create a new top-level frame called `Photo Library Tag Reference`. Suggested size: 1920 x 1400 pixels. Use the same background color as the Adtype containers for consistency.

3. Add the panel header at the top:
   - Title: "PHOTO LIBRARY TAG REFERENCE" (large, bold)
   - Subtitle: "120 photos · 67 unique tags · last updated May 6, 2026"
   - Source line: "refs/photo_library_tags.csv"

4. Below the header, add a 3-column grid (Figma auto-layout, 3 columns, gap of 40px). Each cell of the grid is one of the 9 sections.

5. For each section, build a frame with:
   - Section header (medium-bold, 18pt)
   - Subhead (regular, 12pt, muted color)
   - Tag list (the tags listed in this doc, copy-paste as a text frame)

6. The PEOPLE section is taller because it has profile cards. Build it as a vertical auto-layout of 16 cards, each with the format shown above (ID + demographic + age + count + sample description). Add the `hands_only` chip as a 17th item at the bottom of that section.

7. Group everything together. Name the group `Photo Library Tag Reference` so it's easy to find later.

8. Anchor it near the Adtype templates so it's discoverable when working on templates.

---

## When and how to update this panel

The tag list grows as the photo library grows. When Brandon adds new tags to photos in `refs/photo_library_tags.csv`, this panel needs to be updated too.

Two ways to handle updates:

**Manual:** when Brandon tags new photos, he checks if any new tag values were introduced. If so, he updates the relevant section in this panel.

**Auto-regenerate:** I can produce an updated version of this doc by running the tag extraction script against the current CSV. Whenever the CSV changes, ping me and I'll regenerate the doc, then Brandon updates the Figma panel from the new spec. Faster than manual auditing.

Either way, the source of truth is the CSV. The Figma panel is a human-readable mirror of what's in the CSV.
