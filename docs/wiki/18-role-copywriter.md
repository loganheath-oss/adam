# Role guide: Copywriter (running a sprint)

**Owner:** Adrie Etherington · **Last updated:** 2026-09-21

---

## What is ADAM?

ADAM turns a written brief into finished ad creative. It writes the copy and builds the ads against
Upwork's approved templates, stopping for a person at every step.

You are that person. This is the role that operates the tool.

### How the whole thing flows

```
Paid Acq submits the brief  →  YOU review the copy  →  ADAM generates the images
      →  Designer builds the ads in Figma  →  Paid Acq gets the finished ads
```

### Your role in it

| | |
|---|---|
| **What you get** | A submitted request with a brief, as a sprint link |
| **What you do** | Drive it through six checkpoints, and do the real work at the copy review |
| **What you hand off** | Approved copy and a manifest the designer can build from |
| **Who gets it next** | The designer, who assembles the ads in Figma |

**Time:** 20 to 40 minutes of attention per sprint, spread across the run. The machine work between
checkpoints takes minutes. Image generation is the slow leg.

---

## Before you start

- Access to the ADAM web app. [LINK: app URL]
- Access to the sprint you've been handed.
- The Slack channel where sprints are shared. [LINK: channel]
- Optional but useful: access to `/learnings` and `/quotes`, both editable in the app.

---

## Quick start: your first sprint

1. Open the sprint link. It's paused at **Gate 2**.
2. Check the brief came through and the styles match what was asked for. Approve.
3. Wait a few minutes. It pauses again at **Gate 3** with six copy concepts per style.
4. **Read them and decide what ships.** This is your job. Pick, edit, approve.
5. **Gate 4** shows image direction. Scan it, approve.
6. **Gate 5** shows the manifest. Check nothing says `pending_assembly`. Approve.
7. **Gate 6** is a final look. Approve, then hand the sprint to the designer.

You can do all of it by talking to the chat on the sprint page. "Show me gate 3." "Drop the second
Testimonial." "Approve."

---

## The six gates

Nothing advances until you approve it.

```
Order submitted → Gate 2 Order + refs → Gate 3 COPY → Gate 4 Image prompts
    → Gate 5 Assembly → Gate 6 Final QA → hand to designer
```

**Gate 3 is the main copy review step.** The others are confirmations. Gate 3 is where your craft
enters, and it's the last point where copy can change.

### Gate 2: Order and references

Check the brief came through intact and the styles are what was asked for. Nothing has been
generated and nothing has been spent.

Warnings you might see:

- *"Style X has no confirmed Figma template in the registry"* is usually noise. Those styles almost
  always assemble fine.
- *"Brief looks UNFILLED"* means somebody submitted the template text without filling it in. Go back
  to them. You'll get generic copy otherwise.

Approving here starts copy generation. **This is the first point that spends money.**

### Gate 3: Copy review

ADAM writes six concepts per style and pre-picks its best. You see all six.

For each selected concept you get the full field set: on-creative headline, long and short headline,
primary text long and short, description, CTA. On a "Both" order you get a separate block per
audience.

Read for what a machine can't judge. Is it on brief, is it interesting, would you run it.

**What ADAM already caught:**

- **Placeholder copy.** Concepts with literal stand-in text are auto-rejected and can't ship.
- **Legal and length problems.** Banned terms and over-cap headlines are pulled from selection.
- **ECHO.** A concept reusing another's idea or sentence frame is labelled. Still readable, just
  marked as a variant rather than a fresh idea.

**What you do:**

**Pick what ships.** Tell the chat in plain language. "Keep the top one per style." "Drop the second
Testimonial." Only what you select gets images and reaches Figma.

**Edit the copy.** For example:

> **You:** the Testimonial headline is too long, cut it to under 40 and keep the six weeks bit
> **ADAM:** Updated to "Six weeks of nothing, then a hire in six days" (46 → 44 characters).
> **You:** good, approve gate 3

It applies the change, stamps the concept as operator-edited, and moves on. If you don't name an
audience it updates both, which is usually what you want.

**File anything wrong.** Ask it to log an issue and it goes on the tracked list.

> **Copy freezes when you approve Gate 3.** Everything downstream is built from this text.

**Testimonials come from an approved list.** ADAM doesn't invent them. They're the quotes at
`/quotes`, editable in the app. Fix a stale quote there rather than in the concept, so the next
sprint inherits it.

### Gate 4: Image prompts

A scan, not a decision. Three kinds of rows, all normal:

- **A written prompt.** ADAM will generate this image.
- **A photo pick.** A real photo from the Upwork brand library. People photos always come from the
  library; ADAM never generates images of people.
- **"skip", with a reason.** The style's template brings its own artwork.

### Gate 5: Assembly

The manifest pairs copy with imagery, row by row.

| Status | Meaning |
|---|---|
| `delivered` | A finished file exists on the server |
| `ready_for_figma` | Normal for photo styles. The plugin places the photo inside Figma |
| `skipped` | The style uses its own template artwork. By design |
| `pending_assembly` | **A real gap.** Worth flagging |

