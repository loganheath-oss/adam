# ADAM Architecture Audit — 2026-07-30

Six parallel read-only audits (pipeline core; backend service; chat agent + web UI;
intake + configs; Figma plugin + MCP; infra + stage scaffold), synthesized and
deduplicated. Every P0 below was **independently re-verified against the code**
after the audit pass — line cites are confirmed, not speculative.

**Why this audit:** Adrie's incidents keep sharing root causes. The question was
whether the system is *built* to prevent those classes or merely patched per
incident. Answer: patched. The five patterns below are still open at the
architecture level, and each has multiple live unexploded instances.

---

## The five root patterns

1. **Many writers, no atomic state.** Sprint state (`pipeline_state.json`,
   `copy_outputs.json`, review CSV) is written by three entry surfaces (HTTP,
   chat tool, MCP connector) across two processes with non-atomic `write_text`
   and a lock that covers only one path.
2. **Multiple truths, no single source.** Style names exist in five universes
   (form, intake, style guide, template registry, plugin maps + Figma file);
   copy selection lives in two files; approved images live in two directories;
   the numbered stage modules are a diverged second implementation.
3. **Fail-open error paths.** When a guard's machinery fails, the system ships
   MORE instead of stopping: review failure selects all 6 concepts; Figma
   library failure reroutes to AI-generated people; template lookup failure
   silently picks a cross-family template.
4. **Boundary validates after acceptance.** `/submit` returns success before
   `validate_payload` runs; unbuildable styles are orderable; quantities
   silently truncate; order text renders unescaped on the operator's page.
5. **Display not bound to the data contract.** The renderer, the picker, and
   the chat page each hand-pick fields/parsing — so complete stored data
   displays incomplete (the exact 2026-07-30 incident class, three more times).

---

## P0 — verified, will visibly bite the operator (or already are)

### P0-1 · Poll percentages are structurally impossible
`run_pipeline.py:104-132` builds the output schema from base fields + the style
guide's `char_limits` keys with `additionalProperties: false`. The poll entry's
`char_limits` = {poll_question, poll_option_a, poll_option_b, cta} — **no
`poll_pct_a`/`poll_pct_b`** (integers, never in a char-limits dict). The prompt
demands them (`:1753-1759`); the manifest ships them (`:3664-3666`). Since
structured output landed (07-28), the API strips the percentages from every
Poll concept. `Poll_Pct_A/B` are always empty in the manifest.
**Fix:** one per-style field registry (name + type + cap) generating BOTH the
schema and the prompt field list, plus a deterministic post-parse check that
every prompted field is present. (Also fixes the P&R prompt/schema
contradiction on `creative_headline`.)

### P0-2 · Chat model calls block the entire backend (independently found twice)
`orchestrator.py:905` is `async def run_agent_turn`; inside it, a **sync**
Anthropic client call (`:962-971`, up to 16k output tokens) and inline tool
dispatch — including `tool_approve_gate`, which runs a whole gate stage —
execute on FastAPI's event loop (`main.py:3001`). During any chat turn, every
other request stalls: state polls, SSE heartbeats, other users, `/health`.
A chat-approved gate freezes the server for minutes. This IS the "random
hangs" experience, and proxies idle-kill the zero-byte SSE stream meanwhile.
**Fix:** `AsyncAnthropic` + `messages.stream()` yielding deltas; tools via
`run_in_executor`; chat approval schedules the same background `_run_gate_task`
as HTTP instead of running the stage inline.

### P0-3 · Copy review fails OPEN: API error ships all 6 concepts, legal guard bypassed
`run_pipeline.py:2617-2633`: on any review-call failure (one attempt, no retry)
every concept gets `selected=True` — and the legal/length de-selection
(`:2526-2549`) lives only in the success path above, so flagged concepts ship.
One 529 at the wrong moment → a style presents 6 picks including one with a
banned term, then generates images for all of them (2-3× spend).
**Fix:** split judgment from enforcement — run the deterministic pass (legal
de-select, cap de-select, diverse top-N) unconditionally AFTER whatever
produced the ranking; give review the same retry as generation.

### P0-4 · Gate-5 image veto is silently ignored
Stage 05 hardlinks every image into `exports/` (incl. `_final`) BEFORE the gate
(`run_pipeline.py:3529-3541`); the gate tells the operator to delete unwanted
images from `images/`; resume rescans only `images/`; stage 06 marks
`delivered` purely on `exports/*_final.png` existence (`:3584-3586`). A deleted
image's hardlink survives → the rejected creative ships marked delivered.
**Fix:** `images/` is the single approval truth; derive exports at stage 06
from what survives, and reconcile+downgrade anything orphaned.

