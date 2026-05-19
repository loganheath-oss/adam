# ADAM Pipeline — LLM Prompts for MindStudio

**Purpose:** Paste-ready prompts for every LLM node in the MindStudio agent.
**Variable syntax:** `{{variable_name}}` — MindStudio's standard interpolation.
**Source:** Lifted from `run_pipeline.py` (the working local version).

---

## Variable reference

Variables available to all prompts (set by Stage 00 + Stage 01):

| Variable | Source | Example |
|---|---|---|
| `{{sprint_id}}` | Stage 00 | `2026-04-meta-a3f2` |
| `{{driver}}` | Form | `Logan Heath` |
| `{{platform}}` | Form | `Meta` |
| `{{format}}` | Form | `Static Feed` |
| `{{targeting}}` | Form | `Prospecting` |
| `{{brief}}` | Form | `Showcase how Upwork helps...` |
| `{{visual_style}}` | Current iteration | `Lifestyle Photo` |
| `{{quantity}}` | Hard-coded | `6` (per style) |

Knowledge base references (pull via MindStudio retrieval):
- `{{brand_voice}}` — from `brand_voice.txt`
- `{{writing_style}}` — from `writing_style.txt`
- `{{compliance}}` — from `compliance.txt`
- `{{copy_playbook}}` — from `copy_playbook.txt`
- `{{approved_claims}}` — from `approved_claims.txt`
- `{{copy_bank}}` — from `smb_copy_bank.txt`
- `{{targeting_examples}}` — from `prospecting_examples.txt` OR `retargeting_examples.txt`
- `{{performance_data}}` — from `performance_data.txt`
- `{{copy_style_rules}}` — from `copy_style_rules.txt`
- `{{image_style_rules}}` — from `image_style_rules.txt`

---

## Stage 02a — Copy Generation

**LLM:** Claude Sonnet 4.6
**Max tokens:** 1500
**Temperature:** 0.7

### System prompt

```
You are a senior copywriter for Upwork's Paid Acquisition team. You write direct-response ad copy that drives clicks and signups. Follow every brand rule exactly. Use only approved claims. Match the quality of the real ad examples provided. No generic marketing speak.

Output format: valid JSON array only. No preamble, no explanation, no markdown.
```

### User prompt

```
You are writing paid acquisition ad copy for Upwork. Follow every brand rule below exactly.

===== ORDER BRIEF (HIGHEST PRIORITY) =====
This brief is the most current instruction. If it contradicts any reference document below, follow the brief.

{{brief}}

===== BRAND VOICE =====
{{brand_voice}}

===== WRITING STYLE =====
{{writing_style}}

===== COMPLIANCE AND LEGAL RULES =====
{{compliance}}

===== COPY PLAYBOOK =====
{{copy_playbook}}

===== APPROVED CLAIMS AND STATS =====
Use only these verified claims. Do not invent statistics.
{{approved_claims}}

===== COPY BANK (approved headlines and copy) =====
Reference these for tone and structure. Match this quality.
{{copy_bank}}

===== REAL AD EXAMPLES ({{targeting}}) =====
Study these examples closely. Your output should match this quality and style.
{{targeting_examples}}

===== PERFORMANCE DATA — WHAT ACTUALLY WORKS =====
The following shows real ad performance ranked by cost per job post.
Use this to inform your creative decisions. Lean into patterns that perform well.
Black backgrounds dominate the top performers. Quote-driven messaging outperforms
other approaches. Specific freelancer categories outperform generic talent messaging.
{{performance_data}}

===== VISUAL STYLE COPY RULES =====
Find the rules for "{{visual_style}}" below and follow them exactly. Adapt headline length,
body format, and CTA approach based on what this visual style requires.
{{copy_style_rules}}

===== YOUR ASSIGNMENT =====
Generate {{quantity}} ad copy concepts.

Platform: {{platform}}
Format: {{format}}
Visual Style: {{visual_style}}
Targeting: {{targeting}}
Brief: {{brief}}

For each concept provide these exact fields:
- headline (max 40 characters — this goes on the ad creative AND in the ad platform headline field)
- body_short (max 125 characters — Primary Text short variant for the ad platform)
- body_long (max 300 characters — Primary Text long variant with more detail)
- description (max 25 characters — ad platform description field)
- cta (max 20 characters — this goes on the CTA button in the creative)
- concept_tag (short slug like "talent-speed-v1")

RULES:
- Match the brand voice exactly — clear, concise, supportive, professional
- Use only approved claims and statistics from the section above
- Follow all compliance and legal rules
- Study the real ad examples and match their quality
- No generic marketing speak — be specific about what Upwork offers
- Headlines should follow the 95/5 rule: 95% informative, 5% personality

Return as JSON array of objects with exactly these keys: headline, body_short, body_long, description, cta, concept_tag. No other text.
```

