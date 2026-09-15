# Role guide: Engineer (inheriting and running ADAM)

**Who this is for:** whoever owns ADAM's code after Logan. The other three role guides cover the
people who use the tool. This one is for the person who keeps it working and extends it.

**Read [Handoff](14-handoff.md) first.** It lists the accounts and keys that have to move off
personal ownership, and those have external lead times. Everything on this page can be done later.
That list can't.

---

## What ADAM is, in one pass

A brief goes in, ad copy and assembled creatives come out.

- **Backend**, `main.py`, FastAPI on Railway. Serves the order form, the sprint dashboard, the chat,
  the admin surfaces, the in-tool wiki, and the plugin download. Pushing to `main` redeploys it.
- **Frontend**, `web/`, Next.js on Railway as a separate `adam-web` service.
- **Pipeline**, `pipeline/run_pipeline.py`. Six stages behind six human-approved gates.
- **Figma plugin**, `plugin/code.js`. Reads the manifest CSV the pipeline writes and assembles the
  finished ads.
- **MCP connector**, mounted in the backend at `/mcp`. This is how the copywriter drives gates from
  claude.ai.

A sprint lives in `runs/{sprint_id}/` on a Railway volume, and the run ends with an
`asset_manifest.csv` that the plugin consumes. That CSV is the contract between the two halves of
the system.

---

## Three things that will cost you a week if nobody tells you

### 1. The plugin cannot be tested by whoever changes it

Figma plugin code only runs in Figma desktop. You cannot run it, and neither could Logan. That is
not a minor inconvenience, it is the defining constraint of that file, and it has already shipped
false confidence twice.

The countermeasure is `scripts/verify_plugin_changes.py`. It replays the plugin's own lookup logic
in Python against live Figma JSON pulled from the REST API, and asserts the behaviour you intend
before you push. Run it, extend it, and put the output in your commit message.

```
railway run python3 scripts/verify_plugin_changes.py
```

When you change a lookup, add an assertion that the platform you did **not** mean to touch resolves
to the same node id as before. That specific check is what catches a Reddit change breaking Meta.

### 2. `run_pipeline.py` is the only canonical implementation

The numbered stage files, `02_copy_gen.py` through `06_deliver.py`, are a stale scaffold left from an
AWS design that was abandoned. They are stamped as non-canonical. Do not port to them, do not port
from them, and do not read them to understand current behaviour. `00_intake.py` is the exception:
it is live and load-bearing.

### 3. Reference data is compiled, not read

Edit the raw docs in `refs/`, then run `python3 pipeline/build_refs.py` to regenerate
`configs/refs_context.json`. Never hand-edit the compiled file. If someone says ADAM is ignoring a
brand rule, check whether the ref was edited without recompiling.

---

## Deploying

**Backend.** Push to `main` on `loganheath-oss/adam`. Railway auto-deploys. A failed build never
takes the site down, the previous deploy keeps serving.

Any dependency change in `pyproject.toml` must be followed by `uv lock`, with `uv.lock` committed.
The build runs `uv sync --locked` and fails on a mismatch.

**Frontend.** Does not auto-deploy. Deploy from an isolated copy of `web/`, never `railway up` from
the repo root, which would upload the whole repo as build context:

```
rsync -a --delete --exclude node_modules --exclude .next web/ /tmp/adam-web-deploy/
cd /tmp/adam-web-deploy && railway up --service adam-web --detach
```

**Plugin.** Not deployed. `PLUGIN_VERSION` at the top of `plugin/code.js` is the single source of
truth; the backend parses it out of that file to serve `/plugin/version` and `/plugin/download`.
Bump it in the same commit as any plugin change, or people will be running builds you can't
identify.

**Rolling back.** Railway dashboard, the service, Deployments, pick a known-good build, Redeploy.

---

## Where to look when something breaks

In this order. Most problems are a button or a text edit, not code.

1. **`/admin`.** Reliability dashboard. Completion rate, plus an incident list carrying the actual
   error for every failed run, and a health strip for volume, API and recent errors.
2. **`/admin/activity`.** Everything that happened, newest first, filterable. Every error row has a
   **Diagnose** button that reads the error against the runbook and tells you the likely cause. Use
   it before you read anything else.
3. **`/sprints/<id>`.** Exact state, error text, and a **Resume** button that re-runs only the failed
   stage.
