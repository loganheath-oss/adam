# Role guide: Copywriter (running a sprint)

**Who this is for:** whoever takes a submitted request and drives it to finished copy and a manifest
the designer can assemble. This is the role that actually operates ADAM.

**Time:** 20 to 40 minutes of attention per sprint, spread across the run. The machine work between
gates takes minutes. Image generation is the slow leg.

---

## The shape of the job

A sprint moves through six checkpoints called gates. ADAM does the work in between and stops at each
one for you. Nothing moves forward until you approve it.

```
Order submitted → Gate 2 Order + refs → Gate 3 COPY → Gate 4 Image prompts
    → Gate 5 Assembly → Gate 6 Final QA → hand to designer
```

You can drive every gate from the chat on the sprint page, and that's how it's meant to work. Ask it
to show you what's in a gate, tell it what to change, approve when you're happy.

**Gate 3 is the one that matters.** The rest are confirmations. Gate 3 is where your craft goes in,
and it's the last point where copy can change.

---

## Gate 2: Order and references

Check the brief came through in one piece and the styles are what was asked for. Nothing's been
generated yet and nothing's been spent.

Warnings you might see:

- *"Style X has no confirmed Figma template in the registry"* is usually noise. Those styles almost
  always assemble fine. Not a blocker.
- *"Brief looks UNFILLED"* means somebody submitted the template text without filling it in. Go back
  to them. You'll get generic copy otherwise.

Approve and copy generation starts. **This is the first point that spends money.**

---

## Gate 3: Copy review

ADAM writes six concepts per style and pre picks its best. You see all six.

### What to look at

For every selected concept you get the whole field set: on creative headline, long and short
headline, primary text long and short, description, CTA. On a "Both" order you get a separate block
for Prospecting and Retargeting.

Read for the stuff a machine can't judge. Is it on brief, is it interesting, would you run it.

### What ADAM already caught

- **Placeholder copy.** Any concept where the model wrote literal stand in text gets auto rejected.
  It can't ship.
- **Legal and length problems.** Banned terms and over cap headlines get pulled out of selection.
- **ECHO.** A concept that reuses another one's idea or sentence frame gets labeled. It's still
  readable. It's just flagged so you can see it's a variant and not a fresh idea.

### What you can do here

**Pick what ships.** Tell the chat in plain language. "Keep the top one per style." "Drop the second
Testimonial." Your picks get saved and honored downstream. Only what you select gets images and
reaches Figma.

**Edit the copy.** Tell it what to change, like "shorten that headline" or "change the CTA to Get
started". Or paste in your own rewrite and say "use this". It applies the change and stamps the
concept as operator edited. If you don't name an audience it updates the base and both audience
versions, which is usually what you want. Name one to change only that one.

**File anything wrong.** Ask it to log an issue and it goes on the tracked list.

> **Copy freezes when you approve Gate 3.** Everything downstream gets built off this text. If you
> want it different, now's the time.

### Testimonial copy comes from an approved list

ADAM doesn't invent testimonials. They come from the approved quotes at **`/quotes`**, which you can
edit in the app. If a testimonial ad is pulling a quote that's stale or wrong, fix it there instead
of editing the concept. Then the next sprint gets the fix too.

---

## Gate 4: Image prompts

A scan, not a decision point. You're checking the visual direction makes sense.

Three kinds of rows, all normal:

- **A written prompt.** ADAM's going to generate this one.
- **A photo pick.** The ad uses a real photo out of the Upwork brand library. People photos always
  come from the library. ADAM never generates images of people.
- **"skip", with a reason.** That style's template brings its own artwork. Nothing's missing.

---

## Gate 5: Assembly

The manifest is the row by row list pairing copy with imagery. Statuses you'll see:

- **`delivered`.** There's a finished file on the server.
- **`ready_for_figma`.** Normal for photo styles. The plugin places the photo inside Figma, so
  there's no server file by design.
- **`skipped`.** The style uses its own template artwork. Also by design.
- **`pending_assembly`.** A real gap. Worth flagging.

Only the last one's a problem. If the manifest is completely empty, that's a defect. File it instead
of waiting, because there's no background process still working on it.

---

## Gate 6: Final QA

Last look at the package. Then it goes to the designer to assemble in Figma.

---

## If a gate won't approve

If the sprint has open issue tickets, approval pauses and lists them. Either resolve them or say
explicitly that you want to go ahead, and that acknowledgment gets recorded. This exists so a defect
somebody flagged can't ship quietly, which used to happen.

---

## When something goes wrong

ADAM is built to fail loudly and recover. Almost every problem shows up in one of four places, and
almost every fix is a button or a text edit rather than code.

### Where to look, in this order

