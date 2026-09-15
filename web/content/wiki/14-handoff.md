# Handoff

**Last verified 2026-09-15.** Every status line below says how it was checked. Anything that could
not be checked from the repo, the Railway environment, or the Figma API is marked
**UNVERIFIED** rather than asserted. The previous version of this page carried a deadline of
"before August" that had been blown by six weeks without anyone noticing, so the rule here is that
a claim without a source does not belong on this page.

The goal is unchanged: a new Upwork owner can run, edit, extend and operate ADAM, and when stuck
can ask ADAM's own chat and get a grounded answer.

**Inheriting engineer:** Max Karasso. **Logan's contract ends 2026-09-30**, which from today is
**12 working days**.

---

## Read this first

The wiki's knowledge is portable. Nothing here needs Logan's laptop, and the local `~/...` paths in
the runbooks are just one clone of the repo.

What the *running system* depends on is a short list of accounts and keys currently held by Logan or
CM. **Every one of these has a third-party lead time, and none of them can be done after Logan's
access ends.** They are the only items on this page that are genuinely unrecoverable, so they go
first.

---

## Ownership that must transfer

| Asset | Held by today | What it powers | How this was verified |
|---|---|---|---|
| GitHub repo `loganheath-oss/adam` | Logan's personal GitHub | Canonical source. Railway deploys from it | `git remote -v`, 2026-09-15 |
| Railway project `angelic-liberation` (service `adam`) | Workspace **"loganheath-oss's Projects"**, a personal workspace | Hosts the live tool, its env vars, and the sprint volume | `railway status`, 2026-09-15 |
| **MCP connector registration** | **Logan's personal Claude Max account** | Adrie's entire gate-driving workflow from claude.ai | CLAUDE.md §4. Upwork is on Anthropic Enterprise but Logan's role cannot add connectors, so org registration needs an admin escalation |
| `ANTHROPIC_API_KEY` | Funded account on Railway | Copy generation and Ask ADAM chat | Present on the service, 2026-09-15 |
| `GEMINI_API_KEY` | Current account | Image generation (stage 04) | Present on the service |
| `FIGMA_ACCESS_TOKEN` | **Logan's personal token** | Library photo lookup, the template lint, every audit script | Present on the service. The Figma *file* is already Upwork-owned; the token is not |
| `PIPELINE_API_KEY` | Set | Login for `/sync-log`, `/learnings`, sprint admin | Present on the service. **This was outstanding in the June version of this page and is now done** |
| `MCP_AUTH_TOKEN` | Set | Auth for the `/mcp` connector | Present on the service |
| `DATABASE_URL` | Railway Postgres | Usage, reliability and spend dashboards | Present on the service |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | **Not set** | Delivery stage (Drive upload) | Confirmed absent, 2026-09-15. Delivery has never run |
| Drive folders (Brand / Sprints / Approved) | Logan's Google account | Sprint inputs and outputs | UNVERIFIED, folder IDs are in `configs/upwork_config.json` |
| Adrie's Claude Project | Adrie | Copy-prompt tuning | Person-owned. UNVERIFIED whether it still matters now that refs are compiled |

Everything else, meaning the code, the wiki, the Figma file and the live URL, is usable as-is.

---

## The failure mode that will happen while you are learning the system

**The sprint volume is 500 MB and it fills up.** Sprint images accumulate, and when it fills, runs
die in the middle of the image stage with "No space left on device". This has already happened in
production.

It is not a rare event, it is a periodic chore, and nobody outside this page knows to do it:

1. `GET /admin/storage` lists per-sprint sizes, largest first.
2. `POST /admin/prune` deletes old and errored sprints. Needs the API key.
3. Re-run the failed sprint from its gate.

Full runbook in [Fixing errors](16-fixing-errors.md). **Whoever inherits Railway inherits this
chore.** If nobody has the Railway project, nobody can do it, and sprints stay stranded.

---

## What is actually done

Verified against the repo and the live Figma file on 2026-09-15:

- Pipeline runs end to end through all six gates.
- Web app (order form, dashboard, chat) deployed on Railway, with the `/mcp` connector mounted in it.
- Admin surfaces live: `/admin`, `/admin/activity` with per-error **Diagnose**, `/admin/issues`,
  `/admin/spend`, `/admin/digest`, `/admin/storage`, `/admin/prune`.
- In-tool wiki with wiki-aware Ask ADAM chat and clickable sources.
- **Meta**: 21 templates recognized and assembling.
- **Reddit**: 20 ad types with platform-aware copy rules, caps enforced hard, and as of plugin
  **2026.09.16** the plugin resolves Reddit templates and Reddit's own board master. Proven
  statically by `scripts/verify_plugin_changes.py` (29/29), **not yet proven by a real run in Figma
  desktop.**
- Three role guides for Paid Acquisition, the copywriter and the designer, in this wiki.

