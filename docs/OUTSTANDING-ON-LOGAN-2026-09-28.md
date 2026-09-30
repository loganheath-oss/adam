# What is actually waiting on Logan — 2026-09-28

Swept four sources: the ADAM 2026 Figma file's 308 comments (readable for the
first time tonight), the `.docx` comment threads on the live guides, the threaded
comments in Adrie's punch-list workbook, and the 09-14 / 09-21 / 09-23 / 09-28
call transcripts. This is what nobody has an answer to yet.

## 1. Figma — six open threads name Logan

| Age | Node | Who | What |
|---|---|---|---|
| **83 days** | `6063:2068` `Adtype_Device-UI` | Elise, 07-07 | *"I updated the template here so the scale isn't wonky in the interface, **can we refresh the template in ADAM?**"* |
| 108 days | `4438:108` | Elise, 06-12 | *"Confirm tags are correct in back end and no Figma action is required"* → reply *"Logan debugging! 6/12"*. Left mid-debug. |
| 108 days | `4438:108` | Elise, 06-12 | Per Ravi — more robust photo tags, possibly with the agency that shot them. |
| 139 days | `5491:466` | Brandon, 05-12 | Colour swatches for the order form. **Brandon left in July; almost certainly dead**, but still marked open. |

**The Device-UI one is the find.** A direct request with a question mark, 83 days
old, referenced in no transcript and on no punch list. It only surfaced because
the new token can read comments.

**Not waiting on him:** the two 09-15 threads (`7356:1258`, `7417:813`). Both
nodes are **Generated Tests** frames, not templates — Elise annotating her own
test output. "72/48" is 72pt headline / 48pt body. They matter only as context:
that is the change she later blamed for the 09-21 formatting error
(*"ADAM having trouble reading the updates we made to make the copy bigger"*).

## 2. Guide comments — three need Logan

- **Adrie, Engineer guide, 09-25**, tagging both his addresses: *"I need to know
  if ADMINS can do this or if only the engineer can complete these actions."*
  The answer is now **yes, admins can** — the dashboard grew a prune control on
  09-28 — but nobody has told her.
- **Breanna, Engineer guide, 09-28**: *"What specifics should we include here for
  'day 1 checklist'?"* Needs a content decision. (She took the handoff link herself.)
- **Elise, Producer + Designer guides**: the *"Logan looking into the probability
  this will occur, to report back"* thread. Answer ready, not posted.

## 3. Lee's feedback doc — what is Logan's

Lee, 09-21: *"you don't necessarily need to take it as every single thing needs
to be addressed."* Guidance, not a gate. Most of the ~60 asks belong to Adrie,
Breanna or Elise. Logan's section:

**Done** — access list; current-vs-stale files marked; deploy and rollback cheat
sheet; LLM gateway flagged as unfinished; owner + last-updated on all four guides.

**Open**
- ❌ **Basic setup steps** before jumping into code.
- ❌ **The "make sure everything works" checklist.** Lee named all six items:
  site loads, admin page healthy, tests pass, plugin version current, Figma check
  passes, test sprint works. Every one is a known command.
- ❌ **Remove personal names** so the guide does not go stale.
- ⚠️ **Day 1 checklist** is currently just the access list — this is what Breanna's
  comment is asking about.

**Cross-cutting, and arguably his**
- ⚠️ **"Update all missing [LINKs]."** One remains: the KOTH brief example in
  `17-role-paid-acquisition.md:148`. Lee named it explicitly. Picking the brief is
  Adrie's or Lee's call, not an engineering task.
- 🔴 **"Make sure there is only one clear source of truth."** There are currently
  **three** copies of each guide and they have diverged: the repo `docs/wiki/`
  (ahead — carries the 09-27/09-28 fixes), Logan's own Drive copies (frozen 09-23,
  no comments), and the team's `.docx` in Upwork's Drive (has their edits and all
  the comment threads). The 09-28 call settled the direction — docs become master,
  ADAM's wiki links out — but nobody has executed it. Concrete symptom: the
  Google Doc Engineer guide still sends a new engineer to `/admin`, **which 404s**;
  the repo has said `/admin/dashboard` for some time.