Only the last one is a problem. If the manifest is completely empty, that's a defect. File it rather
than waiting, because nothing is still working in the background.

### Gate 6: Final QA, then hand off

Last look at the package.

**Then hand it to the designer.** Post the sprint link in the channel and say it's ready for
assembly. The designer needs the sprint's `asset_manifest.csv`, which they download from the sprint
page. [LINK: the handoff message to send]

### If a gate won't approve

If the sprint has open issue tickets, approval pauses and lists them. Either resolve them or say
explicitly that you want to proceed, and that acknowledgment is recorded. This exists so a defect
somebody flagged can't ship quietly.

---

## You're done when

- [ ] All six gates are approved
- [ ] Nothing in the manifest says `pending_assembly`
- [ ] The sprint link is posted for the designer
- [ ] Anything that looked wrong is logged as an issue, not just remembered

---

## When something breaks

**Start at `/admin/activity`.** Every error row has a **Diagnose** button that reads the error and
tells you the likely cause, the fix, and whether it needs an engineer. That one screen answers most
questions faster than reading anything else.

If you need more: `/admin` is the health overview, the sprint page has the error text and a
**Resume** button, and `/admin/issues` is what people have filed.

### Who fixes what

| You can fix | Send to the designer | Send to engineering |
|---|---|---|
| Copy that's off brief, wrong tone, too long | Ads with placeholder text still on them | A sprint that fails the same way twice |
| Which concepts ship | Copy landing in the wrong slot on the ad | "model not found" errors |
| A stale approved quote (`/quotes`) | Anything about how the ad looks | Anything needing a key or a deploy |
| Recurring copy problems (`/learnings`) | Missing or misnamed template layers | "No space left on device" |

### When to resume, log, or stop

- **Resume** when a sprint failed once and the error looks transient: a server restart, a state that
  says `interrupted`. It re-runs only the failed stage and keeps everything before it.
- **Log an issue** when something is wrong with the output but the sprint completed. That's the
  system of record and it's how patterns get spotted.
- **Stop and ask** when the same stage fails twice with the same error, when the manifest comes back
  empty, or when an error mentions billing, a model name, or disk space. Those aren't yours to fix
  and retrying won't help.

---

## How ADAM gets better over time

Two things change how ADAM writes, and you control both. Neither needs an engineer.

**Learnings, at `/learnings`.** Editable guidance ADAM reads on every run and every chat. "Stop
doing X, prefer Y" belongs here. It takes effect on the next run. Add one by asking the chat to
remember something, or by editing the page.

**The issue-to-learning loop.** When someone reports a copy problem in `/admin/issues`, hit
**"Distill into a learning"**. That appends your instruction to Learnings and marks the issue
learned. This is what stops the same complaint coming back every month.

**One limit.** Learnings shape how the assistant works with you and how it writes in conversation.
They don't change the per-ad-type structure: character caps, CTA policy and format rules live in a
config file that needs an engineer and a deploy. If you need a cap changed, that's a request, not a
learning.

Write preferences, not facts. Preferences stay true. Facts go stale and quietly mislead it.

### Two screens worth knowing

- **`/admin/spend`.** Tokens and cost by day, user and model, with month-to-date against budget.
  This is the screen to screenshot when someone asks what ADAM costs.
- **`/admin/digest`.** The whole period on one screen, with a plaintext block you can paste into
  Slack. Pull it weekly.

---

## Glossary

| Term | Meaning |
|---|---|
| **Sprint** | One run through ADAM |
| **Gate** | A checkpoint where you approve before it continues. There are six |
| **Concept** | One generated copy option. Six per style, you keep the best |
| **Visual style** | The ad type and layout, like Testimonial or Pie Chart |
| **Template** | The Figma frame a style is built from |
| **Assembly** | The designer's step, building the ads in Figma |
| **Manifest** | The file listing every ad, its copy and its image, handed to the designer |
| **Learning** | A standing instruction that changes how ADAM writes on every future run |
| **Issue** | A problem logged in the tool so it's tracked |

Fuller list in the [Glossary](13-glossary.md).

---

## Appendix: things that need an engineer

You won't do these, but recognising them saves a round trip.

- **"Your credit balance is too low", arriving as a 400.** Billing, not a bad request, despite the
  status code. Someone funds the account or swaps the key in Railway, then you resume from Gate 2.
- **"model not found", a 404 naming a model.** Anthropic retired an ID. One string, two-minute fix.
- **"No space left on device."** The sprint volume filled up. Someone prunes it, then you re-run
  from the gate.

Log any of these and say which sprint. Details are in [Fixing errors](16-fixing-errors.md).

---

## Who to ask

- **Copy rules, tone, approved claims** → the creative lead
- **Anything in Figma** → the designer
- **Keys, deploys, repeated failures** → engineering
- **Schedule and priorities** → the producer
