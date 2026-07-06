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

None of these change the visual design — they're labels, layer structure, and names
so ADAM can fill the boards reliably. Happy to hop on a quick call if anything's
unclear.
