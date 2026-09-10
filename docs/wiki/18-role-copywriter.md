# Role guide: Copywriter (running a sprint)

**Who this is for:** the person who takes a submitted request and drives it to finished copy and a
manifest the designer can assemble. This is the role that operates ADAM.

**Time:** roughly 20 to 40 minutes of attention per sprint, spread over the run. The machine work
between gates takes minutes; image generation is the slow leg.

---

## The shape of the job

A sprint moves through six checkpoints called **gates**. ADAM does the work between them and stops
at each one for you. Nothing advances without you approving it.

```
Order submitted → Gate 2 Order + refs → Gate 3 COPY → Gate 4 Image prompts
    → Gate 5 Assembly → Gate 6 Final QA → hand to designer
```

You can drive every gate from the **chat** on the sprint page, which is the intended way. Ask it to
show you what's in a gate, tell it what to change, approve when satisfied.

**Gate 3 is the gate that matters.** The rest are confirmations. Gate 3 is where your craft
enters, and it is the last point where copy can change.

---

## Gate 2: Order and references

Check the brief came through intact and the styles are what was asked for. Nothing has been
generated yet and nothing has been spent.

**Warnings you may see, and what they mean:**

- *"Style X has no confirmed Figma template in the registry"* is usually noise. Those styles
  generally still assemble fine. Not a blocker.
- *"Brief looks UNFILLED"* means the requester submitted the template text without filling it in.
  Worth going back to them; you will get generic copy otherwise.

Approve to start copy generation. **This is the first point that spends money.**

---

## Gate 3: Copy review (your gate)

ADAM writes **six concepts per style** and pre-selects its best. You see all six.

### What to look at

For every selected concept you get the full field set: on-creative headline, long and short
headline, primary text long and short, description, CTA. On a "Both" order you get a separate
block for Prospecting and Retargeting.

Read for the things a machine cannot judge: is this on-brief, is it interesting, would you run it.

### What ADAM has already caught for you

- **Placeholder copy.** Concepts where the model emitted literal stand-in text are auto-rejected
  and can never ship.
- **Legal and length problems.** Banned terms and over-cap headlines are removed from selection.
- **ECHO.** A concept reusing another's idea or sentence frame is labeled. It is still readable,
  it is just marked so you can see it is a variant rather than a fresh idea.

### What you can do here

**Pick which concepts ship.** Tell the chat in plain language: "keep the top one per style", "drop
the second Testimonial". Selections are saved and honored downstream. Only selected concepts get
images and reach Figma.

**Edit the copy directly.** Tell it what to change ("shorten that headline", "change the CTA to
Get started") or paste in your own rewritten version and say "use this". It applies the change and
stamps the concept as operator-edited. Editing without naming an audience updates the base and both
audience versions, which is normally what you want; name an audience to change only one.

**File anything wrong.** Ask it to log an issue and it goes to the tracked list.

> **Copy freezes when you approve Gate 3.** Everything downstream is built from this text. If you
> want it different, change it now.

### Testimonial ads pull from an approved list

Testimonial copy is not invented. It comes from the approved quotes held at the **`/quotes`** page,
which is editable in the app. If a testimonial ad is drawing on a quote that is stale or wrong, fix
it there rather than editing the concept, so the next sprint inherits the correction.

---

## Gate 4: Image prompts

A scan, not a decision point. You are checking that the visual direction is sane.

Three kinds of rows, all normal:

- **A written prompt.** ADAM will generate this image.
- **A photo pick.** The ad uses a real photo from the Upwork brand library. People photos always
  come from the library; ADAM never generates images of people.
- **"skip", with a reason.** The style's template supplies its own artwork. Nothing is missing.

---

## Gate 5: Assembly

The manifest is the row-by-row list pairing copy with imagery. **Statuses you will see:**

- **`delivered`.** A finished file exists on the server.
- **`ready_for_figma`.** Normal for photo styles. The photo is placed inside Figma by the plugin, so
  no server file exists by design.
- **`skipped`.** The style uses its own template artwork. By design.
- **`pending_assembly`.** A real gap. Worth flagging.

Only the last one is a problem. If the manifest is **completely empty**, that is a defect. File it
rather than waiting. There is no background process to wait for.

---

## Gate 6: Final QA

Last look at the package before it is done. Then the designer assembles in Figma.

---

## If a gate refuses to approve

If the sprint has open issue tickets, approval pauses and lists them. Either resolve them or
explicitly confirm you want to proceed. That acknowledgment is recorded. This exists so a defect
you flagged cannot ship silently, which used to happen.

---

## When something goes wrong

ADAM is built to fail loudly and recoverably. Almost every problem shows up in one of four places,
and almost every fix is a button or a text edit rather than code.

### Where to look, in this order

1. **`/admin`, the reliability dashboard.** The headline view. Percentage of runs completing clean,
   plus an incident list carrying **the actual error message** for every failed run. At the top is a
   health strip of three pills: volume percentage, API and models, errors in the last 24 hours. If a
   pill is amber or red, that is your first clue. **Start here when someone says ADAM is broken.**
2. **`/admin/activity`, the timeline.** Everything that happened, newest first: orders, gate
   approvals, assemblies, edits, errors. Filter by type (there is an "Errors only" option), user, or
   sprint. On any error row there is a **Diagnose** button, which analyzes that error against the
   runbook and hands back the likely cause, the fix, and whether it needs an engineer. **This is the
   fastest way to triage.** Use it before reading further.
3. **The sprint's own page, `/sprints/<id>`.** Shows the exact state (`awaiting_gate_3`, `error`,
   `interrupted`), the error text, and a **Resume** button.
