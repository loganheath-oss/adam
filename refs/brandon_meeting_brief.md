# Brandon Meeting Brief — Templates, Styles, and Mapping
## Purpose: Fill in the blanks so the pipeline knows how to use every template correctly

Every one of the 24 visual styles needs its own Figma template. The template is the quality control layer — it defines what the final output looks like regardless of whether the image is a photo, illustration, headshot, or gradient. Without a template, there are no rules for layout, spacing, logo placement, or how copy and images relate to each other.


---

## PART 1: EXISTING TEMPLATES (3 built)

### Template A: LifestylePhoto_1440x1440
**What I know from the Figma file:**
- Frame: 1440x1440
- image_placeholder: 1918x1439 (full bleed, extends beyond frame edges)
- Gradient overlay covers lower portion
- headline_text: bottom left, very large area
- cta_text: bottom left, inside a button frame
- upwork_logo: bottom left

**Questions for Brandon:**
1. What percentage of the image is visible after the gradient? (Top 40%? 50%?)
2. Is the gradient always the same, or does it adapt?
3. Max character count for the headline before it breaks?
4. Which visual styles should use this template?
5. Rules for what kind of image works here — people required? Environment ok? What doesn't work?

---

### Template B: PhotowithText_1440x1440
**What I know from the Figma file:**
- Frame: 1440x1440
- image_placeholder: 1756x1317 (bleeds off left edge)
- Masking shapes create the "Upwork shell"
- headline_text: near bottom
- cta_text: bottom center, inside a button frame

**Questions for Brandon:**
1. What shape does the visible image area actually make? Can you screenshot or describe it?
2. Where should the subject be so the mask doesn't hide them?
3. Is the shell shape always the same or does it change?
4. Max headline character count?
5. Which visual styles should use this template?

---

### Template C: Quote_1080x1080
**What I know from the Figma file:**
- Frame: 1440x1440
- image_placeholder: 397x397 (small circle, upper-left)
- 4 star shapes for rating display
- headline_text: large area in center-right (for the quote)
- #Headline: smaller text above the quote
- Upwork logo at top

**Questions for Brandon:**
1. Is the image always a circular headshot?
2. What goes in #Headline vs headline_text? (Name vs quote?)
3. Stars always present or variable?
4. Max quote length before it breaks?
5. Which visual styles should use this template?


---

## PART 2: TEMPLATES THAT NEED TO BE BUILT (21 remaining)

Every visual style needs a template. Here are all 24 styles. The first 3 have templates. The remaining 21 need them.

For each template Brandon builds, the pipeline needs to know:

**Layout information:**
- What kind of image is needed (photo with people, headshot, illustration, background/gradient, screenshot, none)
- Where the image sits in the frame (full bleed, left half, right half, small circle, background layer)
- How much of the frame the image occupies (percentage)
- What will be around the image (text, UI elements, brand elements, nothing)
- What the image needs to relate to and be in sync with (headline, CTA, overall concept)

**Layer information:**
- image_placeholder layer name and dimensions
- headline_text layer name and position
- body_text layer name and position (if applicable)
- cta_text layer name and position (if applicable)
- upwork_logo placement
- Any other fixed layers (stars, badges, UI frames, chat bubbles, notification bars)

**Composition rules:**
- Where should the subject be positioned in the photo for this template's crop
- How much space above/below/left/right of the subject
- What the image should NOT include (text, logos, elements that compete with template layers)

### STYLES THAT NEED TEMPLATES BUILT:

**People-focused styles (image is a photo with a person):**

| # | Style | Image type | Template notes |
|---|---|---|---|
| 1 | Graphic with Text | Illustrated graphic + text | Does the pipeline generate the graphic, or does Brandon design it? |
| 2 | Split Screen | Two contrasting photos side by side | Does the template have a divider? Or is it one image with both halves? |
| 3 | Us vs Them | Two opposing scenes | Same question as Split Screen — one image or two? |
| 4 | Hybrid | Photo + UI elements | Template provides the UI overlay? Pipeline provides just the photo portion? |
| 5 | Meme | Expressive reaction photo | Template provides the meme text bars? Pipeline provides the photo? |