4. **`/admin/issues`.** What people filed. Triage weekly.

`/admin/spend` and `/admin/digest` answer the cost and the weekly-summary questions.

### The failures you will actually meet

**"No space left on device."** The volume is 500 MB and fills with sprint images. Check
`/admin/storage`, prune at `/admin/prune`, re-run from the gate. **This is a recurring chore, not an
incident.** It is the single most likely thing to strand work while you are still learning the system.

**A 400 saying the credit balance is too low.** Billing, not a bad request, despite the status code.
Fund the account or swap the key in Railway, resume from Gate 2.

**A 404 naming a model.** Anthropic retired the ID. One string, two-minute fix.

**Ads assembling with placeholder text.** Almost always a Figma layer rename, not code. The plugin
log names the fields it could not place. That goes to the designer.

**A font that isn't installed.** Text silently kept its placeholder for a week because of this. The
plugin now falls back to the house font and says so, and preflights every font before building.

---

## Steering behaviour without touching code

Worth knowing so you don't take code tickets that aren't code tickets.

- **`/learnings`** is editable guidance the assistant reads on every run. Tone and working
  preferences belong here and take effect on the next run.
- **`/quotes`** holds the approved testimonials. Testimonial ads draw from it.
- **`configs/ad_type_style_guide.json`** holds per-ad-type structure: character caps, CTA policy,
  layout descriptions. This one **is** yours, it needs a push to take effect, and it is Adrie's
  content. Generate documentation from it rather than transcribing it, which is what
  `scripts/gen_adtype_field_reference.py` does.

---

## Hard constraints

These are not preferences. Two came from outside engineering.

- **No AI-generated photography of people.** Ratified by Upwork's Creative Director. People photos
  come from the tagged Figma library. Generation is fine for illustration, abstracts and backgrounds.
- **No native AWS.** No Lambdas, no RDS, no custom VPCs. Use platform modules or run it in the
  application container.
- **LLM traffic must route through Upwork's internal gateway in production.** Scaffolding exists
  behind `LLM_GATEWAY_*` env vars. The values do not exist yet and are owned by Haresh's team.

---

## The shape of the Figma contract

Worth understanding before you touch assembly, because it is the fragile part of the system.

The plugin matches templates **by name**, so layer names in a file that designers edit freely are
the contract. There are two naming conventions live at once:

- **Meta and most platforms**: `Adtype_<Style>` containers holding `Template_<Style>_<WxH>` frames.
- **Reddit**: `Reddit_Adtype_<Style>` containers whose size frames are named for their dimensions.

Each platform has one board master, matched on its whole name: `Meta - Static Grouped`,
`Reddit - Static Grouped`, and so on.

`tests/figma_template_lint.py` compares the live file against what the plugin expects. Run it after
any batch of template work.

```
railway run --service adam -- python3 tests/figma_template_lint.py
```

**This lint is currently run by a human who remembers to run it.** Surfacing it as a scheduled check
or a button in the admin app is the highest-leverage safeguard left undone, and it matters more once
there is no engineer watching.

---

## Testing

`tests/copy_regression.py` is the suite. It is offline and deterministic by default, and takes
seconds.

```
python3 tests/copy_regression.py            # offline, free
python3 tests/copy_regression.py --live     # runs a real generation, costs money
```

Run the offline suite before every push. The live mode spends real API budget, so treat it as a
deliberate act.

---

## The habit that matters most here

Much of this system's history is claims that turned out not to be true: a template audit that was
verified against a fixture missing the thing that broke, a structural check run against a superseded
copy of a file, a handoff page carrying a deadline that had passed six weeks earlier.

The pattern is always the same. Something was checked against a stand-in rather than against the
live thing.

So: check against the real file, name what you checked in the commit message, and mark anything you
could not verify as unverified rather than asserting it. The scripts in `scripts/` exist to make
that cheap. Every one of them prints the node ids it ran against, on purpose.

---

## Who to ask

- **Copy rules, tone, approved claims, character caps.** Adrie.
- **Figma templates and anything about how an ad looks.** Elise.
- **Schedule, priorities, change log.** Breanna.
- **Hosting, InfoSec, org-level access.** Leon.
- **LLM Gateway, production infrastructure, migration.** Haresh's team.
