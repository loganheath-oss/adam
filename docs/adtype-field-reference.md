# Which copy fields each ad type gets

**Generated from `configs/ad_type_style_guide.json`. Do not hand-edit.** Run
`python3 scripts/gen_adtype_field_reference.py` after any style-guide change.

For whoever builds templates. Each entry lists the copy fields that ad type
actually carries and the character budget for each, so a template can be built
with the right number of text layers before a sprint ever runs.

Text layers follow `Copy_<Role>`. Where a style has fields with no standard
role name (pie quadrants, poll options, chat lines), the field is listed by its
pipeline name and needs its own agreed layer name.

## Feed copy, which is not on the image

Shown around the ad, never printed on it.

- **Meta**: headline (50), headline_short (30), body_short (125), body_long (300), description (25)
- **Reddit**: headline (50), body (100), description (25). One version only, no long/short pair.

---

## Meta ad types (24)

### Split Screen

A headline at the top above two side-by-side images. The headline is the only copy element — no body copy, no text on the images.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 65 | `Copy_Headline` |
| CTA on the image (`cta`) | 14 | `Copy_CTA` |

### Us vs Them

Split vertically, illustrated. Left = us (Upwork/freelancers), right = them. Each side: a short headline, 2-3 bullet proof points, and a short wrap-up line.

| Field | Max | Figma layer |
|---|---|---|
| us_headline (`us_headline`) | 18 | `Copy_Headline-Left` |
| them_headline (`them_headline`) | 18 | `Copy_Headline-Right` |
| left bullets (`us_bullets`) | 28 | `_needs an agreed layer name_` |
| right bullets (`them_bullets`) | 28 | `_needs an agreed layer name_` |

### Photo with Text (Upwork shell)

A branded photo of a professional in an Upwork border. A short headline in the lower left.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 24 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 43 | `Copy_Subhead` |
| CTA on the image (`cta`) | 19 | `Copy_CTA` |

### Lifestyle Photo (Full Bleed)

Full-bleed branded photography — the photo fills the frame, copy sits over it.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 100 | `Copy_Headline` |
| CTA on the image (`cta`) | 19 | `Copy_CTA` |

### Testimonial

A real client testimonial with brand elements (stars/badges). Always includes attribution (name, job title, company).

| Field | Max | Figma layer |
|---|---|---|
| the quote (`testimonial_quote`) | 100 | `Copy_Testimonial` |
| attribution under the quote (`testimonial_author`) | 51 | `Copy_Author` |

### Social Media Profile

A mockup of a freelancer's social profile — headshot, name (first + last initial), job title. Left/right columns hold supporting content; a subhead below is a punchy wrap-up.

| Field | Max | Figma layer |
|---|---|---|
| profile name (`profile_name`) | 18 | `_needs an agreed layer name_` |
| profile job title (`profile_title`) | 28 | `_needs an agreed layer name_` |
| profile left field (`profile_left`) | 60 | `_needs an agreed layer name_` |
| profile right field (`profile_right`) | 60 | `_needs an agreed layer name_` |
| subhead on the image (`creative_subhead`) | 28 | `Copy_Subhead` |

### Pie Chart

A circular chart in 4 quadrants — features, benefits, outcomes, or stats. A center callout ties them together.

| Field | Max | Figma layer |
|---|---|---|
| quadrant labels (x4) (`pie_labels`) | 30 | `_needs an agreed layer name_` |
| centre callout (`pie_center`) | 28 | `_needs an agreed layer name_` |

### Hybrid

Lifestyle photography + branded Upwork UI elements tied to the concept. Always includes a CTA.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 36 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 60 | `Copy_Subhead` |
| CTA on the image (`cta`) | 22 | `Copy_CTA` |

### Search Results

Three search bars with freelancer role tags inside, each with a hire button. A headline sits above.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 38 | `Copy_Headline` |
| each search result row (`search_results`) | 32 | `_needs an agreed layer name_` |

### Text Only

Text-driven design, maybe a branded background/container. No photo or illustration.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 20 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 60 | `Copy_Subhead` |
| CTA on the image (`cta`) | 22 | `Copy_CTA` |

