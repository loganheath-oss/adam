# ADAM — Design System

The visual language for ADAM's user-facing surfaces (order form, sprint dashboard,
review/handoff pages, agent chat). One system, adopted everywhere, so new components drop
in predictably.

**The feel:** a calm, precise instrument for the Upwork Paid Acquisition team. White
canvas, soft rounded cards, layered low-contrast shadows, and the Upwork green spent
*sparingly* so it always means something. Restrained and premium — closer to a well-made
tool than a marketing page.

Source of truth in code: [`static/adam-design.css`](static/adam-design.css). Link it on
every page:

```html
<link rel="stylesheet" href="/static/adam-design.css">
```

---

## 1. Non-negotiable brand rules (Brandon, May 2026)

1. **Palette is fixed.** Use only the Upwork green ramp + neutrals defined in
   `:root`. Never hand-pick a new hue. Status colors (amber/red) are the only
   non-green accents and exist solely for warn/error signalling.
2. **Font weight is capped at Regular (400).** `body, body * { font-weight:400 }`.
   Build hierarchy with **size, color, letter-spacing, and space** — never weight.
   Removing this cap requires Brandon's sign-off.
3. **Typeface is PP Neue Montreal only.** Self-hosted, served at `/fonts`, declared
   once in the design CSS. No Google Fonts, no display/serif faces.
4. **Light mode only.** No dark theme. The canvas stays white; the accent reads against it.

---

## 2. Principles

- **One accent, used rarely.** `--brand-green (#14A800)` for primary actions, links,
  focus rings, selected states, section markers, and the ambient wash. Everything else is
  neutral so the green carries the signal.
- **Soft elevation, never hard borders.** A 1px hairline (`--rule`) + a layered soft shadow.
- **Restrained, fixed radii.** Cards `--radius-2xl` (14), inputs/buttons `--radius-lg` (8),
  chips `--radius-pill`.
- **Numbers are tabular.** Add `.font-num` to any quantity, id, metric, or table figure.
- **Motion is a whisper.** A staggered fade-up on mount, a small pop on dialogs. Always
  `prefers-reduced-motion`-safe.
- **Hierarchy without weight.** Since weight is locked at 400, use the type scale + color
  ramp (`--ink` → `--ink-mid` → `--ink-dim`) + uppercase tracked micro-labels (`.adam-label`).

---

## 3. Tokens (see `:root` in the CSS for the full list)

| Group | Tokens |
|---|---|
| Canvas / ink | `--bg` `--paper` `--ink` `--ink-mid` `--ink-dim` `--rule` `--rule-strong` `--hover` `--tint` |
| Green ramp | `--brand-green` `--brand-green-deep` `--brand-hero` `--brand-green-bright/medium/soft/light/cream/yellow` |
| Status | `--good`/`--good-fg` · `--warn`/`--warn-fg` · `--bad`/`--bad-fg` · `--neutral` |
| Elevation | `--shadow-soft-sm` `--shadow-soft` `--shadow-pop` |
| Radii | `--radius-sm/md/lg/xl/2xl/3xl/pill` |
| Type / layout | `--font-sans` `--page-max` `--nav-h` |

Tint pattern for status chips: a low-alpha fill of the status color with the `*-fg` shade as
text (done via `color-mix` in `.chip-good/warn/bad`).

---

## 4. Components & utilities

All provided by `adam-design.css`:

- **Page frame** — `.adam-page` (flex column) › `.adam-nav` › `.adam-main` ›
  `.adam-container` (max-width, centered). Add `.adam-wash` once per page for the ambient
  green depth.
- **Nav** — `.adam-nav` with `.adam-nav-brand` (the `ADAM.` lockup, the dot is the only green
  in the mark) + `.adam-nav-links` (active link gets a green underline). Server pages call
  `nav_html(active)` in `main.py`; static HTML files inline the **same markup** (below).
- **Cards** — `.card-soft` (+ `.shadow-soft`/`-pop`). Hover-lift data cards by transitioning
  `shadow-soft → shadow-pop`.
