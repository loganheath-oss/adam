# Figma template punch list

**Generated from the live ADAM 2026 file.** Re-run
`railway run python3 scripts/gen_figma_punchlist.py` to refresh.

File last modified: 2026-09-15T21:48:16Z

Every item links straight to the node. These are template fixes, not code:
nothing here needs an engineer.

---

## 1. Duplicate size frames

Two frames with the same name AND the same size inside one container. The
plugin takes whichever it reaches first, so if the two ever differ, which one
ships is arbitrary. Delete the one you are not using.

- **Reddit_Adtype_Meme** on *-> Reddit Templates*: 2 frames named `1080x1350` at 1080x1350
    - [7023:1354](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7023-1354)
    - [7030:455](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7030-455)
- **Reddit_Adtype_Meme** on *-> Reddit Templates*: 2 frames named `1440x1080` at 1440x1080
    - [7023:1355](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7023-1355)
    - [7030:477](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7030-477)
- **Reddit_Adtype_Graphic-With-Text** on *-> Reddit Templates*: 2 frames named `1080x1350` at 1080x1350
    - [7096:7742](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7096-7742)
    - [7111:158](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7111-158)
- **Reddit_Adtype_Graphic-With-Text** on *-> Reddit Templates*: 2 frames named `1440x1080` at 1440x1080
    - [7096:7767](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7096-7767)
    - [7111:186](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7111-186)
- **Reddit_Adtype_Person-With-Text** on *-> Reddit Templates*: 2 frames named `1080x1350` at 1080x1350
    - [7037:614](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-614)
    - [7111:225](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7111-225)
- **Reddit_Adtype_Person-With-Text** on *-> Reddit Templates*: 2 frames named `1440x1080` at 1440x1080
    - [7037:630](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-630)
    - [7111:270](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7111-270)
- **Reddit_Adtype_Person-Only** on *-> Reddit Templates*: 2 frames named `1080x1350` at 1080x1350
    - [7028:223](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7028-223)
    - [7037:754](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-754)
- **Reddit_Adtype_Person-Only** on *-> Reddit Templates*: 2 frames named `1440x1080` at 1440x1080
    - [7028:224](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7028-224)
    - [7037:755](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-755)
- **Reddit_Adtype_Search-and-Checkbox** on *-> Reddit Templates*: 2 frames named `1080x1350` at 1080x1350
    - [7037:822](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-822)
    - [7293:1267](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7293-1267)
- **Reddit_Adtype_Search-and-Checkbox** on *-> Reddit Templates*: 2 frames named `1440x1080` at 1440x1080
    - [7037:838](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7037-838)
    - [7293:1326](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7293-1326)

---

## 2. A size missing copy layers its sibling has

The portrait and landscape versions of the same style should carry the same
`Copy_*` layers. Where they do not, the run half-fills and looks fine until you
check both sizes.

- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6216:1325](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6216-1325)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6216:1028](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6216-1028)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6207:681](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6207-681)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6066:340](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6066-340)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6066:308](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6066-308)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6332:1208](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6332-1208)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6239:471](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6239-471)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6239:488](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6239-488)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6425:3859](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3859)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6425:3877](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3877)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6425:2212](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-2212)
- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6425:2041](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-2041)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6425:2693](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-2693)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6425:2733](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-2733)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6425:2768](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-2768)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6425:3278](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3278)
- **Reddit_Adtype_Person-With-Text** / `1080x1350` is missing ['Copy_CTA', 'Copy_Subhead']
    - [7111:225](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7111-225)
- **Reddit_Adtype_Text-with-Icons** / `1440x1080` is missing ['Copy_List1', 'Copy_List2', 'Copy_List3']
    - [7028:305](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7028-305)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6507:890](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-890)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6507:908](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-908)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6507:1171](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-1171)
- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6507:1855](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-1855)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6507:2217](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-2217)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6507:2257](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-2257)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6507:2292](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-2292)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6507:3480](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-3480)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6507:7862](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-7862)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6507:7880](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-7880)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6507:8143](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-8143)
- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6507:8827](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-8827)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6507:9189](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-9189)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6507:9229](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-9229)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6507:9264](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-9264)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6507:10471](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-10471)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6507:11332](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-11332)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6507:11350](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-11350)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6507:11613](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-11613)
- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6507:12297](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-12297)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6507:12659](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-12659)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6507:12699](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-12699)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6507:12734](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-12734)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6507:13993](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-13993)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1800` is missing ['Copy_CTA']
    - [6507:14844](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-14844)
- **Adtype_Bespoke/** / `Template_Split-Screen_1440x1440` is missing ['Copy_CTA']
    - [6507:14862](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-14862)
- **Adtype_Search-Results** / `Adtype_Search-Results_1080x1920` is missing ['Copy_Subhead']
    - [6507:15125](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-15125)
- **Adtype_Chat-Bubble** / `Template_Chat-Bubble_1080x1920` is missing ['Copy_Chat-Bubble-1', 'Copy_Chat-Bubble-2']
    - [6507:15809](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-15809)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1080x1920` is missing ['Copy_Left-Column', 'Copy_Right-Column', 'Copy_Subhead']
    - [6507:16171](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-16171)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1800` is missing ['Copy_Subhead']
    - [6507:16211](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-16211)
- **Adtype_Social-Media-Profile** / `Template_Social-Profile_1440x1440` is missing ['Copy_Left-Column']
    - [6507:16246](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-16246)
- **Adtype_Carousel** / `1080x1920 - Carousel` is missing ['Copy_CTA', 'Copy_Headline', 'Copy_Subhead']
    - [6507:17434](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-17434)

---

## 3. Photo slot nested inside another photo slot

When a frame named `Image-Placeholder` contains a child with the same name, the
plugin fills the OUTER one and the inner keeps its built-in photo, so the
template's stock image ships on the finished ad. Nothing looks wrong in the log,
which is what makes this one costly.

**The fix:** only the actual fill rectangle keeps the name `Image-Placeholder`.
Rename its wrapper frame to `Image`.

_None found._

---

## 4. Photo slot naming: no action needed

Most photo slots in the file use `Image_Placeholder` or `image_placeholder`
rather than the documented `Image-Placeholder`. **This is fine and does not need
fixing.** The plugin lowercases the name and treats underscores as hyphens before
matching, so all three forms resolve to the same slot.

- `Image-Placeholder` on 200 node(s)
- `Image_Placeholder` on 68 node(s)
- `image_placeholder` on 67 node(s)
- `Right-Image-Placeholder` on 40 node(s)
- `Left-Image-Placeholder` on 38 node(s)
- `right_image_placeholder` on 37 node(s)

---

## 5. Containers with more than one Rules card

Whichever is read first wins. A stale card marked the whole ad type as blocked
once. Delete the superseded one.

- **Adtype_Carousel** on *⚙️ Template Library*: 2 Rules cards
    - [6335:1544](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6335-1544) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6262:27452](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6262-27452) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 
- **Adtype_Carousel** on *-> Meta Templates*: 2 Rules cards
    - [6425:3273](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3273) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6425:3423](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3423) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 
- **Reddit_Adtype_Split-Screen** on *-> Reddit Templates*: 2 Rules cards
    - [7028:163](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7028-163) — 1546x1286 reads: Headline Max: x CTA Max: x
    - [7055:738](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=7055-738) — 1546x1883 reads: Headline Max: 49 CTA Max: 14
- **Adtype_Carousel** on *-> Linkedin Templates*: 2 Rules cards
    - [6507:3475](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-3475) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6507:3625](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-3625) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 
- **Adtype_Carousel** on *-> Youtube Templates*: 2 Rules cards
    - [6507:10466](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-10466) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6507:10616](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-10616) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 
- **Adtype_Carousel** on *-> Google Templates*: 2 Rules cards
    - [6507:13988](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-13988) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6507:14138](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-14138) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 
- **Adtype_Carousel** on *-> Third Party Templates*: 2 Rules cards
    - [6507:17429](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-17429) — 1546x1610 reads: Headline Max: 60 (Last Slide) CTA Max: 21
    - [6507:17579](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6507-17579) — 1546x1604 reads: Carousel Headline Max: 36 (Last Slide) CTA Max: 

---

## 6. Pill labels set in the wrong font

Both pill labels in every board master use `Neue Montreal` while everything
around them uses `PP Neue Montreal`. When that font is unavailable to whoever is
running the plugin, those labels silently keep their placeholder text.

The plugin now falls back automatically, so this is tidy-up rather than a
blocker. Restyling them to PP Neue Montreal removes the dependency.

- `Inter` on 1251 text layer(s) — example on *📚 Previous Deliverables Libary*: `Description` [4705:9](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=4705-9)
- `Neue Montreal` on 660 text layer(s) — example on *Cover*: `ADAM 2026` [1:103](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=1-103)
- `Shantell Sans` on 144 text layer(s) — example on *⚙️ Template Library*: `Copy_Headline` [6224:3682](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6224-3682)
- `Helvetica` on 113 text layer(s) — example on *Affiliate Email Template*: `Desktop` [4098:627](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=4098-627)
- `Roboto` on 28 text layer(s) — example on *⚙️ Template Library*: `Create report` [6062:1232](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6062-1232)
- `SF Pro Text` on 20 text layer(s) — example on *⚙️ Template Library*: `↳ Time` [6262:25885](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6262-25885)
- `SF Pro` on 8 text layer(s) — example on *-> Reddit Templates*: `1:47` [I7230:128;128:42770](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=I7230-128;128-42770)
- `Helvetica Neue` on 8 text layer(s) — example on *Affiliate Email Template*: `Lorem ipsum` [I4118:1883;2853:4966](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=I4118-1883;2853-4966)
- `Open Sans` on 3 text layer(s) — example on *Affiliate Email Template*: `sender` [4098:686](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=4098-686)
- `Upwork Rza` on 1 text layer(s) — example on *⚙️ Template Library*: `Complete these steps to unlock Upwork’s full potential` [6262:25611](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6262-25611)
- `TikTok Sans` on 1 text layer(s) — example on *-> Meta Templates*: `Copy_Headline` [6425:3134](https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026?node-id=6425-3134)