**Portrait/headshot styles:**

| # | Style | Image type | Template notes |
|---|---|---|---|
| 6 | Social Media Profile | Headshot for profile mockup | Template builds the entire profile UI? Pipeline provides just the headshot? |
| 7 | Talent Profile | Headshot for profile card | Same question — template has the card, pipeline provides the photo? |

**UI-driven styles (template has most of the visual, image is minimal or background):**

| # | Style | Image type | Template notes |
|---|---|---|---|
| 8 | Text Only | Background gradient/texture | Template handles all text layout. What does the background look like? |
| 9 | Chat Bubble | Background + chat UI | Template has chat bubbles? Pipeline provides background + copy? |
| 10 | Notification | Background + notification bar | Template has the notification UI? |
| 11 | Reminder | Background + reminder card | Template has the reminder UI? |
| 12 | Pie Chart | Background + chart graphic | Template has the chart? Or does the pipeline generate data visualization? |
| 13 | Search Results | Background + search UI | Template has the search UI mockup? |
| 14 | Search Bar with Talent Badge | Background + search + badges | Template has all UI elements? |
| 15 | Text with Button and Cursor | Background + text + button UI | Template has the button and cursor? |
| 16 | Poll | Background + poll UI | Template has the poll layout? |
| 17 | Tweet / Post Mockup | Background + social post frame | Template has the social media frame? |

**Specialized styles:**

| # | Style | Image type | Template notes |
|---|---|---|---|
| 18 | Device UI (Photo) | Environment photo + device mockup | Does Brandon composite the device, or does the template have a device frame the image drops behind? |
| 19 | Platform UI | Upwork product screenshot | Is this a real screenshot? Does design provide it? Or does the pipeline need to generate/source it? |
| 20 | Sticky Note | Surface photo + sticky note graphic | Template has the sticky note element? Pipeline provides the desk/surface photo? |
| 21 | Bespoke | Varies | Is this always manual? Or can we define a flexible template? |


---

## PART 3: STYLE-TO-TEMPLATE MAPPING

Once all templates exist, the pipeline needs a clear map:

| Style | Template to use | What pipeline provides | What template provides |
|---|---|---|---|
| Lifestyle Photo | LifestylePhoto_1440x1440 | Full bleed photo | Gradient, headline, CTA, logo |
| Photo with Text | PhotowithText_1440x1440 | Photo for shell | Shell mask, headline, CTA, logo |
| Testimonial | Quote_1080x1080 | Headshot | Circle crop, stars, quote layout, logo |
| Split Screen | ??? | Two-sided photo OR two photos | Divider, text areas, logo |
| ... | ... | ... | ... |

**The key question for every style:** What does the pipeline provide vs what does the template provide?

This is the single most important thing to nail down. If the pipeline generates something the template already has, they'll conflict. If the pipeline doesn't generate something the template expects, there'll be a hole.


---

## PART 4: SIZING AND MULTI-PLATFORM

Right now the 3 templates are all 1440x1440. But orders can request:
- 1440x1440 (1:1)
- 1440x1800 (4:5)
- 1080x1920 (9:16)
- And all the other platform sizes

**Questions for Brandon:**
1. Does each template need a separate version per aspect ratio? (LifestylePhoto_1440x1440 AND LifestylePhoto_1440x1800 AND LifestylePhoto_1080x1920?)
2. Or is there one template per style that adapts/resizes?
3. How many total templates are we looking at? (24 styles x 3 ratios = 72 frames? Or less?)
4. What's the priority order for building them? Which styles does the team use most?


---

## PART 5: WHAT I BUILD AFTER THIS MEETING

Once Brandon fills in these blanks:
1. Machine-readable template registry (JSON) — every template with its node IDs, layer names, dimensions, and composition rules
2. Updated image prompts per style that match exactly how each template uses the image
3. Updated Figma plugin with all template node IDs
4. Style-to-template mapping that the pipeline reads automatically
5. Image review criteria per template (so Claude knows what "good" looks like for each)

**This meeting is the single highest-impact thing for output quality.**
