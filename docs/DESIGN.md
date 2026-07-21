# ADAM — Design system (the source of truth for look & feel)

**Why this file exists.** The homepage Ravi designed *feels* right — airy, legible, deliberate — and we kept drifting from it in the rebuild. This file captures the exact tokens **and the reasoning behind them**, so any new screen (or any fix) can be built to the same bar without re-guessing. When something looks "off," the answer is almost always "it violated a rule below." Reference implementation: **`upwork-adam.vercel.app`** (Ravi's version). When in doubt, open it and measure — don't eyeball.

> **The one rule that governs the rest:** every detail is intentional. Spacing, weight, contrast, motion, and affordance are all *decisions*, not defaults. "Close enough" is the bug.

---

## 1. Principles (the "why")

1. **Dark shell, light work-surfaces.** The app is a dark canvas (`#181818`). Marketing/landing lives *on* the dark; working content (wiki, forms, dashboards) sits on **white cards** floating on that dark. The contrast is the design — it creates focus (chiaroscuro), not decoration.
2. **Airiness = legibility.** Generous, consistent spacing is what makes it read as "designed." Text needs room to breathe; sections need clear separation. Cramped + all-one-size = hard to read. Vary size/weight to create hierarchy, then give it space.
3. **Load calm, never jarring.** First paint is dark. No white flashbang, no elements popping/stacking, no layout shift as things settle. The page should *arrive*, not *assemble*.
4. **Everything clickable looks clickable.** If you can click it, it must signal that — cursor, hover state, and a visual affordance (underline, arrow, lift, border). If two things look identical but only one is interactive, that's a defect.
5. **Nothing moves that shouldn't.** Navigating between pages must not shift the logo, nav, or tabs. Reserve space for scrollbars and dynamic pills so the frame stays rock-steady.

---

## 2. Tokens (exact values)

### Color
| Token | Value | Use |
|---|---|---|
| **Upwork green** (`--primary`) | `#14A800` · `rgb(20,168,0)` | Primary actions, accents, active nav, icons on dark |
| **Dark canvas** | `#181818` · `rgb(24,24,24)` | `html`/landing background; the shell |
| **White work-surface** | `#FFFFFF` | Wiki article, cards, form surfaces |
| **Ink** | `#0A0A0A` | Text on white surfaces |
| Text on dark — primary | `rgba(255,255,255,1)` | Headings on dark |
| Text on dark — secondary | `rgba(255,255,255,0.6)` | Body/descriptions on dark |
| Hairline on dark | `rgba(255,255,255,0.1)` | Borders, nav underline, card edges |
| Featured green border | `rgba(20,168,0,0.4)` | The one highlighted card |

**Landing glow** (layered radial gradients, subtle — never a solid fill):
```
radial-gradient(1000px 540px at 80% -10%, rgba(20,168,0,0.16), transparent 60%),
radial-gradient(760px 480px at 4% 4%,   rgba(132,236,199,0.10), transparent 58%),
radial-gradient(900px 680px at 60% 118%, rgba(103,220,18,0.06), transparent 62%)
```

### Type
- **Face:** PP Neue Montreal (self-hosted, `/fonts/…woff2`). This is the Upwork brand face — don't substitute.
- **Hero H1:** `80px` (lg), weight `500`, line-height `0.98`, letter-spacing `-0.02em`. Big and tight — but only for the hero. Responsive: `text-6xl → 7xl → [80px]`.
- **Hierarchy comes from contrast, not from making everything big.** Card titles `text-xl` (20px). Body/desc `text-sm`/`text-base` at `white/60`. If a screen feels "loud," it's usually too much bold at one size — thin the weight and add space, don't shrink globally.

### Shape & depth
| Token | Value |
|---|---|
| Card radius | `24px` (`rounded-3xl`) |
| Pill/CTA radius | `9999px` (full) |
| Thumb/tile radius | `12px` (`rounded-xl`) |
| Card padding | `32px` (`p-8`) |
| Card backdrop | `backdrop-blur(12px)` |
| Featured card glow | `0 30px 80px -30px rgba(20,168,0,0.42)` + `inset 0 0 0 1px rgba(20,168,0,0.16)` |

### Motion
- **Marquee:** `220s linear infinite`, two rows opposite directions; pause on hover; disabled under `prefers-reduced-motion`.
- **Hover transitions:** `200ms`, easing `cubic-bezier(0.16, 1, 0.3, 1)` (the "expo-out" curve — quick then settle). Use this everywhere for consistency.
- **Card hover:** lift `-translate-y-1`, green border + green glow, CTA arrow nudges `translate-x-0.5`.

---

## 3. Component specs

### Nav (top bar)
- Height ~`61px`, single `1px` bottom hairline `rgba(255,255,255,0.1)`.
- **Padding is specific — give items room.** Don't let items crowd each other or touch the viewport edge. Active item = green underline.
- Logo must not move between routes (see §4 stability).

### Hero
- Contained to `max-w-[1080px]`, comfortable side padding (`px-6`, more on desktop).
- Two CTAs side by side (`gap-3`):
  - **Primary** — green pill: `bg-[#14A800]`, white text, weight `500`, `px-6 py-3`, `text-sm`, trailing `→`. Hover `brightness-95`.
  - **Secondary** — outline pill: transparent, `1px` hairline border (`border-white/20`), text `white/80` weight `400`, same padding/radius. Hover brightens border + text.

### Entry cards (the 2×2 grid)
Four cards, `sm:grid-cols-2`, `gap-6`:
1. **New order** (featured) → `/new`
2. **Sprint runs** → `/sprints`
3. **Ask ADAM** → `/agent`
4. **How it works** → `/wiki`

- Radius `24px`, padding `32px`, `backdrop-blur(12px)`, subtle gradient fill.
- **Featured** (first only): green border `rgba(20,168,0,0.4)`, green-tinted gradient, green glow shadow.
- **Non-featured:** `border-white/10`, white-tinted gradient; hover → green border + green glow.
- Icon chip: `44px`, `rounded-xl`, `border-white/14`, `bg-white/6`, **green** stroke icon.
- Each card = icon → title (`text-xl`, white) → desc (`text-sm`, `white/60`) → green CTA line with nudging arrow.

### Creative marquee
- Full-bleed, two rows scrolling opposite ways.
- **Row 2 runs the thumbnail list reversed** so the rows never show the same tile stacked on first paint. (This was the "duplicates stacked" bug — identical row content.)
- Tiles `160px`, `rounded-xl`, `border-white/10`, image at `opacity-80` → `100` on hover.
- Horizontal edge mask fades both ends into the dark: `linear-gradient(90deg, transparent, black 10%, black 90%, transparent)`.

---

## 4. Guardrails (recurring failures → the fix)

| Symptom | Cause | Fix |
|---|---|---|
| **White flashbang on load** | Body paints white before the dark section | `html`/`body` background `#181818` on landing (scoped via `:has(.adam-home)`); first paint is dark |
| **Logo/nav jumps between pages** | Scrollbar appears on long pages (esp. Windows Chrome) and shifts layout | `html { scrollbar-gutter: stable }` — reserve the track always |
| **Marquee tiles stacked/duplicated on load** | Both rows render identical content at the same phase | Reverse row 2's content list |
| **Can't tell what's clickable** | Interactive element styled identically to static text | Add affordance: hover state, cursor, underline/arrow/lift; clickable error rows get a "click to expand" cue |
| **Missing hover states** | Only some interactive elements got `hover:` | Every clickable element gets a `200ms` expo-out hover |
| **Tabs/pills shift things up-down** | A dynamic pill (e.g. "Last 30 days") changes row height | Fixed heights / reserved space so rows don't reflow |
| **Header too close to the edge** | No enforced page inset | Contain to `max-w-[1080px]` + `px-6`; never let headings touch the viewport edge |

---

## 5. How to use this file

- **Before building a screen:** pick the surface (dark shell vs white card), then pull tokens from §2 and the nearest component in §3. Don't invent new radii/spacings/greens.
- **When something looks off:** check §4 first — it's usually a listed guardrail.
- **When extending the reference:** measure `upwork-adam.vercel.app` with computed styles, add the new value here with its rationale, and *then* build. This file grows; it doesn't get bypassed.