### Expected output shape

```json
[
  {
    "headline": "Hire your next expert in days",
    "body_short": "Upwork connects you with top freelancers — fast.",
    "body_long": "Browse 5M+ experts. Interview today. Hire tomorrow. Upwork makes hiring feel less like luck.",
    "description": "Skip the job boards",
    "cta": "Post a job",
    "concept_tag": "speed-hire-v1"
  },
  ...
]
```

### Iteration

Call this once per visual_style in the order. If the order has `Lifestyle Photo` + `Photo with Text` + `Testimonial`, that's 3 calls producing 18 concepts total.

---

## Stage 02b — Copy Self-Review + Rank

**LLM:** Claude Sonnet 4.6
**Max tokens:** 2000
**Temperature:** 0.3

### System prompt

```
You are a senior creative director reviewing ad copy concepts for Upwork paid acquisition. Score strictly. Pick only the concepts you'd actually ship. Your notes should be specific enough that the writer knows exactly why each concept was ranked where it was.

Output format: valid JSON array only. No preamble, no explanation, no markdown.
```

### User prompt

```
You are a senior creative director reviewing ad copy concepts for Upwork paid acquisition.

===== BRAND VOICE RULES =====
{{brand_voice}}

===== COMPLIANCE RULES =====
{{compliance}}

===== APPROVED CLAIMS =====
Only these stats and claims are verified. Concepts using unverified numbers should be ranked lower.
{{approved_claims}}

===== COPY RULES FOR {{visual_style_upper}} STYLE =====
{{copy_style_rules}}

===== CONCEPTS TO REVIEW =====
Visual Style: {{visual_style}}
Platform: {{platform}}
Targeting: {{targeting}}

{{concepts_text}}

===== YOUR TASK =====
Score each concept 1-10 on these criteria:
- Brand voice alignment (does it sound like Upwork?)
- Headline impact (punchy, specific, not generic?)
- Compliance (only uses approved claims? no legal issues?)
- Style fit (does the copy work for {{visual_style}} format specifically?)
- CTA strength (actionable, specific, not generic "Learn more"?)

Then rank all {{quantity}} concepts from best to worst.
Select the TOP 3 as your recommended picks.

Return as JSON array with one object per concept in ranked order (best first):
[
  {
    "original_index": 1,
    "rank": 1,
    "selected": true,
    "score": 8.5,
    "review_notes": "Strong headline, good use of approved stat, CTA is specific and actionable"
  },
  ...
]

Return ONLY the JSON array. No other text.
```

### How to build `{{concepts_text}}`

Before this LLM call, transform `copy_concepts_raw` into a numbered text block:

```
Concept 1:
  headline: Hire your next expert in days
  body_short: Upwork connects you with top freelancers — fast.
  body_long: Browse 5M+ experts. Interview today. Hire tomorrow.
  description: Skip the job boards
  cta: Post a job
  concept_tag: speed-hire-v1

Concept 2:
  headline: ...
  (etc.)
```

In MindStudio this is a data transform step before the LLM node.

---

## Stage 03 — Image Prompt Generation

Image prompts are not LLM-generated — they're **template-assembled** from the visual style and the linked copy. One image prompt per selected copy concept.

**Why not LLM?** Per Brian's rule, photo-based styles pull from Brandon's library (no Gemini photos). Only abstract/background styles need a Gemini prompt, and those are formulaic.

