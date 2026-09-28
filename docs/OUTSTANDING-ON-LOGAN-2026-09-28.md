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
