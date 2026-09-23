# Role guide: Engineer (inheriting and running ADAM)

**Owner:** the engineer who holds ADAM · **Last updated:** 2026-09-21

---

## What is ADAM?

A brief goes in, ad copy and assembled creatives come out. The other three guides cover the people
who use it. This one is for whoever keeps it working and extends it.

```
Paid Acq submits the brief  →  Copywriter reviews the copy  →  ADAM generates the images
      →  Designer builds the ads in Figma  →  Paid Acq gets the finished ads
```

### Your role in it

| | |
|---|---|
| **What you get** | A running system with six human checkpoints and a Figma plugin |
| **What you do** | Keep it working, fix what breaks, extend it when asked |
| **What you hand off** | Nothing routine. You're the backstop |
| **Who comes to you** | The copywriter for failures, the designer for anything needing a deploy |

**Read [Handoff](14-handoff.md) alongside this.** It lists the accounts and keys that still have to
move, and the migration timeline.

---

## Day 1

Work through this in order. It takes an afternoon and it ends with you having run the whole thing
once.

### 1. Get access

| What | Why you need it |
|---|---|
| **GitHub** repo — `loganheath-oss/adam` (https://github.com/loganheath-oss/adam) | The canonical source. The backend auto-deploys from `main` |
| **Railway** project `angelic-liberation`, service `adam` (https://railway.app) | Hosts both services, holds the env vars and the sprint volume |
| **Figma** file `DoDwumxELkuAuKKSP5p00e` — "ADAM 2026" (https://www.figma.com/design/DoDwumxELkuAuKKSP5p00e/ADAM-2026), edit access | The templates, and every audit script reads it |
| **Anthropic API key** | Copy generation and the in-app chat |
| **Gemini API key** | Image generation |
| **Figma access token** | Library photo lookup and the checker scripts |
| **Claude Max / Enterprise** with connector rights | The MCP connector the copywriter drives gates through |
| Production URLs | App https://adam-production-9618.up.railway.app · Dashboard https://adam-production-9618.up.railway.app/admin/dashboard |

### 2. Set up locally

```
git clone https://github.com/loganheath-oss/adam.git
cd adam
python3 -m venv .venv && source .venv/bin/activate
pip install -r mcp_server/requirements.txt
cp .env.example .env        # then fill it in
```

Run everything through `railway run` rather than pasting keys into your shell. It injects the
service env, so you never handle a key directly.

### 3. Prove it works

Six checks. If all six pass, you have a working system and you can change things with confidence.

- [ ] **The site loads.** Open the app URL, the order form renders.
- [ ] **Admin is healthy.** `/admin/dashboard` shows the health strip with no red pills.
- [ ] **Tests pass.** `python3 tests/copy_regression.py`, offline, free, seconds.
- [ ] **Plugin version is current.** `/plugin/version` matches `PLUGIN_VERSION` in `plugin/code.js`.
- [ ] **The Figma check passes.** `railway run --service adam -- python3 tests/figma_template_lint.py`
- [ ] **A test sprint runs.** `railway run python3 pipeline/run_pipeline.py --test`, then drive it
      through the gates. Use skip-image styles (Pie Chart, Us vs Them, Text Only) so it costs almost
      nothing.

---

## Which files are current

This matters more than usual here, because the repo carries a dead scaffold.

| Path | Status |
|---|---|
| `pipeline/run_pipeline.py` | **Canonical.** The only real implementation |
| `pipeline/00_intake.py` | **Live.** Load-bearing |
| `pipeline/02_copy_gen.py` through `06_deliver.py` | **DEAD.** A stale AWS-era scaffold. Do not read these to understand behaviour, do not port to or from them |
| `mindstudio/` | **DEAD.** Historical only |
| `main.py` | Current. FastAPI backend |
| `web/` | Current. Next.js frontend |
| `plugin/code.js` | Current. The Figma plugin |
| `scripts/` | Current. Audit and verification tooling |

---

## Three things that will cost you a week

### 1. The plugin cannot be tested by whoever changes it

Figma plugin code only runs in Figma desktop. You cannot run it. This is the defining constraint of
that file and it has already shipped false confidence twice.

The countermeasure is `scripts/verify_plugin_changes.py`, which replays the plugin's own lookup
logic in Python against live Figma JSON and asserts the behaviour you intend, before you push.

```
railway run python3 scripts/verify_plugin_changes.py
```

When you change a lookup, add an assertion that the platform you did **not** mean to touch still
resolves to the same node id. That check is what catches a Reddit change breaking Meta.

The scripts talk to the Figma REST API (reference: https://www.figma.com/developers/api). Two traps
that cost real time, both already handled in the scripts and worth knowing before you write a new
one: a whole-file `GET /v1/files/{key}` on ADAM 2026 answers **403** because the document is too
large, so read it a page at a time via `?depth=1` then `/nodes?ids=`; and Figma's edge answers 403
to urllib's default User-Agent, which reads exactly like an auth failure and sends you off
investigating the token.

### 2. Reference data is compiled, not read

Edit the raw docs in `refs/`, then run `python3 pipeline/build_refs.py` to regenerate
`configs/refs_context.json`. Never hand-edit the compiled file. If someone says ADAM is ignoring a
brand rule, check whether a ref was edited without recompiling.

### 3. The schema wins over the prompt

Copy generation is constrained by a JSON schema built from `_BASE_FIELDS`. Telling the prompt not to
produce a field while the schema still requires it produces the field anyway. That exact mistake
shipped once. If you change what copy comes out, change the schema.

---

## Deploy and rollback cheat sheet

| Task | Command |
|---|---|
| **Deploy backend** | `git push` to `main`. Railway auto-deploys |
| **After any dependency change** | `uv lock`, commit `uv.lock`. The build runs `uv sync --locked` and fails on a mismatch |
| **Deploy frontend** | `rsync -a --delete --exclude node_modules --exclude .next web/ /tmp/adam-web-deploy/` then `cd /tmp/adam-web-deploy && railway up --service adam-web --detach` |
| **Never** | `railway up` from the repo root. It uploads the whole repo as build context |
| **Plugin** | Not deployed. Bump `PLUGIN_VERSION` in `plugin/code.js` in the same commit as any plugin change |
| **Roll back** | Railway dashboard → service → Deployments → pick a good build → Redeploy |

A failed build never takes the site down. The previous deploy keeps serving.

---

## Making a change safely

- [ ] Offline tests pass before you start, so you know the baseline is green
- [ ] If it touches the plugin, extend `verify_plugin_changes.py` and run it
- [ ] If it touches copy generation, check the **schema**, not just the prompt
- [ ] If it touches one platform, assert the others are unchanged
- [ ] Bump `PLUGIN_VERSION` if you touched `plugin/`
- [ ] `uv lock` if you touched dependencies
- [ ] Say in the commit message what you actually verified, and against what
- [ ] Offline tests pass again

---

## Where to look when something breaks

In this order. Most problems are a button or a text edit, not code.

1. **`/admin/dashboard`.** Completion rate, an incident list with the real error per failed run, and a health
   strip for volume, API and recent errors.
2. **`/admin/activity`.** Everything that happened, newest first. Every error row has a **Diagnose**
   button that reads the error against the runbook. Use it first.
3. **`/sprints/<id>`.** Exact state, error text, and a **Resume** that re-runs only the failed stage.
4. **`/admin/issues`.** What people filed.

### The failures you will actually meet

**"No space left on device."** The sprint volume is 500 MB and fills with images. Check
`/admin/storage`, prune at `/admin/prune`, re-run from the gate. **A recurring chore, not an
incident**, and the most likely thing to strand work while you're still learning.

**A 400 saying the credit balance is too low.** Billing, not a bad request. Fund or swap the key,
resume from Gate 2.

**A 404 naming a model.** Anthropic retired the ID. One string.

**Ads assembling with placeholder text.** Almost always a Figma layer rename. The plugin log names
the fields it couldn't place. That's the designer's.

**A font that isn't installed.** Text silently kept its placeholder for a week because of this. The
plugin now falls back to the house font and preflights every font before building.

---

## Not finished yet

Be loud about these. They are not bugs, they are unbuilt.

> ### ⚠ LLM Gateway is NOT wired up
> Production requires all LLM traffic to route through Upwork's internal gateway. Scaffolding exists
> behind `LLM_GATEWAY_*` env vars. **The endpoint, key and model values do not exist yet** and are
> owned by Upwork engineering. Until they land, the pipeline calls Anthropic and Gemini directly,
> which is fine for now and not acceptable for production.

> ### ⚠ Delivery has never run
> `GOOGLE_SERVICE_ACCOUNT_JSON` is unset, so the Drive upload stage has never executed once.

> ### ⚠ OAuth on the MCP connector
> The connector authenticates with a bearer token baked into its URL. Real OAuth is pre-production
> hardening.

> ### ⚠ Sprint state lives on a disk
> `/data/runs` on a Railway volume, not a database. It survives redeploys and it fills up.

---

## Hard constraints

Not preferences. Two came from outside engineering.

- **No AI-generated photography of people.** Ratified by Upwork's Creative Director. People photos
  come from the tagged Figma library. Generation is fine for illustration, abstracts, backgrounds.
- **No native AWS.** No Lambdas, RDS or custom VPCs. Use platform modules or the app container.
- **LLM traffic routes through the internal gateway in production.** See above.

---

## The Figma contract

The fragile part of the system. The plugin matches templates **by name**, so layer names in a file
designers edit freely are the contract. Two conventions are live:

- **Meta and most platforms:** `Adtype_<Style>` containers holding `Template_<Style>_<WxH>` frames.
- **Reddit:** `Reddit_Adtype_<Style>` containers whose size frames are named for their dimensions.

One board master per platform, matched on the whole name: `Meta - Static Grouped`,
`Reddit - Static Grouped`, and so on.

Two generated reports, both regenerated from the live file:

- `docs/figma-punchlist.md`, open template defects, with a link per node.
- `docs/adtype-field-reference.md`, which copy fields each ad type carries.

**`tests/figma_template_lint.py` is currently run by a human who remembers to run it.** Surfacing it
as a scheduled check or a button in the admin app is the highest-leverage safeguard left undone.

---

## Glossary

| Term | Meaning |
|---|---|
| **Sprint** | One pipeline run. State in `runs/{sprint_id}/` |
| **Gate** | A human approval checkpoint. Six of them |
| **Manifest** | `asset_manifest.csv`, the handoff from pipeline to Figma plugin |
| **Concept** | One generated copy option. Six per style |
| **Template** | A Figma frame the plugin clones for a style |
| **Assembly** | The plugin run that builds finished ads |
| **Learning** | Editable guidance the assistant reads every run |
| **Issue** | A tracked problem logged in the app |

Fuller list in the [Glossary](13-glossary.md).

---

## The habit that matters most here

Much of this system's history is claims that turned out not to be true. A template audit verified
against a fixture missing the thing that broke. A structural check run against a superseded copy of
a file. A handoff page carrying a deadline that had passed six weeks earlier.

The pattern is always the same: something checked against a stand-in rather than the live thing.

Check against the real file, name what you checked in the commit message, and mark anything you
couldn't verify as unverified rather than asserting it. The scripts in `scripts/` print the node ids
they ran against, on purpose.

---

## Who to ask

- **Copy rules, character caps, approved claims** → the creative lead
- **Figma templates and how an ad looks** → the designer
- **Schedule and priorities** → the producer
- **Hosting, InfoSec, org-level access** → the Upwork sponsor
- **LLM Gateway, production infrastructure, migration** → Upwork engineering

Names and current holders are in [Handoff](14-handoff.md), kept in one place so this guide doesn't
go stale when people change.