### Routing logic (MindStudio data transform)

```javascript
function buildImagePrompt(concept, visual_style, platform, resolution) {
  const library_styles = ["Lifestyle Photo", "Photo with Text", "Testimonial",
                          "Social Media Profile", "Talent Profile"];

  if (library_styles.includes(visual_style)) {
    return {
      asset_id: concept.asset_id + "_img",
      linked_copy_asset_id: concept.asset_id,
      visual_style: visual_style,
      resolution: resolution,
      generation_method: "library",
      gemini_prompt: "",
      negative_prompt: "",
      note: "Select from Brandon's Figma photo library during assembly"
    };
  }

  return {
    asset_id: concept.asset_id + "_img",
    linked_copy_asset_id: concept.asset_id,
    visual_style: visual_style,
    resolution: resolution,
    generation_method: "generate",
    gemini_prompt: STYLE_PROMPTS[visual_style] || DEFAULT_PROMPT,
    negative_prompt: "text, words, letters, numbers, logos, watermarks, blurry, low quality, distorted faces",
    note: ""
  };
}
```

### Style prompt library (drop into a lookup table)

For generate-mode styles only:

**Graphic with Text:**
```
Abstract illustrated graphic with geometric shapes and flowing lines in Upwork green (#14a800) and warm amber tones on a dark charcoal background. 40% of frame occupied by the graphic, 60% clean space for text. Modern, tech-forward, slightly three-dimensional feel. Not a photograph. No text, no logos.
```

**Split Screen:**
```
Two contrasting scenes side by side with a clear vertical division in the center. LEFT HALF: a stressed person with their head in their hands at a messy desk piled with papers, crumpled notes, and coffee cups. Dim, harsh fluorescent lighting. RIGHT HALF: a relaxed, smiling professional working on a clean laptop at a tidy desk with bright natural window light and a plant. Both people are large and clearly visible as the focal points of their respective halves. Shot from chest up. No text, no logos, no watermarks. Warm natural light. Magazine quality.
```

**Us vs Them:**
```
Two contrasting scenes side by side with a clear vertical division. LEFT: a person looking frustrated at a cluttered desk with stacks of printed resumes, dim overhead lighting, old monitor. RIGHT: a person smiling confidently at a clean modern laptop, bright natural light, minimal desk. Both people are prominent, shot from chest up, clearly the focal points. The contrast should be immediately obvious. No text, no logos, no watermarks. Warm natural light. Magazine quality.
```

**Meme:**
```
Expressive reaction photo of a relatable office moment — a person looking overwhelmed at a laptop, or surprised by something on screen, or giving a knowing look to camera. Candid feel, not posed. Clear top and bottom bands for meme text overlay. No text, no logos, no watermarks. Warm natural light. Magazine quality.
```

**Sticky Note:**
```
Clean desk surface shot from directly above. Light wood or white desk with minimal items — a pen, the edge of a keyboard, maybe a coffee ring stain. Large empty center area where a sticky note graphic will be placed. Natural overhead lighting. Warm tones. No text, no logos, no watermarks.
```

**Text Only / Chat Bubble / Notification / Reminder / Poll / etc.** (background-only):
```
Abstract gradient or textured background for a digital advertisement. Upwork green (#14a800) to deep navy gradient, or solid black with subtle noise texture. No text, no logos, no people, no objects. Clean negative space throughout for UI overlay. Optimized for {{platform}} ad placement.
```

**Default fallback** (unknown style):
```
Professional photo for a {{platform}} {{visual_style}} ad about: {{headline}}. Clean composition, adequate negative space for text overlay. No text, no logos, no watermarks. Warm natural light. Magazine quality.
```

---

## Stage 04b — Image Vision Review

**LLM:** Claude Sonnet 4.6 with vision
**Max tokens:** 300
**Temperature:** 0.2
**Input:** the generated image (attached as base64 or URL) + the prompt text below

### System prompt

```
You are a creative director reviewing AI-generated images for paid acquisition ads. Judge strictly — if an image is marginal, reject it. The pipeline will regenerate rejected images with adjusted prompts.

Output format: valid JSON object only. No preamble, no markdown.
```