### P0-5 · Figma-library failure reroutes people-styles into AI-generated people
`run_pipeline.py:2908-2916`: one un-retried fetch; on exception the code prints
"Photo-based styles will fall back to Gemini" and `library_cache=None` makes
the `and library_cache` guard (`:3031`) fall through to `gemini_generate` with
person prompts — violating Brian's ratified no-AI-photography rule on a network
blip, with one console line as the only signal. Auto-runs sail straight through.
**Fix:** deterministic policy assertion — `PHOTO_LIBRARY_STYLES` may never emit
`gemini_generate`; on library failure route to `needs_human_selection` + a
structured flag. Add retry to the fetch.

### P0-6 · Three approval surfaces, one lock; MCP path has no state check at all
`main.py:2100-2128` (locked) vs `orchestrator.py:377-411` (state check, no
lock) vs `mcp_server/server.py:207-242` (**no state check, no lock**, raw
subprocess with a kill-timer that SIGKILLs mid-stage on timeout). Concurrent
approvals run the same stage twice (double spend, interleaved writes); a
timed-out MCP call kills a live stage mid-write and invites a re-approve over
partial output.
**Fix:** one choke point — state CAS + lock inside `resume_gate_N` itself so no
caller can bypass; MCP calls the guarded path, never a raw subprocess.

### P0-7 · The renderer deletes the line breaks the verbatim law protects
`web/components/markdown.tsx` (react-markdown + gfm, no `remark-breaks`)
renders assistant chat (`sprint-workspace.tsx:569`). Markdown collapses single
newlines → bullet stanzas and lead-ins display as run-on paragraphs even when
`chat.jsonl` is byte-perfect. The legacy FastAPI chat preserves them
(`white-space: pre-wrap`), so two surfaces show different copy from the same
transcript. Recurrence of the 07-30 truncation incident at the render layer.
**Fix:** one whitespace-faithful rendering contract for all chat surfaces +
a fixture test diffing rendered text against stored text.

### P0-8 · The Gate-3 picker never shows `body_long`
`web/components/copy-picker.tsx` declares `body_long` (`:12-13`) and never
renders it — only `body_short` (`:175`, `:191`). Selection is saved from this
surface. The field that actually ships in the Meta feed is picked blind.
**Fix:** generate the picker's field list from the pipeline's canonical
copy-field schema so a copy field can never silently vanish from review.

### P0-9 · Web chat page reads `m.content`; the API sends `text` — restored chats are blank
`web/app/sprints/[id]/chat/page.tsx:24-26` maps `content: m.content`
(always undefined) over `{seq, role, text, ts}` records. History renders
empty; the next send posts role-only messages → API 400. Same field-name class
as the earlier zero-messages scanner bug. The workspace does it correctly —
only this page is broken.
**Fix:** one typed chat-history client used by both surfaces (or delete this
page in favor of the workspace).

### P0-10 · /data has no backup and is the entire data plane
All sprints, chat transcripts, gate-decision audit trails, Adrie's quotes
library, and learnings live on one 500MB volume; zero export/snapshot/restore
paths exist anywhere; `/admin/prune` can legally delete almost everything.
The learnings-wipe fix concentrated MORE irreplaceable state here.
**Fix:** nightly off-box export (tar to Drive — a service account is already
planned) + mirror learnings/quotes/gate-decisions into the existing Postgres;
document a restore drill.

---

## P1 — structural, will bite eventually

**State & durability**
- Non-atomic `write_text` on every load-bearing artifact (`copy_outputs.json`,
  `order.json`, manifests) while only the small status files got the
  temp+`os.replace` treatment; one torn `pipeline_state.json` 500s `/sprints`,
  the sprint page, and `/api/sprints` for ALL sprints (`main.py:506-507`
  raises; startup scan skips silently). → single atomic read/write/CAS helper
  (`sprint_state.py`) used by main.py, orchestrator, MCP.
- ENOSPC mid-stage leaves state `running` forever: the error handler's own
  `write_text` also fails, and the stuck-sprint detector only watches
  `awaiting_gate*` — the real stuck class is invisible. → error-state
  persistence off the failing resource + widen detector to stale `running`/
  `resuming_*` mtimes.
- Redeploy-killed sprints never emit `sprint.failed` → clean-rate metrics
  overcount success. Webhook `os.execv` has no drain and races running stages;
  two deploy mechanisms (Railway auto + webhook) coexist undocumented.
