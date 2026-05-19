# Photography Tag Central List

**Source:** `refs/photo_library_tags.csv`
**Library size:** 120 tagged photos
**Purpose:** Canonical reference of every tag currently in use across the brand library, so we can lock in a naming convention that the Figma plugin and Python pipeline both consume.

Each section below shows every unique value currently in use in that dimension, with the number of photos using it. Values are sorted by frequency (most-used first).

---

## People (17 values · 168 uses)

`hands_only` is a flag for photos with no visible faces. The `man_N` and `woman_N` numbers identify unique actors (each shoot has one or more named actors who recur across photos).

| Tag | Count |
|---|---|
| man_4 | 21 |
| hands_only | 17 |
| man_1 | 13 |
| woman_6 | 13 |
| woman_3 | 12 |
| woman_7 | 11 |
| woman_4 | 10 |
| woman_5 | 10 |
| man_3 | 9 |
| woman_1 | 9 |
| woman_9 | 9 |
| man_6 | 7 |
| woman_8 | 7 |
| man_7 | 6 |
| man_2 | 5 |
| woman_2 | 5 |
| man_5 | 4 |

---

## Demographic (6 values · 120 uses)

| Tag | Count |
|---|---|
| white | 42 |
| mixed | 40 |
| asian | 22 |
| south_asian | 8 |
| black | 6 |
| latino | 2 |

---

## Age (4 values · 120 uses)

| Tag | Count |
|---|---|
| young_adult | 72 |
| mature | 21 |
| adult | 20 |
| mixed | 7 |

---

## Device (8 values · 141 uses)

`none` is a flag for photos with no device visible. Note that `coffee` is in this column even though it's not technically a device — Brandon may want to move it.

| Tag | Count |
|---|---|
| laptop | 49 |
| desktop_monitor | 23 |
| tablet | 20 |
| none | 13 |
| headphones | 12 |
| phone | 11 |
| notebook | 8 |
| coffee | 5 |

---

## Location (6 values · 120 uses)

| Tag | Count |
|---|---|
| corporate_office | 32 |
| studio | 28 |
| warehouse | 16 |
| greenhouse | 15 |
| hotel | 15 |
| home_office | 14 |

---

## Color Palette (6 values · 120 uses)

| Tag | Count |
|---|---|
| warm | 48 |
| bright | 33 |
| dark | 20 |
| green | 12 |
| cool | 6 |
| neutral | 1 |

---

## Style Fit (3 values · 120 uses)

These are the visual styles the photo is suited for. Each photo has one.

| Tag | Count |
|---|---|
| lifestyle_photo | 77 |
| photo_with_text | 22 |
| testimonial | 21 |

---

## Activity (18 values · 120 uses)

| Tag | Count |
|---|---|
| working | 37 |
| meeting | 35 |
| facing_camera | 13 |
| on_phone | 10 |
| thinking | 4 |
| browsing | 3 |
| gesturing | 3 |
| reading | 3 |
| holding_coffee | 2 |
| writing | 2 |
| drawing | 1 |
| listening | 1 |
| on_call | 1 |
| presenting | 1 |
| sitting | 1 |
| standing | 1 |
| typing | 1 |
| waving | 1 |

---

## Rights (currently empty)

The `rights` column exists in the CSV but no photos have rights values populated. If we want the pipeline to filter by rights status (e.g., expiring photos, restricted-use photos), this column needs to be filled in across all 120 entries.

---

## Inconsistencies and decisions worth Brandon's attention

These are the places where the current data has overlap, ambiguity, or one-off values. Resolving them will make the naming convention cleaner.

**1. The word `mixed` appears in both `demographic` and `age`.** Same string, different meaning depending on column. The Python code currently disambiguates by looking at which column the tag came from, but if Brandon ever flattens tags into a single list this collides. Options:
- Rename to `mixed_demographic` and `mixed_age` for clarity
- Leave as-is and require column context

**2. `hands_only` lives in the `people` dimension** but it's really the absence of a visible person. Two options:
- Keep in `people` as a deliberate "no-face" marker
- Move to a new dimension like `subject_type` with values `person` / `hands_only` / `object_only`

**3. `none` in `device`** is similar — flag for "no device visible." Same decision as #2.

**4. `coffee` is tagged as a device.** Probably belongs in a separate `prop` or `object` dimension rather than `device`.

**5. `adult` and `young_adult` both exist in age.** These could overlap depending on how the tagger interpreted "adult." If `adult` is meant to be 30-50 and `young_adult` is 20-30, that's fine but worth documenting. If they're being used inconsistently, consolidate.

**6. Activity tags with single-photo usage (drawing, listening, on_call, presenting, sitting, standing, typing, waving)** may be too granular. Consider whether to consolidate into broader tags or keep specific.

**7. `corporate_office` vs `home_office` vs `studio`** are clear. But what's the line between `warehouse`, `greenhouse`, and `hotel`? These are specific to your shoot locations. Worth confirming each is intentional rather than a one-off label.

**8. The `rights` column needs to be populated.** Either drop it from the schema or define what values go there (e.g., `cleared_2026`, `expires_2027_03`, `restricted_no_b2b`, etc.) and backfill across all 120 photos.

---

## Naming convention proposal (for Brandon to react to)

Based on what's currently in use, the convention that would require the fewest changes is:

- **Lowercase, snake_case, no spaces.** Already in use everywhere.
- **Single value per dimension** (no multi-value cells). Already in use.
- **Numbered actors** (`man_1` through `man_7`, `woman_1` through `woman_9`). Already in use.
- **Markers for absence** (`hands_only`, `none`) live in the dimension they relate to.
- **Multi-word tags use underscores** (`young_adult`, `corporate_office`, `holding_coffee`). Already in use.

The main convention questions Brandon needs to lock in:

1. Should `mixed` in demographic and `mixed` in age be renamed for disambiguation?
2. Should activity tags with single-photo usage be consolidated or kept?
3. Should `coffee` move from `device` to a new `prop` column?
4. Are we populating `rights` or removing it?
5. What new tags (if any) does Brandon want to add to support upcoming shoots?

Once Brandon settles those, the Python code (`pipeline/figma_library.py` `TAG_REGISTRY`) and the Figma plugin's tag lookups both need to be updated to match the canonical list.