4. **`/admin/issues`, the issues queue.** Where anyone files "something looked wrong". Triage weekly.
   Open issues older than a week get flagged so nothing rots.

### The problems you are most likely to hit

**A sprint failed or is stuck.** The most common situation by far. Open the sprint page, read the
error, click **Resume**. It re-runs only the failed stage and keeps all prior work. If the state says
`interrupted` or mentions a server restart, a redeploy happened mid-run and nothing is lost. Just
resume. If the same stage fails twice with the same error, match it against the cases below.

**"No space left on device" (ENOSPC).** The storage volume is 500 MB and fills up with sprint images,
after which runs die mid-image-stage. This has bitten us in production. Check usage at
**`/admin/storage`**, which lists per-sprint sizes largest first, then prune old and errored sprints
via **`/admin/prune`** (needs the API key). Keep anything the team still needs, then re-run the failed
sprint from its gate.

**"Your credit balance is too low", as an HTTP 400.** Copy generation returns a 400, not a 401, so it
looks like a bad request when it is actually billing. Fund the Anthropic account or set a funded key
in Railway under the `adam` service variables, then resume from Gate 2.

**"model not found", a 404 naming a model string.** Anthropic retires model IDs. This one genuinely
is a code change, but a tiny one: a single string. File it in `/admin/issues` and the change log. Any
engineer fixes it in two minutes.

**Ads in Figma show placeholder text, or copy lands in the wrong slot.** The plugin fills copy into
named layers, so if a template's text layers were renamed in Figma the plugin cannot find them and
leaves the placeholder. This is a designer fix, not a copy fix. The plugin log names exactly which
fields it could not place and on which style. Send that to Elise.

**Copy quality is off in tone, format, or structure.** This is steering, not a bug, and neither lever
needs code. See the next section.

---

## Steering the copy without an engineer

Two things change how ADAM writes, and you control both.

**Learnings, at `/learnings`.** Editable guidance ADAM reads on every run and every chat. "Stop doing
X, prefer Y" belongs here. It takes effect on the next run. You can add one by asking the chat to
remember something, or by editing the page directly.

**The issue to learning loop.** When someone reports a copy problem in `/admin/issues`, use
**"Distill into a learning"** on that issue. It appends your instruction to Learnings and marks the
issue as learned. This is the intended self-serve fix for a recurring copy problem, and it is the
mechanism that stops the same complaint coming back every month.

**One important limit.** Learnings shape how the assistant works with you and how it writes in
conversation. Per-ad-type structure, meaning character caps, CTA policy and the format rules for each
ad type, lives in a configuration file that needs an engineer to change and redeploy. If you need a
character cap or an ad type's structure changed, that is a request, not a learning. Log it.

Write preferences, not facts. Preferences stay true; facts go stale and quietly mislead it.

---

## Two admin screens worth knowing

- **`/admin/spend`.** Approximate tokens and cost by day, user and model, with month-to-date against
  budget and an end-of-month projection. This is the screen to screenshot when someone asks what ADAM
  costs.
- **`/admin/digest`.** The whole period on one screen (runs, assemblies, issues, errors, spend,
  deploys) with a plaintext block you can paste straight into Slack or the change log. Pull it weekly.

---

## When you cannot fix it

1. **File it in `/admin/issues`** with the sprint ID and what you expected versus what you got. This
   is the system of record.
2. **Add it to the change log.**
3. **Route it.** Template and visual problems go to Elise. Copy rules, tone and approved claims go to
   Adrie. Infrastructure and hosting go to Haresh's team.

---

## The short version

1. Gate 2, check the brief is real.
2. **Gate 3, do your actual job.** Read all six per style, pick, edit, then approve knowing copy is now locked.
3. Gates 4 and 5, confirm nothing looks wrong, and know that `ready_for_figma` and `skipped` are normal.
4. When something breaks, go to `/admin/activity` and hit **Diagnose** before anything else.
5. Recurring copy complaints belong in Learnings, not in a re-brief.
6. Ask for about five ads per run. Quality drops past six.