- No free-space gate at write-heavy entry points; finals-upload caps
  (2GB/sprint) exceed the 500MB disk. Spend events double-count on resume
  (cumulative token_usage re-logged per terminal settle).
- Chat persistence is best-effort (`_append_jsonl_safe` failures ignored);
  agent-side `_read_jsonl` is strict while the UI reader is lenient — one torn
  line permanently breaks `get_chat_history` for that sprint while the page
  renders fine.

**Identity & truth**
- `concept_tag` (model-invented, never uniqueness-checked) keys the operator's
  YES/NO overrides and the manifest copy-join; collisions land her decisions on
  the wrong concept. Rerun-with-same-id resurrects stale review CSVs. → join
  on `concept_id` everywhere; de-dup tags deterministically.
- Copy selection lives in `copy_outputs.json` AND `copy_review.csv` with a
  silent best-effort sync keyed on that same collidable tag; the resume pass
  can override her on-screen selections with stale CSV state.
- `_apply_cta_mix` destroys the original CTA and isn't idempotent — a Gate-3
  swap can ship a "must have one CTA" style with zero CTAs and mis-capped
  headlines (conditional caps not re-run after the swap).
- Stage 03 resurrects operator-rejected concepts (`all_matching[:3]` fallback)
  and ships a "Find talent fast" placeholder for empty styles; `failed_styles`
  gates nothing.
- AI ranking roster is trusted: an omitted `original_index` silently deletes a
  paid-for concept; a repeated one duplicates it. → reconcile to exactly 1..N.
- Retargeting on-image copy bypasses the hard-cap/conditional-cap enforcement
  applied to top-level (Prospecting-mirroring) fields — the enforcement surface
  diverges from the shipping surface. → run every guard over the flattened
  per-audience view the manifest writer uses.
- Cross-sprint photo freshness is dead code: `record_usage()` has zero callers;
  the "don't repeat photos for 3 sprints" mechanism has never run.

**Boundary & validation**
- `/submit`: unauthenticated, acknowledges before validation, accepts a
  client-supplied `sprint_id` that clobbers an existing sprint mid-flight, no
  idempotency (double-submit = duplicate sprints). Hightouch path has all of
  this; the form path has none.
- Order fields (`brief`, `driver`, …) render UNESCAPED into the operator's
  session-authenticated review page (`main.py:3184-3190`) — stored-XSS from a
  public endpoint into the approver's browser. The copy cards right below
  escape correctly.
- Ten orderable styles have no buildable template (`NEEDS_TEMPLATE`/`MANUAL`);
  failure surfaces at assembly (the most expensive manual point) instead of at
  submit. Quantity >6 silently truncates to 6. Quantity coercion turns typos
  into 0 then back into 1-2. Empty brief runs generic with no Gate-2 signal.
- Refs freshness self-check watches `refs_context.json` mtime (resets every
  deploy) instead of comparing source vs compile — Adrie editing a ref without
  recompiling is exactly the case it cannot see.
- Public chat SSE exposes `approve_gate`/`edit_order` with only the sprint URL
  as credential; legacy 4-hex sprint IDs (65,536) remain valid and enumerable;
  finals DELETE is public. MCP HTTP standalone mode fails OPEN with no token;
  plain `==` token compares; admin key rides in query strings into access logs.

**Figma & assembly**
- Cross-family template fallback chains still live (`code.js:39-81`) and log
  as SUCCESS on fallback; substring matching lets "testimonial" match Text
  Only frames; no variant hint in styled_per_row mode → wrong-but-plausible
  template class (the sticky-note incident) is still open.
- Split Screen dual-image fill queries legacy layer names that the plugin's
  own Normalize button renames away → one real photo + one baked stock photo.
- Structured fills discard return values and log ✓ unconditionally; the
  assembly-health loop is dead end-to-end (UI never renders warnings; the
  sprint-id regex can never match real IDs; the manifest has no `sprint_id`
  column, so the dashboard report never fires).
- No try/catch in the assembly loop — one throw silently kills the run
  mid-board with no completion report.
- `template_registry.json` (last updated 05-11) is a stale third naming
  universe whose dead frame IDs collapse Text Only/Meme variants into one
  frame; 14 "NEEDS_TEMPLATE" styles are ones the plugin now fills.
- `figma_template_lint.py` lints the plugin's FALLBACK maps, not its actual
  resolution path — it can pass CLEAN while assembly is broken. → lint must
  execute the same resolution logic + check layer inventories + frame-ID
  liveness.
