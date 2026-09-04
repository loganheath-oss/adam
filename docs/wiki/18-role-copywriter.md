# Role guide — Copywriter (running a sprint)

**Who this is for:** the person who takes a submitted request and drives it to finished copy and a
manifest the designer can assemble. This is the role that operates ADAM.

**Time:** roughly 20–40 minutes of attention per sprint, spread over the run. The machine work
between gates takes minutes; image generation is the slow leg.

---

## The shape of the job

A sprint moves through six checkpoints called **gates**. ADAM does the work between them and stops
at each one for you. Nothing advances without you approving it.

```
Order submitted → Gate 2 Order + refs → Gate 3 COPY → Gate 4 Image prompts
    → Gate 5 Assembly → Gate 6 Final QA → hand to designer
```

You can drive every gate from the **chat** on the sprint page — that is the intended way. Ask it to
show you what's in a gate, tell it what to change, approve when satisfied.

**Gate 3 is the gate that matters.** The rest are confirmations. Gate 3 is where your craft
enters, and it is the last point where copy can change.

---

## Gate 2 — Order and references

Check the brief came through intact and the styles are what was asked for. Nothing has been
generated yet and nothing has been spent.

**Warnings you may see, and what they mean:**

- *"Style X has no confirmed Figma template in the registry"* — usually noise. Those styles
  generally still assemble fine. Not a blocker.
- *"Brief looks UNFILLED"* — the requester submitted the template text without filling it in.
  Worth going back to them; you will get generic copy otherwise.

Approve to start copy generation. **This is the first point that spends money.**

---

## Gate 3 — Copy review (your gate)

ADAM writes **six concepts per style** and pre-selects its best. You see all six.

### What to look at

For every selected concept you get the full field set: on-creative headline, long and short
headline, primary text long and short, description, CTA. On a "Both" order you get a separate
block for Prospecting and Retargeting.

Read for the things a machine cannot judge: is this on-brief, is it interesting, would you run it.

### What ADAM has already caught for you

- **Placeholder copy** — concepts where the model emitted literal stand-in text are auto-rejected
  and can never ship.
- **Legal and length problems** — banned terms and over-cap headlines are removed from selection.
- **⚠ ECHO** — a concept reusing another's idea or sentence frame is labelled. It is still readable,
  it is just marked so you can see it is a variant rather than a fresh idea.

### What you can do here

**Pick which concepts ship.** Tell the chat in plain language — "keep the top one per style", "drop
the second Testimonial". Selections are saved and honoured downstream. Only selected concepts get
images and reach Figma.

**Edit the copy directly.** Tell it what to change ("shorten that headline", "change the CTA to
Get started") or paste in your own rewritten version and say "use this". It applies the change and
stamps the concept as operator-edited. Editing without naming an audience updates the base and both
audience versions, which is normally what you want; name an audience to change only one.

**File anything wrong.** Ask it to log an issue and it goes to the tracked list.

> **Copy freezes when you approve Gate 3.** Everything downstream is built from this text. If you
> want it different, change it now.

---

## Gate 4 — Image prompts

A scan, not a decision point. You are checking that the visual direction is sane.

Three kinds of rows, all normal:

- **A written prompt** — ADAM will generate this image.
- **A photo pick** — the ad uses a real photo from the Upwork brand library. People photos always
  come from the library; ADAM never generates images of people.
- **"skip", with a reason** — the style's template supplies its own artwork. Nothing is missing.

---

## Gate 5 — Assembly

The manifest is the row-by-row list pairing copy with imagery. **Statuses you will see:**

| Status | Meaning |
|---|---|
| `delivered` | A finished file exists on the server. |
| `ready_for_figma` | Normal for photo styles. The photo is placed inside Figma by the plugin, so no server file exists by design. |
| `skipped` | The style uses its own template artwork. By design. |
| `pending_assembly` | A real gap. Worth flagging. |

Only the last one is a problem. If the manifest is **completely empty**, that is a defect — file it
rather than waiting. There is no background process to wait for.

---

## Gate 6 — Final QA

Last look at the package before it is done. Then the designer assembles in Figma.

---

## If a gate refuses to approve

If the sprint has open issue tickets, approval pauses and lists them. Either resolve them or
explicitly confirm you want to proceed — that acknowledgment is recorded. This exists so a defect
you flagged cannot ship silently, which used to happen.

---

## Teaching ADAM between sprints

The **learnings** file is ADAM's memory across sprints. Ask it to remember something and it goes in
permanently; you can also edit the file directly at the `/learnings` page.

**Important limit:** learnings shape how the assistant *works with you* — what it shows, how it
behaves. They do **not** change the generated copy. Copy rules live in the reference docs, which
need an engineer to recompile. If you want copy itself to change, that is a request, not a
learning.

Write preferences, not facts. Preferences stay true; facts go stale and quietly mislead it.

---

## The short version

1. Gate 2, check the brief is real.
2. **Gate 3, do your actual job** — read all six per style, pick, edit, then approve knowing copy is now locked.
3. Gates 4 and 5, confirm nothing looks wrong, and know that `ready_for_figma` and `skipped` are normal.
4. Ask for about five ads per run. Quality drops past six.
