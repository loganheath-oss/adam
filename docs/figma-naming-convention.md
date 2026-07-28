# Figma naming convention (THE standard — decided 2026-07-28)

Basis: an audit of both production files ranked every naming pattern by node recency.
Elise's newest work (KOTH sessions 8272–8444) consistently uses the pattern below, and it
is also the most common by count (~1,000+ nodes). Decision (Logan): **adopt her current
convention as the standard**; the plugin adapts to it. Older strata (`Adtype: Style`,
`AdType_CamelCase`) are legacy — never used for new work.

## The pattern

| Thing | Name | Examples |
|---|---|---|
| Adtype container (section holding a style's templates) | `Adtype_Style-Name` | `Adtype_Sticky-Note`, `Adtype_Talent-Profile`, `Adtype_Notification` |
| Template frame | `Template_Style-Name[_Variant]_WxH` | `Template_Photo-With-Text_Dark_1440x1440`, `Template_Lifestyle-Photo-Full-Bleed_1440x1440`, `Adtype_Sticky-Note_Single_1440x1440`* |
| Text layers | `Copy_<Role>` | `Copy_Headline`, `Copy_Body`, `Copy_Subhead`, `Copy_CTA`, `Copy_Headline-Left`, `Copy_Headline-Right`, `Copy_Testimonial`, `Copy_Author` |
| Photo slot | `Image-Placeholder` — **leaf only** (see rule below) | |

*Sticky shipped its frames prefixed `Adtype_` instead of `Template_` — acceptable, but
prefer `Template_` for new frames so frames and containers stay distinguishable.

Rules of thumb: hyphenate words inside the style name (`Sticky-Note`, not `StickyNote`);
underscore separates segments (prefix / style / variant / size); size is `WxH` with no
spaces; layout or theme variants go between style and size (`_Single`, `_Double`, `_Dark`).

## The leaf rule (prevents the 4:5 photo bug)

Only the actual fill RECTANGLE may be named `Image-Placeholder`. Its wrapper frame is
named `Image`. Never name a frame `Image-Placeholder` with a child of the same name —
the plugin then fills the parent and the child's baked photo ships on the ad
(2026-07-27: every Notification 4:5 shipped the template's stock photo this way).
`tests/figma_template_lint.py` flags every violation; 13 pre-existing instances are
pending cleanup.

## Enforcement

- `tests/figma_template_lint.py` (run: `railway run --service adam -- python3
  tests/figma_template_lint.py [fileKey]`) — diffs the live file against the plugin's
  expectation maps and flags nested placeholders. Run it after any template work lands.
- Plugin follow-up (open): update `STYLE_ADTYPE_CONTAINERS` / `STYLE_TEMPLATE_PREFIXES`
  in `plugin/code.js` so the PRIMARY entries use this convention for all 21 styles
  (legacy names stay as fallbacks). Until then assembly works via fallback name matching.
- August template push (Elise, 17 new templates): build to this doc; run the lint on
  each batch.
