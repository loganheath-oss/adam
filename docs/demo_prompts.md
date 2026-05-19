# ADAM Pipeline — Demo Prompts

Drop the project instructions block once. Run the prompt sequence end-to-end against a fresh sprint to capture screenshot-ready output.

---

## 1. Project instructions to paste

In claude.ai → ADAM Pipeline project → Settings → "Add instructions to tailor Claude's responses" — append the following to whatever's already there:

```
DEMO MODE: When the operator's prompt begins with "DEMO:", produce only the
exact output requested. No preambles like "Let me", "I'll", or "I'm going to".
No trailing offers like "Want me to..." or "Should I...". No tool-call
narration. Use markdown tables when displaying tabular data. Keep responses
under 400 words unless explicitly asked for more. Render all data fields
in full — never truncate or use ellipses.
```

Save. The DEMO prefix triggers screenshot-ready formatting; non-DEMO prompts behave normally.

---

## 2. Pre-demo setup

1. Submit a fresh order via the form at `http://localhost:8000/order-form-local.html`
2. Note the sprint ID from the green success banner — call it `<NEW_SPRINT_ID>` below
3. Open the ADAM Pipeline project in claude.ai, start a new chat
4. Switch claude.ai to light mode if Friday is on a projector
5. Have Cmd+Shift+5 ready (or your screenshot tool of choice)

---

## 3. Prompt sequence

Replace `<NEW_SPRINT_ID>` with the actual sprint ID before pasting each prompt.

### Screenshot 1 — Recent sprints overview

```
DEMO: List the 3 most recent sprints in a markdown table with columns
sprint_id, driver, delivery_date, state, brief.
```

### Screenshot 2 — Order details accepted

```
DEMO: Show the full order details for sprint <NEW_SPRINT_ID>. Include
delivery date, driver, targeting, deliverable, platform, format, visual
styles, quantity, ratios, and brief. Format as a labeled list, one field
per line.
```

### Screenshot 3 — Pipeline executing copy generation

```
DEMO: Approve gate 2 for sprint <NEW_SPRINT_ID>. After approval, output
exactly two lines: the gate transition (gate 2 → awaiting_gate_3) and the
number of concepts generated.
```

### Screenshot 4 — Full copy review (the deliverable surface)

```
DEMO: Render the full copy_review for sprint <NEW_SPRINT_ID> as a markdown
table. Columns: rank, selected, score, headline, primary_text_short,
description, CTA. All 6 rows, no truncation.
```

### Screenshot 5 — Brand and legal audit (the gold frame)

```
DEMO: Audit the 6 concepts against the uploaded brand voice doc, legal
guidelines, marketing claims, and visual_style_copy_rules. For each
violation, give the concept rank, the exact phrase, the rule it violates,
and the source document. Format as a table. Skip clean concepts.
```

### Screenshot 6 — Pipeline running through to completion

```
DEMO: Approve gate 3 as-is. Continue through gates 4, 5, and 6. After each
gate, output one line: "Gate N → awaiting_gate_N+1" or "Gate 6 →
complete". No commentary.
```

### Screenshot 7 — Final asset manifest

```
DEMO: Render the full asset_manifest for sprint <NEW_SPRINT_ID> as a
markdown table. Columns: asset_id, concept_tag, headline, ratio,
figma_node_id, figma_asset_name. All rows, no truncation.
```

---

## 4. Tips

- **Take screenshots in one continuous chat session** so the demo flow is captured as a coherent thread (useful if you need to scroll back or rerecord).
- **Cmd+Shift+5 → "capture selected portion"** for tight crops without surrounding browser chrome.
- **If a screenshot is messy, re-paste the same prompt** and try again — the DEMO prefix produces consistent output, so a re-run looks identical.
- **The audit (Screenshot 5) is the strongest single frame.** It demonstrates AI doing meaningful quality work, not just text generation. Make sure that one is high resolution and readable when projected.
- **Run against a fresh sprint each time you rehearse.** Sprints accumulate quickly and the most recent one is what `list_sprints` will surface first.

---

## 5. Final video sequencing (Brandon's recording)

The seven screenshots above cover the upstream half. Brandon's recording covers the downstream half:

```
1. Form (Screenshot 1, 2)
   ↓
2. Chat driving the pipeline (Screenshot 3, 4)
   ↓
3. The audit (Screenshot 5) ← strongest single frame
   ↓
4. Manifest delivery (Screenshot 7)
   ↓
5. Brandon: Figma plugin loading the manifest
   ↓
6. Brandon: assembled ads appearing in the templates
   ↓
7. Brandon: 30s timelapse of polish
   ↓
8. Closing stat slide ("1 sprint, 9 ads, ~5 minutes of human time")
```
