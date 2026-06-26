# What is ADAM

## In one sentence
ADAM turns a **creative brief** into **production-ready Upwork ads** — AI writes the copy, pulls or
generates the imagery, and a Figma plugin assembles finished creatives across every required size and
visual style.

## The problem it solves
Upwork's Paid Acquisition team manually concepted copy and hand-assembled static ads in Figma for every
batch — slow, repetitive, and hard to scale across the many platforms/sizes/styles each campaign needs.
ADAM automates the repetitive middle (concepting → copy → assembly) while keeping **humans in control at
gates**.

## Who it's for
- **Operators / creative producers** — submit orders, review and approve at each gate, hand finals to the Paid Acq team.
- **Creative leads (copy/brand)** — tune the brand voice, reference docs, and approved claims that steer the AI.
- **Designers** — own the Figma templates + tagged photo library the plugin assembles into.
- **The future maintainers at Upwork** — inherit and run all of the above after the build contract ends.

## The shape of the system (90-second tour)
1. **Order** — someone fills the order form (platform, format, sizes, visual styles, brief).
2. **Copy generation** — Claude writes multiple concepts per style, self-scores, picks the best.
3. **Imagery** — either a Gemini-generated illustration/abstract, or a **rights-cleared photo pulled from
   Upwork's tagged Figma library** (no AI photos of people — a hard rule).
4. **Assembly** — the Figma plugin clones the right template per row and fills copy + image into named layers.
5. **Delivery** — assembled creatives go to the Paid Acq team.

Between each major step is a **human gate** (approve / edit / reject). See [The pipeline](04-the-pipeline.md).

## What makes it "ADAM" and not just a script
- It applies **layered judgment**: hard rules set the boundaries (brand, legal, rights), the AI makes the
  judgment calls inside them, humans veto at gates.
- It has **institutional memory** ([`learnings.md`](../../learnings.md)) the AI reads every session.
- It has an **in-app assistant** that can inspect any sprint and answer questions — the seed of the
  "ask the tool anything" handoff goal.

## Current status
See the [status table on the Home page](README.md#-status-at-a-glance). Short version: the machinery is
built and the plugin recognizes all 21 templates; the only thing gating live unique output is a **funded
Anthropic key**.

## The vision for handoff
A new Upwork owner should be able to: run a batch end-to-end, edit the brand refs, add a new template/style,
redeploy, and — when stuck — **ask ADAM's own chat** and get a correct, grounded answer. This wiki exists to
make that true.
