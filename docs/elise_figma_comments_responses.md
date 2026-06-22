# Figma Comments → Logan's Responses

**Source:** "Paid Acquisition 2026" → ⚙️ Template Library comments (verbatim, newest→oldest).
**Purpose:** one place to see each comment/question and the answer, so you can reply/resolve in Figma.
**Compiled:** 2026-06-22, grounded in the live Figma file + the ADAM code (`pipeline/figma_library.py`, `configs/template_registry.json`).

**Legend:** `[ ]` = still needs you to reply/resolve in Figma · **TYPE** tags each: `LOGAN` (decision/answer from you), `TOOL` (a change I make in ADAM), `TEAM` (design/copy decision — not a tool thing), `FYI` (context, no action).

---

## TL;DR — the answers that matter

- **Tagging is healthy.** Photo tags are **per-photo, not a duplicated bundle** (120 photos → 120 distinct tag sets). ADAM reads them **live from Figma every run** — there's no separate backend to sync, so "no Figma action required" is essentially true. Only caveat: tag names are **spelling-sensitive** (must match the controlled vocabulary or they silently don't match).
- **Rights ARE handled** — via a `rights_YYYY_MM` hidden-rectangle tag + expiry check, not the flat CSV column. Most photos just don't carry an expiration today (treated as evergreen).
- **Templates: the tool is behind Elise's rebuild.** The registry knows **7** styles (and points at **old, pre-rebuild frame IDs**); the live Template Library has **~21** templates. **~14 are completely unwired.** The plugin itself needs **no rebuild** — it's registry-driven; the work is registry + routing + copy-gen.

---

## Action items pointed at YOU or the TOOL (the short list)