### User prompt

```
You are a creative director reviewing an AI-generated image for a paid acquisition ad.

Visual Style: {{visual_style}}
Ad Headline: {{headline}}
Image Category: {{image_category}}

Review this image against these criteria:
{{criteria}}

Score the image 1-10 where:
- 8-10: Good to go, looks professional and matches the style
- 5-7: Acceptable but has issues
- 1-4: Reject, has major problems

Respond with ONLY a JSON object:
{
  "score": <number 1-10>,
  "passed": <true if score >= 7, false otherwise>,
  "notes": "<one sentence explaining the score>",
  "fix": "<if rejected, one sentence telling the image generator what to fix. empty string if passed>"
}
```

### Criteria lookup (choose based on `{{image_category}}`)

**people_focused** (Lifestyle Photo, Photo with Text, Split Screen, Hybrid, Meme, Us vs Them):
```
1. Is there a clear, prominent person as the focal point?
2. Is the person's face visible, natural, and well-lit?
3. Does the composition match the style (e.g., split-screen has two halves, lifestyle has a single subject)?
4. Is the frame filled appropriately (no tiny subjects, no empty frames)?
5. Is the overall composition clean and professional, like a magazine ad photo?
```

**portrait** (Testimonial, Social Media Profile, Talent Profile):
```
1. Is there a clear headshot of one person's face filling most of the frame?
2. Is the face centered, sharp, and not cut off?
3. Does the person look natural, friendly, and professional?
4. Is the background clean and undistracting?
5. Would this work as a professional profile photo?
```

**environment** (Device UI, Sticky Note):
```
1. Is the scene clean, modern, and professional looking?
2. Is there a clear focal point (desk, laptop, workspace)?
3. Is the lighting warm and natural?
4. Does it look like a real photograph, not AI-generated?
5. Is the composition balanced and intentional?
```

**background_only** (Text Only, Chat Bubble, Notification, Reminder, Poll, UI styles):
```
1. Is the background clean with no distracting elements?
2. Is there ample negative space for text/UI overlay?
3. Are the colors on-brand (Upwork green, navy, warm neutrals, or solid black)?
4. Is the composition balanced?
5. Would this work as a background for copy-heavy content?
```

### Retry logic (MindStudio branching)

```
IF score < 7 AND attempts < 3:
  adjusted_prompt = original_prompt + " CRITICAL FIX: " + fix
  → loop back to Stage 04a with adjusted_prompt
  → increment attempts

IF score >= 7 OR attempts >= 3:
  → mark complete, continue
```

---

## Manual assembly — no prompts (reviewer instruction)

The Figma assembly step has no LLM call. Just instructions displayed to the reviewer at Gate 5. See `AGENT_SPEC.md` → Gate 5 section.

---

## Summary table

| Stage | LLM calls | Max tokens | Temp | Input size |
|---|---|---|---|---|
| 02a Copy Generation | 1 per visual_style | 1500 | 0.7 | ~20k (ref docs + prompt) |
| 02b Copy Review | 1 per visual_style | 2000 | 0.3 | ~8k (concepts + rules) |
| 03 Image Prompts | 0 (template lookup) | — | — | — |
| 04a Image Gen | 1 per image (Gemini) | — | — | ~500 chars prompt |
| 04b Image Review | 1 per image (Claude vision) | 300 | 0.2 | image + 500 chars |

**Cost estimate for 1 sprint** (Meta, 3 styles, 3 concepts/style selected, 1 resolution):
- 02a: 3 calls × ~20k input / 1500 output ≈ ~$0.75 (with prompt caching enabled, drops to ~$0.10)
- 02b: 3 calls × ~8k input / 2000 output ≈ ~$0.30
- 04a: 9 Gemini images × ~$0.04 each ≈ $0.36 (library photos = $0)
- 04b: 9 vision reviews × ~1k input / 300 output ≈ ~$0.10

Per sprint total: **~$1.50 without caching, ~$0.80 with prompt caching enabled**.
