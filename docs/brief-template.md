# Brief / key-messaging template

A short, structured way to write the **Brief** (Additional Info) on a New Order so ADAM
routes your direction exactly where you intend — instead of guessing.

ADAM reads a brief by breaking it into four buckets (`theme`, `copy_directives`,
`design_directives`, `resources`). Writing under those four headers makes that breakdown
near-deterministic: your theme steers every ad, your copy must-dos are applied verbatim,
your design cues reach the image stage, and your links are kept as resources.

The **Insert brief template** button on the New Order form (Brief step) drops this skeleton
straight into the field.

---

## What goes in the form vs. the brief

**The brief only steers CONTENT.** The *scaffold* is set by the order-form fields and never
changes based on what you write here:

| Decided by the form (NOT the brief) | Steered by the brief |
|---|---|
| How many ads | The core message / angle |
| How many copy variations you choose from | Required phrases, claims, tone, do/don'ts |
| Prospecting / Retargeting split | Visual & ad-format direction |
| Platform, sizes, visual styles | Reference links & assets |

If you write "make 10 versions, prospecting only" in the brief, ADAM ignores it on purpose —
set quantity and audience in the form fields. (This guardrail is verified: a brief that says
"give me 10 versions, prospecting only" is stripped down to just its real content direction.)

---

## The template

```
THEME
(One or two sentences — the single core message or angle every ad should lead with.)

COPY MUST-DOs
- (A required phrase, claim to feature, tone note, or do/don't. Remove this line if none.)

DESIGN DIRECTION
- (A visual, style, or ad-format cue for the image stage. Remove this line if none.)

RESOURCES
- (A reference link, doc, or example asset. Remove this line if none.)
```

### What each section becomes

- **THEME → `theme`.** The angle ADAM writes every concept around. If you fill in *only*
  this, that's fine — the standard rules write the ads around your theme (a "theme-only"
  brief). Keep it to the angle, not sample ads (full sample ads bias generation).
- **COPY MUST-DOs → `copy_directives[]`.** Specific, must-apply copy instructions. These get
  preferential weight in copy generation. Use for required phrases, a claim to feature, a
  tone note, or an explicit do/don't. Leave empty if your theme says it all.
- **DESIGN DIRECTION → `design_directives[]`.** Visual / style / ad-format cues. These are
  handed to the image stage, not the copywriter. Leave empty if none.
- **RESOURCES → `resources[]`.** Links, docs, example assets you referenced. Kept for the
  team; not treated as copy.

A brief with anything beyond a theme is flagged **high-touch** so reviewers know there are
must-apply directives to check at the gates.

---

## Filled example

```
THEME
Speed to hire — on Upwork you can post today and have proposals from qualified,
AI-savvy specialists the same week, so a project never stalls waiting on a hire.

COPY MUST-DOs
- Feature "post today, hire this week" somewhere in the long copy.
- Contrast against slow traditional hiring (months), but never say "staffing" or "employee".
- At least half the long-copy variants should use emoji/checkmark bullets.

DESIGN DIRECTION
- Favor the Split Screen and Us-vs-Them styles (slow-old-way vs fast-Upwork).
- Show a real product surface (search results / proposals list), not an abstract gradient.

RESOURCES
- Q3 speed-to-hire deck: <link>
- Prior winner for reference: sprint 2026-07-meta-… "Precision match"
```

That brief breaks down to: a **theme** (speed to hire), **3 copy_directives**, **2
design_directives**, **2 resources**, `has_high_touch = true` — each routed to the stage
that uses it.

---

## Tips

- **One theme per order.** If you have two genuinely different angles, run two orders — one
  theme keeps the whole batch coherent.
- **Remove the placeholder lines** you don't use, so empty buckets stay empty (don't leave
  the "(A required phrase…)" hint text in — it's just a prompt).
- **Blank is valid.** No brief → ADAM writes to the standard rules for the platform.
- **Don't restate the form.** Sizes, counts, and audience are already captured; repeating
  them in the brief adds noise and is ignored.
