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
  Modifiers: `.btn-pill`, `.btn-lg`.
- **Inputs** — `.input` or any control inside `.field`; green focus ring built in.
- **Labels / numbers** — `.adam-label` (uppercase tracked micro-label), `.font-num` (tabular).
- **Status** — `.chip` + `.chip-good/warn/bad/neutral`; `.dot` + `.dot-good/warn/bad`.
- **Motion** — `.stagger` (container; children fade up in sequence), `.reveal-up`,
  `.menu-pop` (dialogs). All disabled under reduced-motion.
- **Display title** — `.adam-display`.

### Canonical nav markup (keep static files in sync with `nav_html()`)

```html
<nav class="adam-nav">
  <a class="adam-nav-brand" href="/" aria-label="ADAM home">
    <span class="adam-logo">ADAM<b>.</b></span>
    <span class="adam-sub">Upwork Paid Acquisition</span>
  </a>
  <div class="adam-nav-links">
    <a href="/new" class="active">New Order</a>
    <a href="/sprints">Sprints</a>
    <a href="/sync-log">Sync Log</a>
    <a href="/learnings">Learnings</a>
  </div>
</nav>
```

Set `class="active"` on the link for the current page.

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
