# Photo Library Tag Standard

The source of truth for a photo's tags is **the image itself** — a human (or a
vision model) looks at the photo and records what is actually visible. This doc
defines the controlled vocabulary and the judgment rules so tags are consistent
and, above all, **accurate**. ADAM reads `refs/photo_library_tags.csv` to choose
photos, so a wrong tag = a wrong photo in an ad.

## Columns

| Column | What it records | Allowed values |
|---|---|---|
| `node_id` | Figma node id | (do not edit) |
| `photo_name` | Figma layer name | (do not edit) |
| `description` | one plain-language line describing the photo | free text, ≤80 chars, factual |
| `people` | each visible person, as `{gender}_{n}` | `man_1`, `woman_1`, … ; `hands_only` when no face is visible; comma-separate multiple people (e.g. `woman_1, man_2`) |
| `demographic` | apparent ethnicity of the people | `asian`, `black`, `latino`, `south_asian`, `white`, `mixed` |
| `age` | apparent age band | `young_adult`, `adult`, `mature`, `mixed` |
| `device` | devices visibly in use/frame | `laptop`, `desktop_monitor`, `phone`, `tablet`, `notebook`, `headphones`, `coffee`, `none`; comma-separate |
| `location` | the setting | `corporate_office`, `home_office`, `studio`, `warehouse`, `greenhouse`, `hotel` |
| `color_palette` | dominant palette | `bright`, `warm`, `cool`, `dark`, `green`, `neutral` |
| `style_fit` | which template family the photo suits | `lifestyle_photo`, `photo_with_text`, `testimonial` |
| `activity` | the primary action | `working`, `typing`, `on_phone`, `on_call`, `meeting`, `presenting`, `reading`, `writing`, `drawing`, `thinking`, `listening`, `gesturing`, `standing`, `sitting`, `browsing`, `holding_coffee`, `facing_camera`, `waving` |
| `rights` | usage rights note | free text (currently empty) |

## Judgment rules

- **people / demographic / age** — describe *only what is visibly true*. If two
  people of different apparent ethnicities appear, `demographic = mixed`. If the
  face isn't visible (hands, back-of-head, silhouette), use `hands_only` and set
  `demographic`/`age` to the best visible cue or `mixed` if none.
- **Accuracy over guessing** — when a field genuinely can't be judged from the
  image, prefer the most defensible value (often `mixed`) rather than inventing a
  specific one. Never carry over a tag that contradicts the image.
- **device / activity** — record what's actually shown; multiple devices allowed.
- **style_fit** — `testimonial` = a clean portrait/headshot suitable for a quote
  card; `photo_with_text` = composition with negative space for overlaid copy;
  `lifestyle_photo` = a person-in-context scene. A photo can fit only what its
  composition supports.
- **New values** must be added to this doc first, then used — don't invent
  one-off values, so the vocabulary stays a fixed set ADAM can rely on.
