# ADAM — Open Items (from Adrie's test + the July 2026 spec docs)

Source: Adrie Etherington's ADAM Test Brief (issues) + Ad Type Style Guide + Meta
Claude copy instructions, provided 2026-07-14. Grouped by workstream; most-actionable
first. Status: ✅ done · 🔨 in progress · ⛔ blocked/needs coordination · ⬜ not started.

## A. Copy engine
- ✅ **Wire the binding 24-entry Ad Type Style Guide into copy_gen.** Replaced the loose
  `refs/visual_style_copy_rules.txt` with the July guide; copy_gen now resolves the ONE
  matching entry per style and injects it **untruncated** (was `copy_style_rules[:5000]`,
  which silently cut entries ~#11–24 — the root cause of chat/tweet drift). Matcher +
  all 24 styles + alias + no-match fallback verified. `run_pipeline.py`
  `_parse_style_guide` / `_style_guide_block`.
- ✅ **Chat Bubble reads as a conversation, not headline+subtext** (Adrie #2). Reframed the
  `chatbubble` block to two dialogue turns (opener ≤18 / reply ≤91), field names kept.
- ✅ **Long copy requires a bullet/paragraph mix** (Adrie #3). Added "LONG PRIMARY COPY
  FORMAT" to `meta_copy_instructions.txt` (≈half bullets w/ ✅/emoji, ≈half punchy prose).
- ✅ **Style Guide converted to structured JSON + deterministic enforcement.**
  `configs/ad_type_style_guide.json` is now the single source of truth (prose rules +
  `char_limits` keyed to ADAM's own output fields). `run_pipeline.py` renders the matched
  entry into the prompt AND enforces caps: HARD on-image overflow → `length_flags` →
  de-selected in ranking + backfilled (like the legal guardrail); SOFT editorial/feed
  overflow → `length_warnings` → recorded + demoted (yield protected, no copy mangling).
  Universal field caps now defer to the matched entry so text-heavy types (Tweet 115,
  Lifestyle 100) aren't force-capped at 30. `_load_style_guide` / `_style_caps` /
  `_enforce_lengths`. Verified: all 24 styles resolve, over/under-length + array fields flag
  correctly, compiles.
- ⬜ **Tweet reads too headline-y** (Adrie #2). Entry #19 (organic post) now reaches the
  model untruncated + can run to 115 chars — expected to resolve. **Confirm with a live run.**
- ℹ️ **Tweet has no dedicated on-image field** — its ~115-char post currently maps to
  `creative_headline`. Works, but a dedicated `tweet_text` field (like Chat Bubble's fields)
  would be cleaner. Minor follow-up.
- ⛔ **True two-bubble Chat Bubble layer** — a real field rename (chat_bubble_1/2) touches
  the Figma template layers + plugin mapping + manifest columns. Needs Elise. The content
  reframe above is the safe interim; revisit if the template renders bubble 1 as a header.
- ⬜ **Naming: "Creative Headline" vs `Text_On_Visual`** — align so the PDF/labels don't confuse.

## B. Order form
- ✅ **End at Submit — submitters kept out of the sprint surface.** Confirmation page ends the
  flow (dropped the "Open the sprint" button) with a copy-link + Adrie's Slack workflow copy
  ("drop it in #paid-acquisition"). Removed "Sprints" from the top nav + home hero/cards.
  `/sprints` still works by direct URL for reviewers (verified live 200); returns as an
  admin-gated nav item with RBAC. Deployed to adam-web + verified on the live site.
  NOTE: this is UX-level (no hard auth yet) — true enforcement is Phase 3 RBAC.
- ✅ **Key Messaging themes in the Brief (→ Additional_Info).** Added an insertable
  "Key messaging themes" helper below the Brief field: data-driven chips (starts with
  Sprint 9 — AI + Specialization) that drop the theme's angle/why/top-categories/considerations
  into the Brief so it guides copy generation. Chip shows ✓ when inserted. Add the next
  sprint's theme to `KEY_MESSAGING_THEMES` in `app/new/page.tsx`. Deployed.
- ⛔ **Blank Notification tile** in the order-form style menu (missing Figma template image) — asset fix (Elise).

## C. Bug
- ✅ **Long brief → stalls at gate 5 / no manifest.** Root cause: the brief was the ONE
  unbounded prompt input; a long brief pushed the model's JSON past the 4000-token output cap
  → truncated JSON → `json.loads` throws → 3 retries with the same oversized prompt all fail →
  **0 concepts** → nothing downstream → no manifest. Three fixes: (1) cap the brief at 6000
  chars in the copy prompt (like every other block); (2) raise output cap 4000→8000; (3) add
  `_salvage_json_array` so a truncated array still yields its complete concepts instead of
  zero. Verified live: a ~5k-char brief that returned 0 now generates all 6 concepts ($0.08).

## A2. Review-pass findings vs Adrie's docs (2026-07-15 audit)
- ✅ **Testimonials — interim fabrication policy (Logan's call).** No real-quote library exists,
  so Lorem Ipsum is out and fictional quotes are sanctioned: prompt now prefers a brief-provided
  real quote, else generates a clearly-fictional person+company; every testimonial concept is
  auto-flagged "ℹ FICTIONAL testimonial" in review notes. Style-guide Entry 5 rewritten to the
  interim policy (the old NEVER-fabricate text contradicted the generation instructions in the
  same prompt). **Real fix = a quote library** (→ Adrie's July "Quotes or instructions on
  quotes" roadmap item): a refs doc of approved real quotes ADAM samples from.
- ✅ **Feed-headline caps aligned to Adrie's spec:** Headline_Long ≤50, Headline_Short ≤30
  (was 40/27) — prompt (both targeting branches) + field_caps_meta_feed.
- ✅ **Sticky Note single-column version now generated** (Entry 17 requires BOTH layouts).
  Template already exists in Elise's Figma (registry caps: Single Headline 26 / Single Column
  112). Copy gen emits `single_headline`+`single_bullets` (hard-enforced), manifest carries
  `Single_Headline`/`Single_Bullets`. ⬜ Plugin assembly of the single-column frame untested —
  verify on the next sticky-note sprint.
- ✅ **With-CTA / without-CTA variant mix implemented.** Each guide entry now declares `cta_mix`
  (all ×7 / none ×8 / one ×6 / two ×1 / default ×2). The model always writes its best CTA;
  `_apply_cta_mix` runs AFTER ranking and deterministically keeps the CTA on the top-N ranked
  selected variants, blanks the rest, and sets `no_cta` → new manifest column → the plugin's
  existing `wantCTA` template-variant pick (which was never fed before). Entry 3's
  subhead-only-without-CTA rule enforced too. Unit-verified all five modes + rank ordering.
  ⬜ Verify on a live sprint that the no-CTA template variants assemble correctly in Figma.
- ⬜ **Variant model deviation — surface to Adrie for sign-off.** Her spec: N concepts × 3
  labeled variants (A/B/C, original re-executions). ADAM: 6 independent concepts → top 3.
  Outputs land similarly; get her explicit OK rather than re-architect.
- ⬜ **Missing refs from Adrie:** Freelancer Work Categories.pdf (Entry 9 talent tags), updated
  ad examples doc, updated SMB copy bank (all on her July list). Drop into refs/ + build_refs
  when received.

## Quotes library — BUILT & LIVE (2026-07-17)
- ✅ **Live approved-quotes page at `/quotes`** (nav item, Learnings-style editor) — answers
  Adrie's "static PDF goes stale" concern. Volume-backed (`/data/approved_quotes.md`, survives
  redeploys); edits apply on the very next run; `quotes.edited` dashboard event; runbook updated.
- ✅ **Testimonial gen consumes it, verified live:** each concept gets a DIFFERENT library quote
  (exact attribution), library concepts are pinned into selection + not marked fictional;
  fictional placeholders only fill beyond the pool. Format: `- "Quote." — First L., Title, Co`.
- 📋 **Friday:** Adrie pastes her quotes doc into `/quotes` → done, no integration step.
- 🔮 When Sarah's client photography lands, quote↔photo pairing hangs off these entries.

## Meeting outcomes (2026-07-16 working session — Adrie, Bree, Logan, Ravi)
- 📅 **Deadlines locked:** Adrie — ad examples doc Jul 17, approved-quotes doc Jul 18 (WIP),
  key messaging brief Mon Jul 21; copy bank already DONE. Delivery meeting **Aug 4**.
  Platform updates = first two weeks of Aug (team); Elise+Zach explore Figma nice-to-haves
  mid-Aug; Bree's change log late Aug → Logan reviews before first week of Sept.
- ✅ **DECIDED: approved-quotes document** — static reference doc of approved quotes for ADAM.
  Adrie worried a PDF goes stale → candidate build: a LIVE editable Quotes page (mirror of
  /learnings) that testimonial gen reads + distributes distinct quotes from. The pinning +
  distinctness machinery already lands quotes correctly once a pool exists.
- ⚠️ **Adrie ruling on testimonial imagery:** the 26 curated profiles are fine for Talent
  Profile cards but CANNOT represent clients on quote/testimonial ads long-term. Real client
  photography = Sarah (Adrie consulting). Interim fictional-quote + curated-photo behavior is
  placeholder-only; the quote-library integration must pair quote ↔ approved client photo.
- ℹ️ **Linear** = task management + engineering escalation. Haresh's migration help requires a
  formal Linear request (Adrie + Lee submitting, with business impact + stakeholders).
- ℹ️ **August knowledge transfer:** record as many meetings as possible (transcripts mined for
  bug/feature patterns), Bree's fixes/unresolved spreadsheet → Logan last week of Aug.
- ✅ **Emoji library action item — CLOSED (2026-07-16 evening):** no library/integration
  needed. Emojis are Unicode the model writes natively; the "art-director" rule (derive from
  each line's concrete subject + brief theme, no repeats, classics only) is live + verified.

## Observability build — SHIPPED (2026-07-17)
Goal: know exactly what's happening when the Upwork team runs ADAM in August (team
self-diagnosis in the moment + Logan's September reconstruction). All live + verified.
- ✅ **P0 Activity timeline** (`/admin/activity`) — every event newest-first, filter by
  type/user/sprint; **global error capture**: unhandled server 500s → error.unhandled,
  UI crashes → error.client (Next global-error boundary), both first-class rows.
- ✅ **Spend analytics** (`/admin/spend`) — RAVI'S ASK (Slack 2026-07-16, w/ Lee+Adrie,
  wanted before EOM): approximate tokens + cost by day/user/model, MTD vs
  `ADAM_MONTHLY_BUDGET_USD` + projection. "Definitive data to share" for usage-approval
  asks. Set the budget env var to light up the budget bar.
- ✅ **P1 Health banner** (`/admin/health`) — volume % (warn@75/crit@90), Anthropic key +
  live model-ID check (prefix-matched), 24h error count. Turns the runbook's 3
  predictable failures into pre-emptive pills. NOTE: volume at ~72% — prune soon.
- ✅ **P1 Assembly degradation** — plugin reports ⚠/✗ + slot shortfalls;
  assembly.completed carries degraded=bool; timeline shows amber. Catches Aug template
  drift (Elise/Zach) behind the green board count.
- ✅ **P2 Deploy log** — each Railway deploy → deploy.detected (sha+message), so behavior
  changes trace to code. **Digest** (`/admin/digest`) — period summary + Slack-pasteable
  text; automates Bree's manual change log.
- ✅ **P3 Issue aging** (stale >7d flagged) + workflow read (gate approvals + Gate-3
  picker usage, flags approve-without-picker).
- Wiki August runbook + where-things-live updated to document all new surfaces.

## Copy-quality closeout (2026-07-16 evening)
- ✅ **Distinct testimonial per concept** — brief quote used exactly once; other concepts
  invent distinct fictional people (verified 6/6 unique); DUPLICATE QUOTE + BRIEF-QUOTE LEAK
  review flags added. (Root cause of the "five faces, one name" board set.)
- ✅ **Feed-length fix** — `_fit_feed_fields`: overlong Meta feed fields (headline/body/
  description + per-audience copy) get one rewrite call (drop whole bullets/sentences, keep
  format) with a sentence-boundary trim fallback → feed fields deterministically <= caps
  BEFORE review, so selection compares cap-clean copy (dissolves the clean-vs-rank tension).
  Verified live: 0 violations across a 6-concept both-targeting run; bullets preserved.
- ⬜ **Elise (from the 9-board review):** Chat Bubble 1080×1920 template has old layer
  structure (placeholder "Small Business Wins" pill renders; opener lands in wrong bubble);
  Photo-with-Text light variant headline lozenge doesn't hug text ("Automate with a pro"
  overflow). + previous: Notification tile, Targeting pill layer.

## Figma assembly verified with the fixed plugin (2026-07-16, driven hands-off)
- ✅ **"Assembly complete: 2 of 2 boards assembled"** on the gate-3 sprint's manifest (4 rows,
  2 concepts × 2 targeting) — **1 board per chosen concept**; the -pros/-reta doubling is dead.
  Correct template placement (Photo-With-Text Dark variants) + copy panels filled.
- ✅ **CSV parser bug found & fixed in the process:** the plugin split rows on newlines BEFORE
  quote handling, so any quoted field with a line break (✅-bulleted Primary_Text_Long, review
  notes) tore the row and shifted every later column — silently corrupting copy on earlier
  assemblies too. Replaced with a character-walk RFC-4180 parser; verified against the real
  manifest (4 clean records).
- ✅ **Paste-the-CSV path added to the plugin UI** (textarea next to the file button) — same
  effect as choosing the file; enables keyboard/automation-driven assembly and is handy for
  humans too.
- ⬜ **Figma cleanup (Logan):** delete the two junk generations in "Generated Tests" — the
  36-board meeting run (old plugin) and one garbled 2-board run (pre-parser-fix, boards show
  CSV fragments as copy). The GOOD run is the most recent "2 of 2" generation.

## Gate-3 picker verified live (2026-07-16, sprint 2026-07-meta-74664fd049f9 — kept)
- ✅ **"Choose in ADAM before Figma" works end-to-end in production.** 2-style both-targeting
  run: 12 concepts generated → picker trimmed 6 pre-selected to **2 winners at gate 3**
  (`copy-select` HTTP 200, changed 4) → completed in 2m17s → manifest = **4 rows exactly**
  (2 picks × 2 targeting) instead of 12. Retargeting tone verified subtle ("Still searching
  for the right designer?" — nudge, no creeping). no_cta correct per mix (Testimonial none;
  Photo w/ Text's single shipped concept keeps its CTA). Guard also verified: 409 outside
  gate 3. Reliability dashboard: 2/2 clean runs.

## Meeting outcomes (2026-07-15 ADAM Working Session — Adrie, Bree, Logan)
- 📅 **TIMELINE: everything polished by Wed Jul 29** (copy + backend done by Wed Jul 22;
  29th–31st = Upwork migration/grace). August = Logan out (Bree keeps a change log; review
  end of Aug). September = align, apply fixes, platform expansion.
- ✅ **Retargeting tone SIMPLIFIED (Adrie):** subtle — "a super hint of coming back /
  revisiting / getting started", never "we know you've been here" creeping language (the
  platform decides who sees it). Prompt rules softened in both targeting branches.
- ✅ **Figma "239 concepts" explained + fixed:** the e2e assembly ran during the meeting;
  my -pros/-reta concept_tag suffixes doubled the board groups (18→36 → ~239 styled clones).
  Plugin now strips the suffix so a both-targeting pair lands on ONE board (feed copy ships
  via CSV); the Targeting pill reads "Prospecting + Retargeting" for merged groups. Both
  plugin copies updated (repo + ~/Documents live). ⬜ Re-run assembly to confirm 18 boards;
  also clean up the 36-board test output in Figma.
- ⬜ **Adrie sends updated reference PDFs this week** → swap into refs/ + `build_refs.py`.
- ⬜ **Adrie creating a standard Paid-Acq brief template** → wire into the order form's Brief
  helper when it lands.
- ⬜ **Wiki: team-facing "how to fix/change things" directions** (Bree) — verify coverage in
  the wiki + build an FAQ-style "most likely fixes" from the change log. (+ Logan reports odd
  wiki styling — audit in progress.)
- ⬜ **Admin access tiers** (dashboard vs engine): likely Lee = dashboard view; decision
  pending Lee (Bree adding to plan doc). Roles scaffolding already supports it.
- ℹ️ **Technical home = Haresh** (reviewing wiki/build now; multiple teams share the need;
  ~2 days heads-down to migrate). InfoSec call only after Haresh finishes discovery.
- ℹ️ **Motion:** Elise tests Figma Motion in August; designer conversation (After Effects vs
  in-ADAM vs Figma) = September. On-visual copy robustness = the Style Guide work (DONE —
  tell Adrie).

## E2E validation run (2026-07-15, sprint 2026-07-meta-c3bade5da2a7 — kept as evidence)
- ✅ **Full live sprint through the deployed app: COMPLETE in 6.4 min, zero errors.** 6 touched
  styles, Targeting = both, long brief w/ embedded quote. 18/19 checks passed on first run:
  chat=conversation, tweet=organic, brief quote used in a testimonial + FICTIONAL flag,
  sticky single-column populated + capped, CTA mix (1-with/2-without on Split Screen +
  Photo w/ Text incl. the subhead rule), manifest doubled 18 Prospecting + 18 Retargeting
  rows sharing creatives, no_cta column correct, reliability dashboard logged the run
  (100% clean, $0.42 tracked spend).
- ✅ **The 1 failure was a REAL gap, fixed same-night:** two Testimonial concepts shipped with
  feed copy over Adrie's caps (body_long 391>300 etc.) because `length_warnings` were
  recorded but never consulted at selection. Now soft-warned concepts are demoted in favor
  of clean ones (tiered backfill: clean → least-warned → never legal). Unit-verified both
  the failure scenario and yield protection. NOTE: the test sprint's manifest still contains
  the two warned concepts (pre-fix); flagged in its review notes.

## D. Product decisions (Logan + Ravi + Adrie)
- ✅ **Prospecting vs Retargeting differentiation.** DECIDED (Logan, Option A): one shared
  creative per ad, both text versions. Implemented in copy_gen: explicit per-targeting RULES
  in the prompt (Prospecting = cold/awareness/introduce; Retargeting = warm/familiar/convert);
  single targeting applies its own rules; **"Prospecting and Retargeting" generates a
  `targeting_copy` object** with distinct Prospecting + Retargeting headline+description, and
  the manifest expands each concept into a Prospecting row + a Retargeting row (same image,
  only feed copy + Targeting differ). Enforcement extended to the per-audience feed copy.
  Verified live: genuinely different angles ("Hire AI freelancers fast" vs "Still looking for
  AI expertise? You already know Upwork…"), emoji bullets present, manifest → 2 rows.
- ✅ **Emoji-bullet descriptions (~50%).** Already in the copy instructions (bullet/paragraph
  ~half-each, ✅/✔️/emoji-led). Examples: ADAM already loads Adrie's separate Prospecting +
  Retargeting example docs; live output produces the format.
- ℹ️ Adrie noted the legal self-flag on competitor-comparison copy is a human-in-the-loop
  solve — nothing to fix.

## E. Admin / usage / reliability (design in docs/admin-usage-design.md)
- ✅ **Phase 1 backend — reliability data spine, LIVE.** Railway Postgres provisioned +
  `DATABASE_URL` referenced into adam. `db.py` (best-effort, no-ops without DB) wired into
  `main.py`: `init_db()` on startup, logs `order.submitted` / `sprint.completed` /
  `sprint.failed` (terminal state, offloaded off the loop), `GET /admin/reliability` +
  `GET /admin/usage` (api-key gated). Deployed + verified end-to-end on the live backend: a
  test order logged `order.submitted` + `sprint.failed` and the incident surfaced with the
  real error; test data cleaned up. NOTE: the deploy runs `uv sync --locked`, so any
  pyproject dep change MUST be followed by `uv lock` + commit `uv.lock` or the deploy fails.
- ✅ **Reliability dashboard — LIVE at `/admin`** (adam-web). Clean-run rate (color-coded) +
  clean/failed bar, stat cards (runs started / completed / failed / active users), an
  incidents table (when · sprint · user · gate · error), and a usage-by-action breakdown.
  Reads `/admin/reliability` + `/admin/usage` server-side (key stays server-side); handles
  DB-off / backend-unreachable gracefully. Off the public nav (direct URL; gated with RBAC
  later). `lib/admin.ts` + `app/admin/page.tsx`. Verified live (empty-DB state renders).
- ✅ **More usage touchpoints + cost.** `log_event` now fires on `gate.approved` (approve
  handler), `chat.asked` (sprint chat), `learnings.edited` (learnings save), and
  `copy.generated` (at run outcome, from `token_usage.json`, with `cost_usd` at Sonnet-4.6
  pricing). `usage_summary` sums `meta.cost_usd` → **total spend** shown in the `/admin` Usage
  header. Cost aggregation verified against real Postgres.
- ✅ **Phase 2 — issue-report → learning loop, LIVE.** Backend: `POST /issues` (public capture),
  `GET /admin/issues` (queue + counts), `PATCH /admin/issues/{id}` (triage + "distill into a
  learning" → append to learnings.md + mark learned); `db.list_issues`/`update_issue`. Frontend:
  `/admin/issues` triage page (Reliability|Issues tabs), a "Report an issue" form, per-issue
  triage actions + a distill-to-learning box; API-route proxies (`/api/issues`,
  `/api/admin/issues/[id]`). Backend loop verified live (report → list → triage → cleanup).
  Scoreboard = the queue/counts shrink over time.
- 🔨 **Phase 3 — role scaffolding, LIVE (enforcement gated on SSO).** Role model (users.role
  admin|member) + management: `db.list_users`/`set_role`/`is_admin`/`ensure_admins` (seeds
  admins from `ADMIN_EMAILS` env on startup); `GET /admin/roles` + `PATCH /admin/roles/{email}`;
  a **Roles tab** at `/admin/roles` (list users, counts, make-admin/make-member toggle). Verified
  live (seed → list → flip → is_admin). **Still needs SSO** for per-route enforcement — today
  `/admin/*` is gated by the shared API key; `is_admin()` is the hook to wire in once a
  per-user identity exists. ACTION: set `ADMIN_EMAILS` on the adam service with Ravi + Logan's
  emails (or flip them in the Roles tab).

## Roadmap anchors (Adrie's doc)
- **July:** Logan UI + troubleshooting, final tests/fixes, updated ad examples, SMB copy bank,
  quotes handling, key-messaging template, technical home.
- **August:** updated copy instructions, template-size reuse audit, Paid Acq platform Qs,
  creative-team delivery grid, color + illustration additions.
- **September:** review August, apply fixes, extend ADAM to all platforms.

## 2026-07-21 — Ravi design/handoff review (punch list)
Reference = `upwork-adam.vercel.app` (Ravi's version). Handoff ~1.5 weeks out; Max (Upwork, via
Adrie's Slack) to get GitHub access + integrate. Design bar: pixel-perfect, "airy," everything
intentional. Full rationale + tokens now in `docs/DESIGN.md`.

**A. Homepage / global (DONE this session — deploying + verifying):**
- ✅ 4th entry card **Sprint runs → /sprints** (was 3, his has 4; 2×2 grid).
- ✅ 2nd hero CTA **Current sprints → /sprints** (outline pill).
- ✅ Marquee un-stack — row 2 runs PREVIEWS reversed (his technique) so no duplicates stacked on load.
- ✅ White **flashbang** → landing paints `#181818` first (scoped `:has(.adam-home)`).
- ✅ **Logo/nav jump** between pages → `html { scrollbar-gutter: stable }`.
- ✅ **`docs/DESIGN.md`** design-base spec (the "style markdown" Ravi + Logan asked for).
- ⏳ Remaining polish: nav padding/airiness, thin white outline on card icons, missing hover states,
  clickability affordances (e.g. clickable error rows must signal it), golden-ratio spacing pass.

**B. Nav & access (structural — role model already partly built, see Phase 3 above):**
- Two layers: **admin** vs **non-admin** (authorization middleware once SSO/identity lands).
- Non-admin nav = **New Order, Ask ADAM, Wiki** (Ask ADAM *before* Wiki). Everything else
  (Sprints, Sync Log, Learnings, Admin dashboard) behind a **profile icon** (top-right dropdown).
- Rename **Learnings → "Teach ADAM"**, make it tabbed; move **Quotes to a tab under it** (drop Quotes
  as its own nav item). "Everything we teach ADAM lives there."

**C. Issues → "Get help" (move out of admin):**
- Remove Issues from the admin dashboard. Add a **"Get help"** button (under profile icon, everyone
  can reach it) that opens issue submission. Route submissions somewhere real (Linear?) — **get
  destination from Adrie.**

**D. Admin dashboard upgrades:**
- Human-readable labels for gate approvals / activity action codes.
- Activity: **column headers** (the right-side code = the sprint).
- Spend: **per-model breakdown** (currently none), input tokens; keep month-to-date + projection.
- Landing = **overview dashboard** (top 4–5 things) then deep-dive w/ filters — **ask Adrie/Lee what
  they want first** (maybe spend). **PDF export** of the dashboard.
- Consistency: tabs/pills must not shift rows up/down; make Reliability clearer; icons on tabs.

**E. Wiki cleanup:**
- ✅ Repo-map "funky text" fixed (block-code pill bug).
- ✅ Glossary TODO + 7 other leaked `TODO:` notes removed; deploy page filled with real commands.
- ⏳ Sweep for **personal names** (Ravi wants them out — but ownership refs may be intentional; judgment pass).

**Open questions / Logan actions:**
- **Deploy target:** fixes are on our repo → Railway (`adam-web-production`). The Vercel
  `design-redesign` (cm-wonder) Logan views is SSO-walled + a different Vercel scope. Confirm what
  feeds it (repo/branch) so fixes land there too.
- **Max** GitHub access = Logan's action (can't add collaborators from here).

## 2026-07-21 — Adrie/Ravi/Bree working session (decisions + copy fix)
- ✅ **Copy-segmentation bug FIXED & shipped** (commit 3b2c72d). Root cause: copy-gen
  read the order-level `targeting` and only tripped the both-audience path when the
  string held both words; the batch form's per-concept `audience` defaults to "Both",
  which matched neither → every batch concept fell to single-audience → one copy set.
  Fix (`_generate_copy_for_style`): per-concept `batch["audience"]` wins for P&R orders,
  "Both" is normalized to the both-audience path, and a **backstop** flags any
  P+R concept that returns without a populated Prospecting+Retargeting `targeting_copy`
  (`targeting_incomplete` + ⚠ SEGMENTATION log). NEXT: confirm against Adrie's sprint
  links when they arrive; a P&R batch test run would verify end-to-end (token cost — flag first).
- **Access model DECIDED**: any company (Upwork) email can VIEW; admin rights (manage
  quotes/testimonials/config) restricted. Admins for redundancy: **Lee, Ruby, + engineering**.
  → matches the Phase-3 role model; still needs the SSO/identity hook to enforce per-user.
- **Issues** confirmed = manual catalog (not auto-repair) ✓. **Dashboard metrics** they
  want (clean-run rate, spend, runs, incidents, sprint activity, MTD, digest) ✓ all present.
- **Billing PRE-APPROVED by Lee** — Logan can bill all project expenses, no recurrent
  approval. (Separate from the standing "flag API-token spend with a number" working pref.)
- **Max** = `maxkarasso@cloud.upwork.com`, the Upwork engineer taking over migration.
  Logan to add via GitHub web UI (Settings → Access → add by email). Avoid making the
  private repo public (the meeting's fallback idea) — exposes all history.
- Adrie to email 4 docs (testimonials, updated ad examples, copy-update processing,
  retargeting examples) + the copy-bug sprint links → ingest into `refs/` when they land.

## 2026-07-21 — dashboard/nav "do everything" pass (SHIPPED)
Worked Ravi's list top-down; all live on Railway + verified:
- ✅ **Tab consistency + icons** — shared fixed-height `AdminHeader` (tabs no longer jump
  between pages) + an icon per admin tab (b867d2d).
- ✅ **Nav restructure** — top nav = New Order · Ask ADAM · Wiki; the rest (ADAM Dashboard,
  Sprint runs, Sync Log, Teach ADAM, Get Help) behind a **profile-icon dropdown**. Role-gating
  (hide dashboard from members) still needs SSO/identity — the Phase-3 role hook is ready (3cb5325).
- ✅ **Learnings → "Teach ADAM"** with **Quotes as a tab** under it (dropped from top nav) (3cb5325).
- ✅ **Issues → "Get Help"** — moved out of the admin dashboard to everyone-accessible `/help`
  (report form + queue); Issues tab removed; `/admin/issues` redirects to `/help` (297de17).
- ✅ **PDF export** on the Digest (browser print-to-PDF + print stylesheet) (80671ff).
- ✅ **Reliability verdict line** — plain-language "all clean / N failed" at-a-glance (80671ff).
- ✅ **Copy segmentation** fix + **operator sees both audience versions** at Gate 3 (earlier commits).
- 🟡 **Per-model spend** — plumbing verified working; populates on the next real run (empty-state honest).
- ❌ **Overview landing page** (top 4-5, then deep-dive) — Ravi wants Adrie/Lee's input on what lands first.
- ⏸ **Wiki personal names** — the remaining names are legitimate ownership/handoff attribution
  (esp. 14-handoff.md); blanket removal would gut the handoff doc. Recommend keeping; genericize on request.

## 2026-07-22 — Adrie's 3 revised reference docs INGESTED (commit f3e6721, deployed healthy)
Per Adrie's 07-21 email ("3 of these are revisions of docs already attached to ADAM that
need to be replaced with these new versions"), exported all 3 Google Docs to text and
swapped them into `refs/`:
- ✅ **Prospecting** ad copy examples → `refs/Prospecting ad copy examples Updated 7-2026.txt`
  (22.7K; 30 categories, 5-field format Primary_Text_Short/Long · Text_On_Visual · Headline_Short/Long).
- ✅ **Retargeting** ad copy examples → `refs/Retargeting Ad copy examples Updated 7-2026.txt` (20.2K).
- ✅ **SMB Copy Bank Phase 3** (was Phase 1) → `refs/SMB Copy Bank_Phase 3_Final.txt` (9.8K;
  Perception/Trust structure — headlines, subheads, short copy, sourced customer quotes).
- `build_refs.py` REF_FILES remapped to the 3 new filenames; `refs_context.json` recompiled
  (13/13, `prospecting_examples`/`retargeting_examples`/`smb_copy_bank` all confirmed holding new
  content). Old versions left in refs/ (no longer referenced). Backend redeploy = 5/5 healthy.
- ↪ This resolves the 07-21 "Missing refs from Adrie" + "ingest 4 docs when they land" items
  (the 4th, client testimonials, was already ingested into Approved Quotes on 07-21).
- ⬜ NOTE for Adrie: the docs are NOW live in ADAM (they weren't before this) — copy runs from
  today forward calibrate against the July versions.

## 2026-07-22 — Copy-segmentation fix VERIFIED against Adrie's two real sprints ✅
Queried the Railway backend (authed) for Adrie's two flagged P&R sprints. Both are
real orders (brief "Sprint 10: Outcome Alignment"), targeting = "Prospecting and
Retargeting", both batches `audience: "Both"` — i.e. the exact scenario that used to
collapse to one copy set. Copy generated 2026-07-21T18:48 (post-fix). Result:
- `2026-07-meta-423b11dfe7f1`: **36/36 concepts** carry both a Prospecting AND a
  Retargeting block; **36/36 DISTINCT** (0 identical-both-slots).
- `2026-07-meta-0a18955bdb28`: **36/36 both-populated, 36/36 DISTINCT**.
- Tone is genuinely differentiated, not duplicated — Prospecting = cold value-prop
  ("Build chatbot support faster on Upwork" / "Fractional experts. Full-time results.");
  Retargeting = subtle return framing ("Ready to build that chatbot?" / "Still need that
  senior hire? Try fractional."), matching the "hint of coming back" tone Adrie asked for.
- ↪ Closes the 07-21 "confirm against Adrie's sprint links" NEXT item. No test run / API
  spend needed — her live gate-3 sprints already prove it end-to-end.

## 2026-07-22 — Truncation fix: feed-fit fallback never leaves a mid-sentence stub ✅
Adrie flagged body copy being cut mid-sentence. Root cause was NOT the LLM feed-fit
rewrite (it already drops whole sentences) but its deterministic fallback `_smart_trim`
(hit when the rewrite call errors or a field is still over cap): it word-cut whenever the
last complete sentence ended before the halfway mark → dangling stub ("...who integrate
with your"). Rewrote `_smart_trim` to (1) end on a complete sentence/bullet/line keeping
>=50% of cap — clean, no ellipsis; (2) else word-cut + ellipsis so the break reads as
intentional; (3) convert a dangling "...who:" intro to an ellipsis. Always <= cap;
re-runs length + legal guardrails. Verified vs the stub case + 7 edges. Commit 8442437.