| # | Comment | Type | Status |
|---|---|---|---|
| 8 | PieChart from a data % | LOGAN→TOOL | Feasible, new build — needs data source defined |
| 9 | Will variants confuse ADAM? | LOGAN | **No** — registry already supports variants |
| 11 | "Generated Illustration" drop-zone | LOGAN→TOOL | New fill mode — feasible, needs layer spec |
| 1 | Layer syntax vs deliverables grid / copy generator | LOGAN | Renames DO matter — lock naming (see #19) |
| 19 | Naming convention for versions (A/B, Light/Dark) | LOGAN | Use the existing `variants` pattern |
| 18/23 | Confirm tags correct / duplicated? | LOGAN | Confirmed: live-read, per-photo, not duplicated |
| 16 | More robust tags | TOOL | Enrich the controlled vocab (thin dims) |
| 13 | "Rebuild" | TOOL | Re-point the registry to current frames |
| 28 | Sticky-note: 2 headlines + 4 bullets | TOOL | Needs the 4-quadrant copy-gen (known pending) |
| 4 | Meme copyright | TEAM | Legal/Paid-Acq call, not a tool feature |

---

## Every comment, newest → oldest

### 1. [ ] [UNRESOLVED] Natelise — *Elise's Build Reference* — **TYPE: LOGAN**
> "Double check none of the syntax here changes the header columns on our deliverables grid. And also how that applies to the naming fields in the copy generator."
**Answer:** Yes, this matters. ADAM's plugin fills **named layers**, and the pipeline hands off an `asset_manifest.csv` whose columns are those names. So renaming a layer in a template **will** change what the plugin can fill, and the manifest columns. Rule: any layer rename must be reflected in `template_registry.json`. I can audit the current template layer names against the registry once we start wiring. → resolves with #19.

### 2. [ ] [UNRESOLVED] Natelise — *AdType: SocialMediaProfile* — **TYPE: TEAM**
> "Adrie to advise if we should shrink and up the character count potential here."
**Answer:** Copy/design decision (character budget). Once decided, I set the copy-gen length target for this style. Note: SocialMediaProfile is one of the **~14 templates not yet wired** into ADAM.

### 3. [ ] [UNRESOLVED] Natelise — *SocialMediaProfile* — **TYPE: TEAM**
> "Build a few of these."
**Answer:** Build task (Brandon). No tool action until the template/variants exist; then I wire them.

### 4. [ ] [UNRESOLVED] Natelise — *Meme* — **TYPE: TEAM**
> "We want to discuss usability within copyright laws (with Paid Acq.)" + "also, meme origins."
**Answer:** ADAM's rights system covers **brand-photo licensing windows** (`rights_YYYY_MM` expiry), not meme/template copyright. Meme copyright is a **legal/Paid-Acq policy** decision, not a tool feature. If memes must use only cleared imagery, that becomes a content rule we can enforce (e.g. restrict the meme template to an approved image set).

### 5. [ ] [UNRESOLVED] Natelise — *Platform UI* — **TYPE: TOOL (good framework)**
> Tiered model: Text-only ≈ 90% unassisted (Tier 1) … this template ≈ 10% (Tier 3) … Bespoke = Tier 4. "Templates have labels. Helps manage expectations."
**Answer:** Strong framework — it maps exactly to how I'd scope the wiring. I recommend adding a **`tier` field to each template in `template_registry.json`** so the expectation is encoded (Tier 1 = auto-fill, Tier 3 = needs logic, Tier 4 = designer-built). I'll add tier labels when I wire templates.

### 6. [ ] [UNRESOLVED] Natelise — *Platform UI* — **TYPE: FYI**
> "This one is a flag Elise + Adrie discussed Wed 6/17."
**Answer:** Internal flag. No tool action.

### 7. [ ] [UNRESOLVED] Natelise — *Hybrid* — **TYPE: FYI**
> "Zach may have elements we can use."
**Answer:** Asset-sourcing note. No tool action.

### 8. [ ] [UNRESOLVED] Natelise — *PieChart* — **TYPE: LOGAN → TOOL**
> "Ask Logan: Can the machine alter this to be reflective of a % from a data set?"
**Answer:** **Yes, feasible — but it's a new feature, not a text/photo fill.** Two viable approaches: (a) pre-build a few chart states and ADAM picks the closest %, or (b) ADAM computes the arc and the plugin draws the slice. The real prerequisite is **defining where the % comes from** (the brief? a metric field on the order form?). This is a **Tier-3 build item** — give me the data source and I'll scope it.

### 9. [ ] [UNRESOLVED] Natelise — *Photo with Text* — **TYPE: LOGAN**
> "Narrow down to one template possibly." + "Ask Logan if variants will be confusing to ADAM and if so, how to mitigate."
**Answer:** **Variants are NOT confusing to ADAM.** The registry already supports a `variants` array per template (Text Only, Reminder, Meme use it today), and ADAM selects a variant deterministically. So **keep the variants you want for design reasons** — you don't need to narrow to one for the tool's sake. If you want predictability: set a default variant per style, or let the brief specify which.

### 10. [ ] [UNRESOLVED] Natelise — *Generated Tests* — **TYPE: FYI**
> "Thought is this goes through the request form and it's fully built."
**Answer:** Correct — that's exactly the ADAM flow (order form → pipeline → assembled creative). No action; it confirms the model.

### 11. [ ] [UNRESOLVED] Natelise — *Elise's Build Reference* — **TYPE: LOGAN → TOOL**
> "Generated Illustration Version." → "Maybe this is a blank template, the area a generated asset is dropped into." → "Template is: Layer for generated graphic / Layer for text (node `4635:2578`)." → "connect with Logan."
**Answer:** This is the **generated-illustration drop-zone** — a designed template with a **graphic layer (Gemini-generated)** + a **text layer**. ADAM uses brand *photos* today; this is a **new fill mode** (drop a generated asset into a designed slot, within Brian's no-AI-*people* rule — illustrations/abstracts are allowed). Feasible and it's the bridge to the "designed, not flat-AI" image direction. Needs: the template's named layers finalized + the spec for what Gemini produces. **Tier-3 build item.**

### 12. [ ] ⭐ ELISE [UNRESOLVED] — *Split Screen* — **TYPE: TEAM**
> "Add Descriptions from Reference."
**Answer:** Design task (add template descriptions). Informs the per-template `brandon_rules` in the registry; no code change.

### 13. [ ] ⭐ ELISE [UNRESOLVED] — *Build Area* — **TYPE: TOOL**
> "Rebuild."
**Answer:** Confirmed — you rebuilt the Template Library, which is exactly why the **registry's frame IDs are stale** (they point at the old `47xx`/`53xx` frames; the current templates are `51xx–60xx`). I'll re-point the registry to the current frames as part of wiring.

### 14. [ ] ⭐ ELISE [UNRESOLVED] — *Build Area* — **TYPE: TEAM (access)**
> "Get access to main library."
**Answer:** Figma permissions request (Elise needs access to a main component library). Not a tool/code item — grant access or route to whoever owns that library.

### 15. [ ] ⭐ ELISE [UNRESOLVED] — *Build Reference* — **TYPE: FYI / future**
> "Per Ravi, motion later. Per Adrie/Lee, Localization is currently higher priority than motion. (6/12 Team Sync)"
**Answer:** ADAM is **static-image only** today; motion is out of scope. **Localization** (copy in multiple languages) is a realistic copy-gen enhancement when prioritized — the copy generator can produce localized variants. No immediate action; logged as a future copy-gen feature.

### 16. [ ] ⭐ ELISE [UNRESOLVED] — *Build Materials* — **TYPE: TOOL**
> "Per Ravi, more robust tags (potentially working with the agency that produced these shots). Logan has a plugin here assisting with tag process."
**Answer:** The `tag_manager` plugin writes tags onto the Figma nodes; ADAM reads them live. "More robust" = **enrich the controlled vocabulary** — today some dimensions are thin (`style_fit` = 3 values, `demographic`/`location` = 6 each). I extend the vocab in `figma_library.py`; Brandon/the agency tag photos with the new values.

### 17. [x] ⭐ ELISE [RESOLVED] — *Split Screen* — **TYPE: TOOL (sizing)**
> "Do all completed/green-star templates still need 9:16 added?"
**Answer:** ADAM supports **multiple sizes per template** (Split Screen already has 1440×1440 and 1440×1800). 9:16 is just another size — each size needs its own frame + a registry size entry. Resolved; noted for wiring.

### 18. [ ] ⭐ ELISE [UNRESOLVED] — *Photography Element* — **TYPE: LOGAN (tagging)**
> "Confirm tags are correct in back end and no Figma action is required." → "Logan debugging! 6/12"
**Answer:** **Confirmed.** ADAM reads photo tags **live from the Figma file via the API on every pipeline run** (`fetch_library_components`) — there's **no separate backend store to sync**, so "no Figma action required" is essentially true. Tags are **per-photo** (120/120 distinct). **One caveat:** tags are encoded as hidden-rectangle names and are **spelling-sensitive** — a tag that doesn't exactly match the controlled vocabulary silently won't match. So "tags correct" = correct *spelling* against the vocab.

### 19. [ ] ⭐ ELISE [UNRESOLVED] — *Photo with Text* — **TYPE: LOGAN (naming)**
> "Define naming conventions for differentiating versions (A, B? Light/Dark?). Do what we can now, FB list post-batch-1."
**Answer:** Use the **existing variant pattern**: descriptive variant names in the registry's `variants` array, e.g. `WhiteBorder_GreenBg`, `NoBorder_GreenBg`, `GreenBorder_BlackBg` (exactly how Text Only / Meme already do it). For Light/Dark, `Light` / `Dark` variant names. Layer names stay **per-style, mountain-peak-with-underscores** (the 4/30 decision). I'll document the convention.

### 20. [ ] ⭐ ELISE [UNRESOLVED] — *Build Reference* — **TYPE: FYI**
> "2-do."
**Answer:** Placeholder. No action.

### 21. [x] ⭐ ELISE [RESOLVED] — *Sticky Note* — **TYPE: TEAM**
> "Adrie open to one column approach pitch." — design decision, resolved. No action.

### 22. [x] ⭐ ELISE [RESOLVED] — *Generated Tests* — **TYPE: FYI**
> "EL Note: These are Generated." — label, resolved. No action.

### 23. [ ] ⭐ ELISE [RESOLVED] — *Photography Element* — **TYPE: LOGAN (tagging)**
> "Works — Precision in future." → "Clarify with Logan if the tag bundle is duplicated across all products / needs refinement per photo." → "Confirm tag bundle needs for accuracy."
**Answer:** **Not duplicated — per-photo.** 120 photos → 120 distinct tag sets, zero shared. No de-duplication needed. "Precision in future" = the vocab enrichment (#16) and, optionally, adding `rights_YYYY_MM` expirations where photos have licensing windows.

### 24. [ ] [UNRESOLVED] Brandon — *Build Materials* — **TYPE: TEAM**
> "Color swatches here… use first three for section windows, white bg, black text." (order-form styling)
**Answer:** Order-form **visual styling** note — not an ADAM-pipeline item. Logan/Brandon on the form design.

### 25. [x] [RESOLVED] Brandon — *Testimonial Variants* — **TYPE: TOOL (naming)**
> "What to name the 'quote giver name' layer — `subheadline_text`? `Notification_SubjectName_Text`?" — Adrie: "Looks good."
**Answer:** Resolved (Adrie approved). The layer name just has to match the testimonial template's text-layer mapping in the registry. Follows the per-style convention.

### 26. [x] [RESOLVED] Brandon — *Notification* — **TYPE: FYI**
> "Double checking we have this name copy connected." — layer-connection check, resolved.

### 27. [x] [RESOLVED] Brandon — *Sticky Note* — **TYPE: FYI**
> "Revised Sticky Note is ready." — resolved. (Sticky Note is one of the unwired templates → ready to wire.)

### 28. [ ] [RESOLVED] Brandon — *Sticky Note* — **TYPE: TOOL**
> "What are these cells called in the spreadsheet? Two headlines (one per column) and 4 bullets (2 per column)."
**Answer:** This is the **4-quadrant sticky-note copy structure**. ADAM's copy-gen currently produces a **single headline** — multi-field (2 headlines + 4 bullets) is a **known pending item** ("4-quadrant copy generation"). Wiring the Sticky Note template fully requires that copy-gen enhancement.

### 29. [x] [RESOLVED] Adrie — *Generated Tests* — **TYPE: FYI**
> "On-ad copy populates in the image, doesn't need to be listed here, but discuss." — resolved.

### 30–31. [x] [RESOLVED] Adrie — *Generated Tests* — **TYPE: FYI (copy fields)**
> `Primary_Text_Long / Headline_short / CTA` and `Primary_Text_Short / Headline_Long / CTA`.
**Answer:** These are the canonical copy fields ADAM's copy-gen emits. They align with the pipeline. No action.

### 32. [x] [RESOLVED] Brandon — *Generated Tests* — **TYPE: FYI**
> "Where can we populate the generated ads." — resolved.

### 33. [x] [RESOLVED] Brandon — *Generated Tests* — **TYPE: FYI**
> "Naming conventions for copy layers — discuss in sync." — led to the 4/30 per-style-naming decision. Resolved.

---

## Frame-pin notes (from the transcription)
The "Generated Tests / copy naming" group (#80, #79, #78, #77, #76) and the color-swatch / testimonial / notification pins are positional — they sit inside the **Generated Tests**, **Build Materials**, **Adtype: Testimonial Variants**, and **Adtype: Notification** frames respectively. No action beyond the per-comment answers above.

---

## Live template-library gap (context for the answers above)

**Registry knows (7, pointing at stale frames):** Lifestyle Photo · Photo with Text · Testimonial · Text Only · Split Screen · Reminder · Meme

**Built by Elise, not yet wired (~14):** TalentProfile · Text with Button · Mockup · Poll · Sticky Note · PlatformUI · Mobile Homepage · Notification · Chat Bubble · SearchResults · Hybrid · PieChart · SocialMediaProfile · UsVsThem

**The plugin needs no rebuild** (it's registry-driven). Wiring each template = read its layers → registry entry (frame ID, image/text layers, rules, size, tier) → style→photo-tag route → copy-gen handling → order-form option. Tier-1 (text/photo) are mechanical; Tier-3 (PieChart-from-data, PlatformUI, Generated-Illustration slot) are real build items.