**Nobody has started** Lee's QA step: give each guide to someone who has never
used ADAM and log every "where is that?".

## 4. Cleared

Everything Logan committed to on 09-23 and 09-28 is done: whether the
assembles-but-fills-nothing case was still possible (**yes — the Rules cards, 19
of 22 styles — now fixed**), whether generated images interfere with the next run
(**no**, pinned with tests), the `/admin/storage` and `/admin/prune` 404s (wrong
host, guides corrected), and reading Lee's engineering feedback.

The one loose end is that he never tagged Elise in Figma about the light-mode
variant — but he had already determined it was not a defect, so there is nothing
to say.

## 5. One public URL — done 2026-09-29, with two follow-ups

`adam-web-production.up.railway.app` now serves everything via a `fallback`
rewrite; the `adam` backend keeps the sprint volume and is no longer addressed
directly. Verified live: 20/20 routes OK, auth-gated routes 401 (reachable) not
404, dashboard login works through the proxy, plugin zip byte-identical.

Two references to the backend host remain, both machine-to-machine and invisible
to Upwork. Each needs a deliberate step, neither was worth rushing:

- **Figma plugin.** `plugin/manifest.json` `allowedDomains` hardcodes the backend
  host and Figma enforces it, so `ui.html` posts `/assembly-report` there. Moving
  it means a new plugin build AND everyone re-importing — the team had just taken
  2026.09.28. Do it with the next plugin release, not on its own.
- **MCP connector.** Registered against the backend host in Logan's personal
  Claude account (which is separately a handoff blocker — see `CLAUDE.md` §4).
  Re-pointing it at the public host means re-registering the connector.

**The asymmetry that caused the drift is still there:** the backend auto-deploys
from `main`, `adam-web` does not (manual `railway up` from an isolated copy). So
the two can still ship out of step. Worth raising with Haresh's team for the
December migration — two services is also two things to migrate.

## 6. Working session 2026-09-29 — the list, as of 2026-09-30

| Item (Gemini's wording) | State |
|---|---|
| Fix 22px font on Reddit | **Done, plugin 2026.09.30** (6bd0eb2). Meta too. Cause: fitTextLayer's shrink loop can't narrow a fixed-width box, so a 3px margin miss ran every copy-panel value to the 22px floor. |
| Troubleshoot degradation / false flags | **Partly.** Font preflight no longer counts a substituted font as ⚠. Which warnings actually fired in Elise's runs is unknown — the assembly report keeps counts, not lines. Ask Elise to paste the ⚠ lines from one run. |
| Plugin + manifest logic for new naming | **Done.** Lookup already resolved size-only names via the container; variant choice didn't (light→Dark, photo testimonial→text-only Alt1, Social Media Profile→legacy page). `scripts/verify_template_resolution.py` now proves every style×size per platform. |
| Reddit thumbnails | **Done 09-29 17:03** (575d618), verified live 09-30: 20/20 load. Adrie's call was before the deploy. |
| /admin/storage, /admin/prune 404 | **Done 09-29 17:37** (4b212cb), verified live. /admin/prune is a POST behind the dashboard's checkboxes, not a page — the team's Google Doc Engineer guide still says "prune at /admin/prune" with no host. |
| Replace legal guidelines | **Blocked on Adrie's link.** Swap = refs/ file + `REF_FILES["compliance"]` in build_refs.py + rebuild + copy_regression. Also her Claude Project knowledge. |
| Invoice to Lee | Logan's. |

Also found: on the Assembly page, `Testing_04302026` holds four frames named
"Reddit - Static Grouped", and findBoardMaster searches the current page first,
so a Reddit run started there clones one of those instead of Elise's master
7356:1259. Today they are structurally identical to it (copy panel at 48px), so
nothing breaks — but an edit to the real master will not reach runs started
from Assembly until those copies are deleted or renamed.