### Claims removed from the June version of this page

- *"All templates complete, confirmed 2026-06-26"* and *"Bree confirmed all templates incorporated"*
  predate the entire Reddit surface and are no longer true in any useful sense. As of 2026-09-15 an
  audit of the 20 Reddit templates found **eight open Figma-side defects** (see
  `docs/OPEN-ITEMS.md`, 2026-09-15 entry).
- The migration status dated 2026-06-26 naming **John Papus** and **Mike Leon** is **UNVERIFIED** as
  of today. Treat it as a lead to chase, not as current state.

---

## What is left, in the order it should be done

1. **Transfer ownership** per the table above. Repo, Railway project and billing, the four keys, and
   the org-level MCP connector registration. This is the only work with an external clock.
2. **Escalate the LLM Gateway values** (endpoint, key, model) with Haresh's team. Production is
   blocked on values that do not exist yet, and this is a hard constraint, not a nice-to-have.
3. **Reddit end-to-end verification** with Elise on plugin 2026.09.16, plus her eight Figma fixes.
4. **`GOOGLE_SERVICE_ACCOUNT_JSON`** so the delivery stage can run for the first time.
5. **Prospecting/retargeting image split.** Adrie asked for this on 2026-09-10. Spec is clear, not
   built.
6. **Reddit copy shape in the pipeline.** `field_caps_reddit_feed` exists in config and is read by
   nothing; Reddit runs currently generate Meta-shaped long/short pairs.
7. Field-coverage polish: Pie Chart quadrant labels, Photo-with-Text subhead variant, layer renames.
8. Production hardening, which is Upwork engineering's: LLM Gateway, OAuth on the MCP server, per-user
   audit trail, sprint state off the volume and into a database.
9. **Rotate** the Figma and Railway tokens shared during the build.

---

## Things that will surprise a new engineer

- **The plugin cannot be tested by whoever changes it.** Figma plugin code only runs in Figma
  desktop. `scripts/verify_plugin_changes.py` exists because of this: it replays the plugin's own
  lookup logic in Python against live Figma JSON so a change can be justified before shipping. Use
  it. Two separate "verified" claims have shipped false confidence on this surface.
- **Three copies of every wiki page.** `docs/wiki/`, `web/content/wiki/`, and two independent page
  lists in `main.py` and `web/lib/wiki.ts`. Editing one and not the others is a live drift risk that
  has already happened. Inherited debt, deliberately not consolidated this month.
- **`pipeline/run_pipeline.py` is the only canonical implementation.** The numbered stage files
  `02_*.py` through `06_*.py` are a stale, non-canonical scaffold. Do not port to or from them.
- **The assembly contract is layer-name strings in a file designers freely edit.** The countermeasure
  is `tests/figma_template_lint.py`. It is currently run by hand by an engineer, which stops working
  once there is no engineer.

---

## Stakeholders

| Person | Role | Owns |
|---|---|---|
| Max Karasso | Inheriting engineer | The system, after 2026-09-30 |
| Logan Heath | Tech lead (CM contractor, through 2026-09-30) | Pipeline, web app, chat, plugin, integration |
| Adrie Etherington | Creative lead | Copy rules, brand voice, approved claims, curation |
| Elise | Designer | Figma templates and the assembly run |
| Breanna Hovan (Bree) | Design producer | Production schedule, change log |
| Brian | Upwork CD | Veto on AI photography, source of the no-AI-photo rule |
| Leon Zhao | Upwork architect / sponsor | Hosting decisions, InfoSec narrative, handoff support |
| Ravi Parikh | Director of AI (Wonder) | Architecture sign-off |
| Haresh's team | Upwork engineering | LLM Gateway, Terraform, production deploy |
| Sal / Shams | Upwork InfoSec | Security review |
| Blake | CM owner | Logan's contracting entity |

---

## Handoff checklist

- [x] Wiki-aware Ask ADAM chat live with cited answers
- [x] Live copy generation verified on the Railway key
- [x] `PIPELINE_API_KEY` set (was outstanding in June)
- [x] Reddit ad types, caps enforcement, and plugin template resolution shipped
- [ ] **GitHub repo moved to an Upwork/CM org**, Railway deploy source repointed
- [ ] **Railway project and billing transferred** off the personal workspace
- [ ] **MCP connector registered at the Upwork org level** rather than Logan's personal account
- [ ] API keys swapped to team-funded accounts, build-time tokens rotated
- [ ] **`FIGMA_ACCESS_TOKEN` replaced with a team token**
- [ ] LLM Gateway values received from Haresh's team
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` set, delivery stage verified once
- [ ] Reddit verified end to end in Figma desktop
- [ ] Gemini quota confirmed and an image-style sprint run
- [ ] A live walkthrough recorded: order, gates, assembly, delivery