### Chat Bubble

TWO chat bubbles simulating a text conversation between two people. One bubble opens, the second closes. The exchange should sound like a natural conversation — NOT ad copy, NOT a headline + subtext.

| Field | Max | Figma layer |
|---|---|---|
| chat name label (`chat_label`) | 18 | `_needs an agreed layer name_` |
| chat message (`chat_message`) | 91 | `_needs an agreed layer name_` |

### Notification

An ad that looks like an app notification. Copy mimics a real notification. Always includes a CTA.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 52 | `Copy_Headline` |
| CTA on the image (`cta`) | 12 | `Copy_CTA` |

### Reminder

A mobile app pop-up reminder. Short, direct, action-oriented. Always a CTA.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 52 | `Copy_Headline` |
| CTA on the image (`cta`) | 20 | `Copy_CTA` |

### Device UI (Photo)

A device (phone/laptop) showing Upwork's platform/UI. A headline appears at the top.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 38 | `Copy_Headline` |

### Platform UI

A featured moment from the Upwork platform (homepage, search page, Uma interface). The headline relates to the specific UI feature.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 25 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 18 | `Copy_Subhead` |
| CTA on the image (`cta`) | 16 | `Copy_CTA` |

### Meme

A viral meme format carrying key messaging. Copy usually prompted or requested in the brief.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 43 | `Copy_Headline` |

### Sticky Note

A sticky note with a title at top and listed items below — single or two columns. Checklist, comparison, us-vs-them, or feature/benefit.

| Field | Max | Figma layer |
|---|---|---|
| left_headline (`left_headline`) | 12 | `Copy_Headline-Left` |
| right_headline (`right_headline`) | 12 | `Copy_Headline-Right` |
| left bullets (`left_bullets`) | 30 | `_needs an agreed layer name_` |
| right bullets (`right_bullets`) | 30 | `_needs an agreed layer name_` |
| headline (`single_headline`) | 26 | `_needs an agreed layer name_` |
| list items (`single_bullets`) | 34 | `_needs an agreed layer name_` |

### Poll

A background image with a poll bar overlaid — stats, mock results, or comparisons. Always includes a CTA.

| Field | Max | Figma layer |
|---|---|---|
| poll question (`poll_question`) | 75 | `_needs an agreed layer name_` |
| poll option A (`poll_option_a`) | 14 | `_needs an agreed layer name_` |
| poll option B (`poll_option_b`) | 14 | `_needs an agreed layer name_` |
| CTA on the image (`cta`) | 12 | `Copy_CTA` |

### Tweet / Post Mockup

A mockup of a tweet or social post — organic social content, a veiled ad that reads like a real post.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 115 | `Copy_Headline` |

### Text with Button and Cursor

A UI-style ad with a button element and a cursor clicking it. The copy is INSIDE the button — the button copy is the entire message.

| Field | Max | Figma layer |
|---|---|---|
| button label (`button_text`) | 15 | `_needs an agreed layer name_` |

### Talent Profile

A freelancer profile card with a headline at the top. The profile is the visual element; the headline is the primary copy.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 36 | `Copy_Headline` |
| CTA on the image (`cta`) | 21 | `Copy_CTA` |

### Bespoke

A custom layout built from scratch — no fixed structure.

**No copy on the asset.**

### Illustration

Illustrations tied to the ad theme. The illustration carries the visual concept; copy complements it.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 38 | `Copy_Headline` |
| CTA on the image (`cta`) | 16 | `Copy_CTA` |

### Carousel

A multi-slide ad. Each slide has its own headline. The final slide always includes a CTA. Default 3-4 slides.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 36 | `Copy_Headline` |
| CTA on the image (`cta`) | 22 | `Copy_CTA` |

---

## Reddit ad types (20)

### Reddit — Meme

Memes or nods to viral images paired with brand messaging in a recognizable format.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 45 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Graphic With Text

A ‘cut through’ maze illustrating the easy path of hiring with Upwork.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 12 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 12 | `Copy_Subhead` |

Caps are enforced hard.

### Reddit — Split Screen

