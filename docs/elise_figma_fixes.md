# Figma template fixes for ADAM (for Elise) — before Thursday demo

File: **Paid Acquisition 2026** (`DoDwumxELkuAuKKSP5p00e`)

Three small template fixes will close the copy-panel and Bespoke issues the plugin
can't fix from the code side. All are in Figma only.

---

## 1. Swap the two "Primary Text" labels on the board copy panels

Board master: **`Meta - Static Grouped`**. Its left panel has two copy blocks,
**Copy Version 1** and **Copy Version 2**. ADAM fills them like this:

- **Copy Version 1 = the LONG version** → long headline + long primary text
- **Copy Version 2 = the SHORT version** → short headline + short primary text

The headline labels are already correct ("Headline Long" on V1, "Headline Short"
on V2). But the **Primary Text labels are swapped**:

| Panel | Label says now | Should say |
|-------|----------------|-----------|
| Copy Version 1 | `Primary Text (short):` | **`Primary Text (long):`** |
| Copy Version 2 | `Primary Text (long):`  | **`Primary Text (short):`** |

Just swap those two label texts. (The content ADAM fills is already correct — only
the labels are backwards, which makes it look like the text is swapped.)

## 2. Make Copy Version 1's panel structure match Copy Version 2's (fixes the empty CTA)

On **Copy Version 1**, the **CTA value comes up empty** because V1's panel is built
differently from V2's — the plugin fills the value layer that sits under each label,
and V1's CTA doesn't have a matching value layer in the same place.

Fix: make V1's block structurally identical to V2's — each of the three rows
(Headline / Primary Text / CTA) should have **a label layer AND a separate value
layer beneath it**, in the same order and grouping as V2. If you can also give the
value layers consistent names, use:

- `CopyV1_Headline`, `CopyV1_Primary`, `CopyV1_CTA`
- `CopyV2_Headline`, `CopyV2_Primary`, `CopyV2_CTA`

(Consistent value-layer names let ADAM fill by name instead of guessing by position,
which makes the panels reliable going forward.)

## 3. Rename the Bespoke template frames

Inside the section **`Adtype_Bespoke/`**, the three size frames are currently named:

- `Template_Split-Screen_1080x1920`
- `Template_Split-Screen_1440x1800`
- `Template_Split-Screen_1440x1440`

They were duplicated from Split-Screen and never renamed. Rename them to:

- **`Template_Adtype_Bespoke_1080x1920`**
- **`Template_Adtype_Bespoke_1440x1800`**
- **`Template_Adtype_Bespoke_1440x1440`**

ADAM already works around the mislabel, but renaming is the clean fix and it removes
a latent bug where a real Split-Screen order could grab these Bespoke frames.

---

## 4. Detach the Talent Profile avatar so its headshot can be swapped

In the Talent Profile templates, the freelancer card's headshot is an **external
library component** — `Avatar Icon/100px` (`component 6057:449`, `remote: True`).
Because it's a locked external component, ADAM **cannot swap the photo**, so every
Talent Profile board shows the same person even though ADAM picks a distinct
library portrait per concept.

Fix (in each `Template_Adtype_Talent-Profile_*` size): select the `Avatar Icon/100px`
instance in the Freelancer card and **Detach instance** (right-click → Detach, or
⌘⌥B), OR replace it with a plain local image fill / `Image-Placeholder`. Once the
avatar is an editable local image, ADAM swaps the headshot automatically — the
name, title, and photo all vary per concept with no further changes.

(ADAM already generates a different name + title + portrait per Talent Profile
concept — this is the only thing standing between that and different people on
every board.)

---

## 5. Cropping / safe-area on the 9:16 (and some 4:5) templates

ADAM places each styled template into its matching board slot at the exact size
(1440×1440 / 1440×1800 / 1080×1920, aligned to 0,0) — so what shows is exactly
what's in the template. On a few templates, content sits **outside the frame** and
gets clipped by the frame's "clip content". Most overflow is intentional (oversized
gradient backgrounds), but these read as bugs and should be pulled into the frame's
safe area for the **9:16 (1080×1920)** and **4:5 (1440×1800)** sizes:

- **Platform-UI (1080×1920 and 1440×1800):** the "Uma" app-window card is much larger
  than the frame (one element overflows the right edge by ~1,185px) and its bottom row
  ("Ask anything…") falls below the frame, so it looks cut off. Scale/reposition the
  card so the whole window (including the input row) sits inside the frame with a
  margin, or crop the mock intentionally at a natural edge.
- **Hybrid (1080×1920):** the `Image-Placeholder` is wider than the 1080 frame, so a
  landscape photo loses its sides. Consider a portrait-friendlier crop box for 9:16 so
  the subject stays centered.
- **Lifestyle-Photo-Full-Bleed (1080×1920):** same full-bleed situation; also confirm
  the bottom headline/CTA sit above the frame's bottom safe margin (the headline read
  as clipped in testing).
- **Notification (1080×1920):** confirm the green border/card has an even margin on all
  four sides at 9:16 (the border read as tight/cut on one edge).

Note on photos: ADAM now uses **one photo per concept across all three sizes** (so the
same person appears in 1:1, 4:5, and 9:16). A single landscape photo can't be cropped
perfectly for both a square and a tall 9:16 frame — the more the 9:16 art direction
relies on a portrait-safe crop box, the better these will look. (If we ever want per-size
photos, that's a product decision — say the word.)

---

None of these change the visual design — they're labels, layer structure, and names
so ADAM can fill the boards reliably. Happy to hop on a quick call if anything's
unclear.