1. **`/admin`, the reliability dashboard.** The headline view. What percent of runs are completing
   clean, plus an incident list with the actual error message for every failed run. Up top there's a
   health strip with three pills: volume, API and models, errors in the last 24 hours. If one's amber
   or red, start there. This is the first place to go when somebody says ADAM is broken.
2. **`/admin/activity`, the timeline.** Everything that happened, newest first. Orders, gate
   approvals, assemblies, edits, errors. You can filter by type, and there's an "Errors only" option.
   On any error row there's a **Diagnose** button that reads the error against the runbook and tells
   you the likely cause, the fix, and whether it needs an engineer. **Use this before you read
   anything else.** It's the fastest way to triage.
3. **The sprint page, `/sprints/<id>`.** Shows the exact state, the error text, and a Resume button.
4. **`/admin/issues`.** Where anybody files "something looked wrong." Triage it weekly. Anything open
   more than a week gets flagged so it doesn't rot.

### What usually goes wrong

**A sprint failed or is stuck.** Far and away the most common one. Open the sprint page, read the
error, hit **Resume**. It re runs just the failed stage and keeps everything before it. If the state
says `interrupted` or mentions a server restart, that's a redeploy that landed mid run and nothing's
lost. Just resume. If the same stage fails twice the same way, check it against the list below.

**"No space left on device."** The storage volume is 500 MB and it fills up with sprint images, and
then runs die in the middle of the image stage. This has bitten us in production. Look at
**`/admin/storage`** for per sprint sizes, largest first, then prune old and errored sprints at
**`/admin/prune`**, which needs the API key. Keep anything the team still needs, then re run the
failed sprint from its gate.

**"Your credit balance is too low," coming back as a 400.** It's a 400, not a 401, so it looks like a
bad request when it's really billing. Fund the Anthropic account or drop a funded key into Railway
under the `adam` service variables, then resume from Gate 2.

**"model not found," a 404 with a model name in it.** Anthropic retires model IDs. This one is a code
change, but a tiny one, just a string. File it in `/admin/issues` and the change log. It's a two
minute fix for any engineer.

**Ads in Figma come out with placeholder text, or copy in the wrong slot.** The plugin fills copy
into named layers, so if a template's text layers got renamed in Figma the plugin can't find them and
leaves the placeholder sitting there. That's a designer fix, not a copy fix. The plugin log names
exactly which fields it couldn't place and on which style. Send that to Elise.

**Copy quality is off.** Tone, format, structure. That's steering, not a bug. See below.

---

## Steering the copy without an engineer

Two things change how ADAM writes and you control both.

**Learnings, at `/learnings`.** Editable guidance ADAM reads on every run and every chat. "Stop doing
X, prefer Y" goes here. It takes effect on the next run. Add one by asking the chat to remember
something, or just edit the page.

**The issue to learning loop.** When somebody reports a copy problem in `/admin/issues`, hit
**"Distill into a learning"** on it. That appends your instruction to Learnings and marks the issue
learned. This is the self serve fix for a recurring copy problem, and it's what stops the same
complaint coming back every month.

One limit worth knowing. Learnings shape how the assistant works with you and how it writes in
conversation. They don't change the per ad type structure. Character caps, CTA policy, the format
rules for each ad type, all of that lives in a config file an engineer has to change and redeploy. So
if you need a cap or an ad type's structure changed, that's a request, not a learning. Log it.

Write preferences, not facts. Preferences stay true. Facts go stale and quietly mislead it.

---

## Two more screens worth knowing

- **`/admin/spend`.** Rough tokens and cost by day, user and model, with month to date against budget
  and a projection for the end of the month. Screenshot this when somebody asks what ADAM costs.
- **`/admin/digest`.** The whole period on one screen. Runs, assemblies, issues, errors, spend,
  deploys, plus a plaintext block you can paste straight into Slack or the change log. Pull it weekly.

---

## When you can't fix it

1. **File it in `/admin/issues`** with the sprint ID and what you expected against what you got.
   That's the system of record.
2. **Add it to the change log.**
3. **Route it.** Template and visual problems go to Elise. Copy rules, tone and approved claims go to
   Adrie. Infrastructure and hosting go to Haresh's team.

---

## The short version

1. Gate 2, check the brief is real.
2. Gate 3, do your actual job. Read all six per style, pick, edit, then approve knowing the copy is
   locked after that.
3. Gates 4 and 5, confirm nothing looks wrong, and remember `ready_for_figma` and `skipped` are both
   normal.
4. When something breaks, go to `/admin/activity` and hit Diagnose first.
5. Recurring copy complaints belong in Learnings, not in another brief.
6. Ask for about five ads a run. Quality drops past six.