Two or more photos on opposite sides paired with copy. Mirrors Meta ads type Split-Screen.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 49 | `Copy_Headline` |
| CTA on the image (`cta`) | 14 | `Copy_CTA` |

Caps are enforced hard.

### Reddit — Pie Chart

Round graph element sliced into segments to show data. Mirrors Meta Pie-Chart but with less copy, due to reduced size.

| Field | Max | Figma layer |
|---|---|---|
| quadrant labels (x4) (`pie_labels`) | 20 | `_needs an agreed layer name_` |
| centre callout (`pie_center`) | 28 | `_needs an agreed layer name_` |

Caps are enforced hard.

### Reddit — App Notification

Inbox icon paired with a headline call to action.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 45 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Text Only

Design that utilizes mostly text to convey message. CTA optional (hidden but built-in). Mirrors Meta Text-Only but with less copy due to reduced size.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 20 | `Copy_Headline` |
| subhead on the image (`creative_subhead`) | 30 | `Copy_Subhead` |
| CTA on the image (`cta`) | 18 | `Copy_CTA` |

Caps are enforced hard.

### Reddit — Person With Text

Text and person profile. Similar to Talent Profile in Meta.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 30 | `Copy_Headline` |
| CTA on the image (`cta`) | 15 | `Copy_CTA` |

Caps are enforced hard.

### Reddit — Venn Diagram

Diagram with limited text capacity.

| Field | Max | Figma layer |
|---|---|---|
| left_headline (`left_headline`) | 7 | `Copy_Headline-Left` |
| right_headline (`right_headline`) | 7 | `Copy_Headline-Right` |
| subhead on the image (`creative_subhead`) | 38 | `Copy_Subhead` |
| headline (`single_headline`) | 50 | `_needs an agreed layer name_` |

Caps are enforced hard.

### Reddit — Person Only

Single person ad, full bleed or profile avatar style. No copy on asset. No copy on Asset.

**No copy on the asset.**

### Reddit — Us vs Them

Opposing views on opposite sides of layout. Total Bullet Text: 22

| Field | Max | Figma layer |
|---|---|---|
| left_headline (`left_headline`) | 22 | `Copy_Headline-Left` |
| right bullets (`them_bullets`) | 60 | `_needs an agreed layer name_` |
| right_headline (`right_headline`) | 18 | `Copy_Headline-Right` |

Caps are enforced hard.

### Reddit — Testimonial

User testimonial with option to feature brand elements such as stars or badges. Mirrors Meta Testimonial but with less copy due to reduced size.

| Field | Max | Figma layer |
|---|---|---|
| the quote (`testimonial_quote`) | 60 | `Copy_Testimonial` |
| attribution under the quote (`testimonial_author`) | 46 | `Copy_Author` |

Caps are enforced hard.

### Reddit — Button

Branded Graphic approach with a Button/CTA and a cursor.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 16 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Search

Search bar with variable job title copy.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 26 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Icon

Icon + Tagline, ideally calling out a type of feature or freelancer status or tag.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 26 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Note

A reminder note format in Upwork Brand colors.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 60 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Notification

Mobile app reminder features key messaging with branded background layer. Mirror to ‘Reminder’ Meta ad type.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 52 | `Copy_Headline` |
| CTA on the image (`cta`) | 20 | `Copy_CTA` |

Caps are enforced hard.

### Reddit — Search and Checkbox

Checkbox UI search format, with or without a headline.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 45 | `Copy_Headline` |
| list items (`single_bullets`) | 12 | `_needs an agreed layer name_` |
| each search result row (`search_results`) | 15 | `_needs an agreed layer name_` |

Caps are enforced hard.

### Reddit — Text with Icons

Text with icons, left aligned.

| Field | Max | Figma layer |
|---|---|---|
| list items (`single_bullets`) | 8 | `_needs an agreed layer name_` |
| headline on the image (`creative_headline`) | 20 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Twitter

Tweet Mockup on Glimmer BG.

| Field | Max | Figma layer |
|---|---|---|
| headline on the image (`creative_headline`) | 115 | `Copy_Headline` |

Caps are enforced hard.

### Reddit — Logo

Logo w/Brand Glimmer Gradient.

**No copy on the asset.**