- **Buttons** — `.btn` + `.btn-primary` (green), `.btn-secondary` (outline), `.btn-ghost`.
  Modifiers: `.btn-pill`, `.btn-lg`. The primary is **one flat `--brand-green`** with a
  soft shadow — no gradient, no colored glow. Hover deepens to `--brand-green-deep`. Every
  primary action in the app (page buttons, the order form's submit/confirm) uses this same
  calm fill so green reads consistently; a gradient+glow style was tried and removed.
- **Inputs** — `.input` or any control inside `.field`; green focus ring built in.
- **Labels / numbers** — `.adam-label` (uppercase tracked micro-label), `.font-num` (tabular).
- **Status** — `.chip` + `.chip-good/warn/bad/neutral`; `.dot` + `.dot-good/warn/bad`.
- **Motion** — `.stagger` (container; children fade up in sequence), `.reveal-up`,
  `.menu-pop` (dialogs). All disabled under reduced-motion.
- **Display title** — `.adam-display`.
- **Icons** — [Lucide](https://lucide.dev) (ISC), inlined as SVG path data (no
  runtime dependency). In the order form they live in an `ICONS` map with an
  `ic(name, size)` helper; base class `.lic` (inherits `currentColor`,
  `vertical-align:middle`). Stroke style: `viewBox 0 0 24 24`, `fill none`,
  `stroke-width 2`, round caps/joins. Use one consistent set everywhere; icons
  are an accent — color them `--ink-dim`/`--ink-mid`, or `--brand-green` only
  when the icon itself is the signal (e.g. resolution crop marks).

### Canonical nav markup (keep static files in sync with `nav_html()`)

The brand lockup is **Upwork ∣ ADAM.** — the Upwork wordmark SVG, a 1px pipe
separator, then the `ADAM.` lockup (the dot is the only green in the mark). This
is the single consistent header treatment on every page; do not add a second
per-page logo. The full SVG path data lives in `nav_html()` (`main.py`) and in
the order form's inlined nav — keep the two in sync.

```html
<nav class="adam-nav">
  <a class="adam-nav-brand" href="/" aria-label="ADAM home">
    <svg class="upwork-wordmark" viewBox="0 0 296 83" aria-label="Upwork"><!-- paths --></svg>
    <span class="nav-sep" aria-hidden="true"></span>
    <span class="adam-logo">ADAM<b>.</b></span>
  </a>
  <!-- CSS-only mobile menu: checkbox toggles the dropdown, label is the burger.
       The checkbox MUST precede both the burger and the links so the
       `:checked ~` sibling selectors reach them. -->
  <input type="checkbox" id="adam-nav-toggle" class="adam-nav-toggle">
  <label for="adam-nav-toggle" class="adam-nav-burger" aria-label="Toggle menu">
    <span></span><span></span><span></span>
  </label>
  <div class="adam-nav-links">
    <a href="/new" class="active">New Order</a>
    <a href="/sprints">Sprints</a>
    <a href="/sync-log">Sync Log</a>
    <a href="/learnings">Learnings</a>
  </div>
</nav>
```

Set `class="active"` on the link for the current page. `.upwork-wordmark` and
`.nav-sep` are sized once in `adam-design.css` — never re-declare them per page.

**Mobile (≤640px):** the link row collapses into a **CSS-only hamburger** — no
JS. The hidden checkbox drives a dropdown panel under the bar (frosted, same
blur as the nav) and the burger morphs into an X via `:checked ~` selectors;
the active link gets a `--tint` fill instead of the underline. Because every
link is a full-page navigation, the menu resets closed on click — no script
needed. All of this lives in `adam-design.css`; the markup above is the only
per-copy change, so keep `nav_html()` and the order form's inlined nav in sync.

### Multi-step forms (tabs / wizard)

The order form is the reference pattern: a single white `.tab-card` with a
**horizontal step-tab header** on top and the form **panel** below. A standalone
`<h1>` hero sits above the card. The card is the page's hero, and green stays an
*accent* — never a filled slab. Rules:

- **The card is one calm white surface.** `.tab-card` is `--paper` with a soft
  shadow and a hairline border — no gradient. The only green on it is the active
  tab's underline + step label and the primary button. This keeps the accent a
  *signal* (§2: "one accent, used rarely"). A green gradient rail was tried and
  removed — it overwhelmed the page and buried the hierarchy.
- **Steps are a horizontal tab bar.** `.tab-nav` is a
  `grid-template-columns:repeat(3,1fr)` strip across the card top on `--hover`,
  each `.tab-btn` a check circle + step label + name. The active tab lifts to
  `--paper` with a `--brand-green` bottom border.
- **One 12-column grid is the alignment spine.** `.grid-12`
  (`grid-template-columns:repeat(12,1fr)`, shared `--grid-gutter` column-gap,
  `32px` row-gap) is the single source of horizontal rhythm; content blocks
  snap to **column spans** rather than ad-hoc `fr` ratios or fixed pixel caps.
  Step 1 is a **5 / 7 split** — fields `grid-column:1/span 5`, the inline
  calendar `6/span 7` — the cleanest 12-column approximation of the golden
  ratio (≈1.4), calendar as the dominant block. Step 2's three-up card rows are
  the same spine read as span-4 thirds. Snapping to spans is what makes the
  left field edge, the calendar's right edge, the `.field-note`, and the
  primary action all land on the same vertical lines. Below ~700px the two
  columns each go `grid-column:1/-1` (stack). **Never reintroduce a fixed
  `max-width` on a grid child to "make it line up" — that was the old random
  feel; let the span define the width.**
- **The work surface is `.tab-panel`.** The primary action sits in a
  `.tab-footer` **inside** the panel, flush-right with the inputs
  (`justify-content:flex-end`). Because the footer is nested in the already-
  padded panel, it carries **zero horizontal padding** (`padding:30px 0 44px`)
  so its right edge lines up exactly with the calendar/inputs above — re-applying
  the panel's padding here is the classic misalignment bug. A Back button is
  pushed hard-left with `margin-right:auto`. Step 1's primary action is an
  **icon-only arrow circle** (`.next-arrow-btn`): grey/inert until
  `validateStep(1)` passes, then it animates to `--brand-green` (`.is-active`,
  toggled by `_updateTab1Arrow()` on every `input`/`change`) — the form
  *earns* its green as the user completes it.
- **Gate forward progress.** A step is only reachable once every earlier
  required step validates. Implement one `validateStep(n)` per step; derive both
  the *furthest reachable* tab and the per-tab `done`/`locked` styling from it
  (`refreshTabState()`), recomputed on every `input`/`change`. Backward
  navigation is always allowed. The done-check `✓` is injected by JS via
  `textContent` — don't also add it in CSS (`::after`) or it doubles.
- **Step states:** `.tab-btn.active` gets a green underline + green step label;
  `.tab-btn.done` a solid green check circle; `.tab-btn.locked` is dimmed
  (`opacity:.5`) with a dashed ring, no pointer.
- **Field constraints ride the label**, not a line below it: pair the label and
  a right-aligned `.field-note` in a `.field-label-row` (e.g. "5 business days
  minimum" next to *Delivery Date*). On the grid the note sits at the **right
  edge of the calendar's 7-column span**, so it reads as a caption on that block.
- **Audience is a pill toggle, not a dropdown.** Two `.aud-pill` buttons
  (Prospecting / Retargeting); selecting both writes "Prospecting and
  Retargeting" to the hidden `#targeting` select (data contract intact).
  `pickAudience()` owns the toggle and fires `change`/`input`. The pill
  container keeps `id="targeting-trigger"` for the validate/highlight contract.
- **Headline treatment:** page title is `<h1>` with the second line in a dim
  `<span>` ("Ad Creative" in `--ink`, "Request" in `--ink-dim`). No eyebrow —
  it added a label with no meaning. Keep the hero tight to the nav.
- **Below ~700px** the grid columns each go full-width (`1/-1`), the panel
  padding tightens, and the tab bar compresses.

---

## 5. Adding a new page or component — checklist

1. **Link the system:** server page → `page_head(title)` + `nav_html(active)` from
   `main.py`; static file → `<link rel="stylesheet" href="/static/adam-design.css">` + the
   nav markup above + `<div class="adam-wash">`.
2. **Wrap content** in `.adam-main > .adam-container`; add `.stagger` to the top-level group
   for the mount animation.
3. **Build from tokens/utilities.** Reach for `.card-soft`, `.btn*`, `.chip*`, `.adam-label`,
   `.font-num` before writing new CSS. Page-local CSS is for genuinely page-specific
   components only (e.g. the order form's batch cards) and must use the tokens — no raw hexes.
4. **Respect the rules:** weight 400, palette-only colors, light mode, tabular numbers.
5. **Verify** in the browser at the relevant route, and check reduced-motion.

> Keep raw hex values out of page CSS. If you need a color, it's a token — or it shouldn't
> exist. That discipline is what keeps the system coherent as it grows.