- Text fitting only fixes right-edge overflow; wrapped copy can overrun the
  ad bottom / CTA zone; shrink floors at 22px still clipped; logs carry no ⚠.
- MCP `get_copy_concepts` synthesizes a review table missing the per-audience
  columns at exactly the gate where they must be reviewed; `get_manifest`
  reads a file nothing writes (always []); `list_sprints` caps at 20 with no
  `total/truncated` signal.

**Stale scaffold & docs**
- Numbered stage modules 02-06 are a diverged pre-July implementation (old
  model, 4096 cap, `[:N]` ref slices, no legal guardrail, MindStudio refs) and
  CLAUDE.md §11 tells the migration engineer to port TO them. The `[:N]`
  ratchet only scans `run_pipeline.py`. → delete or stamp NON-CANONICAL;
  extend the ratchet to all of `pipeline/`; fix CLAUDE.md.
- The "retired" Fly app auto-wakes on any request (`auto_start_machines=true`)
  with live tokens and April sprint data baked into its image — an invisible
  parallel deployment until deleted and its secrets rotated.
- `.env.example` is two architectures old; bootstrapping from it leaves `/mcp`
  auth OFF. CLAUDE.md still teaches Fly-era truths (§3/§10/§11 contradictions).
- adam-web manual deploy has no skew detection — a forgotten deploy after a
  backend field rename renders blank review fields, indistinguishable from
  data loss.

---

## P2 (selected)
Approve button posts an empty note (the "required" rationale is never
captured) and is armed before the artifact renders; tool-doc/schema
contradictions in the orchestrator (`limit` default, optional `note`);
`sync_log.jsonl` on container FS (deploy-amnesiac, same class as the
learnings wipe); analytics endpoints return 200-with-error (broken DB looks
like a quiet dashboard); emoji validators miss ⏱ (U+23F1) and ⭐ (U+2B50) —
two emoji the pipeline itself inserts — and caps count code points, so ZWJ
clusters can be severed on-creative; CLI `--resume` bypasses gate-state
checks; style-routing sets duplicated between run_pipeline and figma_library.

---

## The structural program (in leverage order)

1. **`sprint_state.py`** — one atomic, locked state API (temp+rename, CAS,
   per-sprint lock) used by main.py, orchestrator, MCP; move state validation
   INTO `resume_gate_N`. Retires P0-6 + the torn-state, stuck-state, and
   double-approve families. (~1 day)
2. **Fail-closed guards** — deterministic enforcement pass (legal/caps/
   selection floor) that runs unconditionally after review; photo-policy
   assertion; per-row plugin error handling with a DEGRADED completion state.
   Retires P0-3/4/5 + the fallback family. (~1 day)
3. **One field registry per style** — generates the JSON schema, the prompt
   field list, the manifest columns, AND the review-UI field inventory.
   Retires P0-1, P0-8, the MCP column drift, and the enforcement-surface
   divergence. (~1-2 days)
4. **One style/naming table** — slug-keyed, carrying {form label, guide entry,
   template, buildable}; form + intake + matcher + plugin + lint all consume
   it; lint executes the plugin's real resolution logic. Retires the
   five-universes family. (~2 days, needs Elise's Figma pass)
5. **Async chat + verbatim rendering contract** — AsyncAnthropic streaming,
   executor tools, `remark-breaks`/pre-wrap + render-vs-stored fixture test,
   shared typed chat client. Retires P0-2/7/9 + the SSE fragility family.
   (~1 day)
6. **Ops floor** — nightly /data export + Postgres mirror for learnings/
   quotes/decisions; free-space gate at entry points; drain-before-restart;
   delete the Fly app + rotate its secrets; delete stages 02-06; regenerate
   `.env.example`. (~1 day + Logan actions)

Quick wins shippable independently: escape the order-summary fields (30 min);
`/submit` validate-before-acknowledge + idempotency (1-2 h); body_long in the
picker (30 min); `remark-breaks` (30 min); chat-page field fix or deletion
(30 min); review-failure fail-closed (1 h); `record_usage()` call (15 min);
Poll fields into the schema registry (1 h interim: add int fields to schema).

---

*Verified and held up under re-check: all ten P0s. Confirmed sound during
audit: SSE finally-block persistence, Hightouch idempotency, webhook HMAC,
zip-slip guard, UTC handling, Next.js no-store fetching, restart-recovery
machinery (the gap is timing, not existence).*
