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
- ✅ **Tweet reads too headline-y** (Adrie #2) — CONFIRMED via 2026-07-23 live sprint. Entry #19 (organic post) now reaches the
  model untruncated + can run to 115 chars — expected to resolve. **Confirm with a live run.**
- ℹ️ **Tweet has no dedicated on-image field** — its ~115-char post currently maps to
  `creative_headline`. Works, but a dedicated `tweet_text` field (like Chat Bubble's fields)
  would be cleaner. Minor follow-up.
- ⛔ **True two-bubble Chat Bubble layer** — a real field rename (chat_bubble_1/2) touches
  the Figma template layers + plugin mapping + manifest columns. Needs Elise. The content
  reframe above is the safe interim; revisit if the template renders bubble 1 as a header.
- ✅ **Naming: "Creative Headline" vs `Text_On_Visual`** — aligned. The Gate-3 review CSV now
  labels the on-image copy `Text_On_Visual` / `Text_On_Visual_Subhead` (Adrie's copy-spec
  term), matching her doc and disambiguating from the FEED `Headline`. The Figma manifest
  keeps `Headline_On_Creative` (layer name, machine handoff). run_pipeline.py copy_review builder.

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

## 2026-07-22 — Key-messaging brief template BUILT + browser-verified ✅ (commit 361189c)
Adrie's briefs now have a structure that maps 1:1 to the Additional-Info breakdown schema.
- **New Order → Review step**: "+ Insert brief template" button drops a 4-section skeleton
  (THEME / COPY MUST-DOs / DESIGN DIRECTION / RESOURCES) into the Brief field; headers align
  to `_breakdown_brief`'s theme / copy_directives / design_directives / resources so the
  breakdown is near-deterministic. Button toggles to "✓ Template inserted"; textarea grows.
- **docs/brief-template.md**: canonical reference — form-vs-brief boundary table (quantity /
  audience / sizes stay in the form; brief only steers content), what each section becomes
  downstream, and a filled example.
- Verified live on adam-web (Railway): drove New Order → Details → Creative(Copy Only) →
  Review, clicked Insert, confirmed all 4 sections render in the textarea + button toggled.
  (Did NOT submit — no junk sprint created.) Frontend deploy confirmed live via the browser
  after curl/bundle checks were inconclusive (the /new page is client-rendered).

## 2026-07-22 — Nav hover + homepage cards: exact parity with Ravi (harvested from live DOM)
Reverse-engineered Ravi's reference (upwork-adam) via computed styles + extracted SVGs, then matched:
- **Nav hover** (commit 22387ef): items were text-color-only on hover. Ravi's are padded rounded
  pills that fill with a subtle bg on hover (`bg-white/10` dark / `#f7f8f6` light) + text to full,
  and the active underline is an inset green `::after` bar (2px, inset 12px, rounded) — NOT a
  full-width border-b. Rewrote linkClass to his exact spec (px-3 py-1.5, text-[13.5px], gap-1).
  Verified live: hovering "Wiki" shows the pill fill; "Home" keeps the green inset underline.
- **Homepage cards** (commit a0adbb4): container styling already matched (gradient/border/shadow/
  icon-wrap). Real diffs were the ICONS (mine were hand-drawn approximations) → swapped to Ravi's
  exact Lucide markup: layout-grid (was layers), message-square-text (was plain bubble), book-open,
  plus. Also matched hover: featured card no longer lifts (border-brighten only), non-featured cards
  lift + no phantom hover-shadow. Verified live: all 4 icons + featured green wash match #237.
- METHOD NOTE: everything harvestable from Ravi's live site (SVG paths, computed gradients/shadows,
  hover classes). The one accelerator for future parity work = read access to his upwork-adam repo.

## 2026-07-22 — Systemic Tailwind v4 shadow bug fixed (4 "not the same" reports) ✅
Root cause of the homepage-cards / Ask ADAM / Wiki / New Order "these aren't the same"
batch: Tailwind v4's class scanner mis-tokenizes an arbitrary `shadow-[a,b]` value at the
comma BETWEEN layers, so the class is never generated → box-shadow renders TRANSPARENT.
Verified: the homepage featured card's computed box-shadow was rgba(0,0,0,0). This flattened
every multi-layer shadow: featured-card green glow, Ask ADAM cards/input, New Order panels,
Wiki content article. Fix (systemic, commit 184a8f7): 3 plain unlayered CSS utilities in
globals.css (elevate-1, elevate-2, glow-featured) + swapped all 6 broken usages. Single-layer
shadow-[…] (no inter-layer comma) still works, left as-is.
Verified live (computed styles):
- Home featured card boxShadow = rgba(20,168,0,.16) 0 0 0 1px, rgba(20,168,0,.42) 0 30px 80px -30px ✅
- Ask ADAM suggestion card = rgba(0,0,0,.04) 0 1px 2px, rgba(0,0,0,.05) 0 4px 12px ✅
- Wiki content <article> = same elevate-1 ✅
Also: New Order now defaults BOTH audiences selected (was none) — matches Ravi ✅ (verified).
NOTE on "white borders": the non-featured cards' 1px rgba(255,255,255,.1) border already
matched Ravi exactly; the real gap was the featured card's missing glow (same shadow bug).

## 2026-07-23 — Live copy-only smoke sprint (2026-07-meta-d5cc) — engine changes VERIFIED end-to-end
Ran a real copy-only P&R sprint locally (deployed code + refs, service env injected; stopped at
Gate 3 — no image/Gemini spend, no deployed-DB sprint). Cost: $0.22 (7 Sonnet calls). Results:
- ✅ **Segmentation**: 12/12 concepts both-audience, 12/12 DISTINCT P vs R — on a fresh sprint.
- ✅ **Brief-breakdown (Additional-Info)**: structured brief → theme + 3 copy + 2 design directives,
  high-touch; directives measurably shaped copy (the "contrast slow hiring" directive appeared).
- ✅ **Truncation fix exercised LIVE**: feed-fit trimmed 20+21 fields; trimmed bodies end on
  complete bullets or the `…` marker (3) — zero mid-sentence stubs.
- ✅ **Tweet conversational** (Adrie #2): "You could be reviewing proposals by friday" — a post,
  not a headline. Closes the "confirm with a live run" item.
- ✅ **Refs**: 13 docs incl. the new July examples loaded; "using both example sets" for P&R.
- ✅ Legal + length guardrails fired correctly.
- ↪ Surfaced a gap: the SYNTHESIZED Gate-3 review (get_copy_concepts, shown before delivery)
  still used `Headline_On_Creative` + mapped the feed headline → fixed to `Text_On_Visual` from
  `creative_headline` (commit 5eb2287). Completes the #5 naming alignment across ALL surfaces.

## 2026-07-23 — ADAM Working Session (Adrie/Bree/Ravi/Logan): backlog + fixes
Aligned decision: **Prospecting and Retargeting must each get their OWN creative content.**
Needs-discussion: Sept engineering timeline (Haresh not ready till end of next week; team off
in Sept) → Monday call w/ Lee+Ruby, possible Logan extension.

SHIPPED this session (all live on Railway, verified):
- ✅ **Emoji** green-checkmark bug → varied, content-apt emoji from the full library (a546c58).
- ✅ **Resolve Styles** — Graphic-with-Text emitted an off-spec subhead → headline-only ad types
  now strip it (e80468b).
- ✅ **Fix Copy / fatigue** — 6-in-one call hit the max_tokens ceiling → later concepts truncated/
  scrawny. Now small angle-seeded sub-batches (COPY_BATCH_SIZE), each full budget (058f1dd).
  Verified: 12/12 concepts full, diverse.
- ✅ **Separate P&R creative** (aligned decision) — unique on-visual copy per audience end-to-end:
  generation (Part A, 2bc6359) + manifest boards + review columns (Part B, 99bf40b). Verified
  12/12 distinct Text_On_Visual.
- ✅ **Self-heal** — overlong ON-IMAGE copy (creative_headline/subhead) was flagged not fixed →
  now rewritten to fit via the feed-fit pass (3adcdcf). Verified: 0 unresolved length flags.

OPEN (Logan / code):
- ⬜ **#3 Surface long + short headline** in review/deliverable (data has both; web copy-picker
  shows only one, no P&R split).
- ⬜ **#4 Update Digest** → recap of what the RUNS did (orders/outputs), not a list of git deploys
  with cryptic names (Adrie: top section not decision-useful).
- ⬜ **#5 Remove Sprint 9/10 theme chip** from the intake form (wasn't meant to go live).
- ⬜ **Gate-2 brief-placeholder flag** — Adrie confused where theme/copy-must-do/design/resources
  live; she's adjusting her template, smooth the flag/messaging.
- ⬜ **Testimonial false-fictional flag** — flagged a REAL library testimonial as fictional (monitor).

NOT code (Logan): invite Sarah (Thursday, review the additional brief section); Monday Lee/Ruby
call re: Sept timeline + extension (owns Railway accounts + incident response = why present).

## 2026-07-23 (cont.) — autonomous sweep of remaining open items
SHIPPED:
- ✅ **#4 Digest → run recap** (5566b88) — leads with "This period's runs" (driver/platform/
  targeting/styles/deliverable per order); deploys demoted to collapsed "Technical changes".
  Verified: digest API returns 8 runs.
- ✅ **#5 Remove Sprint chip** (d1d62cc, deployed w/ the #4 frontend build) — emptied
  KEY_MESSAGING_THEMES; chip row hides when empty. Code-correct + typechecked; visual confirm
  blocked by a flaky form interaction (worth a 5-sec eyeball).
- ✅ **#3 long/short headline + P&R split in review** (d1d62cc) — copy picker shows feed
  headline long+short and a Prospecting/Retargeting block. Verified data flow.
- ✅ **Testimonial false-fictional flag** (9420016) — match on substring OR content-word
  overlap so a legitimately SHORTENED real quote isn't tagged fictional. 6/6 cases pass.
- ✅ **Gate-2 placeholder flag** — _breakdown_brief now strips unfilled brief-template
  placeholder lines so an un-edited section isn't parsed as direction (rest = Adrie's template).

FLAGGED (identified, deferred — need coordination or are risky to rush):
- ⬜ **Style-guide conditional caps** (Split Screen 49/65, Lifestyle 80/100, Platform UI +16):
  ADAM enforces the looser no-CTA cap; the tighter with-CTA cap needs CTA-aware enforcement,
  but CTA assignment happens AFTER ranking (cta_mix) — needs an enforcement-timing change.
- ⬜ **Style-guide combined caps** (Social Media 65 combined; Sticky double-col 136): ADAM caps
  per-field (Social 60+60=120; Sticky 180) so the COMBINED can exceed the design space. Needs a
  combined-cap field in the JSON + summed-length enforcement + feed-fit support.
- ⬜ **Style-guide missing/extra fields** (Us-vs-Them wrap-up line; Social name/title should NOT
  be generated; Poll needs a headline not options) — changes what ADAM generates; confirm the
  Figma templates have/lack those layers with Brandon first.
- ⬜ **Adrie (not code):** variant-model sign-off; Freelancer Work Categories.pdf; brief-template
  reconciliation (mine vs hers).

## 2026-07-23 (cont.) — read Adrie's actual Test Brief + combined-cap enforcement
- Read the real ADAM Test Brief (Logan sent it as PDF). RECONCILED: every open issue in it is
  addressed — theme chip (#5), Gate-2 placeholder note, short+long headline (#3), fatigue/
  self-flag (fatigue + self-heal), Graphic-with-Text subhead, and "P&R body copy but not on-
  creative visual copy → distinct creative for all" (P&R creative). Struck-through items (chat
  bubble, Tweet, manifest stalling, handoff flow, FAQ/diagnose) were already resolved. The
  spec's caps (125/300/30/50) match what ADAM enforces.
  - ↪ Highlighted note "need bullet points in SOME long copy versions" — handled by the LONG
    PRIMARY COPY FORMAT rule (mix of bullet+paragraph required); worth a variety spot-check.
- ✅ **Style-guide combined caps ENFORCED** (Logan approved): Social Media columns ≤65, Sticky
  Note double-column ≤136. Added `combined_caps` to the JSON + `_enforce_combined_caps` (sums
  the fields, proportional deterministic trim to fit). Verified: Social 92→53, Sticky 154→108.
- DECISIONS: brief template → defer to Adrie's (mine stays until hers lands); emoji → keep the
  varied professional palette until something else is requested.

## 2026-07-23 (cont.) — Mount MCP into Railway (retire stale Fly connector)
- ROOT CAUSE: the claude.ai MCP connector talked to adam-pipeline-cm.fly.dev, whose
  server reads a runs/ folder BAKED INTO its Docker image (frozen ~May). So the
  connector showed April/May sprints while Railway's live pipeline is all July.
  Railway served no MCP endpoint (main.py only mounted /fonts). Verified: MCP
  list_sprints returned 2026-04/05 sprints; Railway /admin/storage all 2026-07.
- FIX (Logan chose "Mount MCP into Railway"): mounted the FastMCP streamable-http
  app at /mcp inside main.py so the SAME tools read Railway's live /data/runs + env.
  - mcp_server/server.py: RUNS_DIR now env-overridable (reads RUNS_DIR → /data/runs
    on Railway; unchanged for Fly/local). Added the Railway host to allowed_hosts.
  - main.py: load server.py by path, streamable_http_path="/", mount at /mcp,
    compose adam_mcp.session_manager.run() into the lifespan (required or every
    call 500s), pure-ASGI _MCPAuth gate (?auth= / Bearer vs MCP_AUTH_TOKEN ||
    PIPELINE_API_KEY). pyproject.toml: added mcp>=1.27.0.
  - Canonical endpoint is /mcp/ (trailing slash; /mcp 307-redirects to it).
  - VALIDATED locally before deploy: isolated mount proof + full real-main.py boot
    (health 200, bad-token 401, 7 tools, list_sprints reads live runs). PASS.
- FOLLOW-UP for Logan: repoint the claude.ai connector to the Railway /mcp URL
  (auth token = PIPELINE_API_KEY) and delete the Fly app. Connector auth currently
  reuses PIPELINE_API_KEY; set a dedicated MCP_AUTH_TOKEN later to stop embedding
  the admin key in the connector URL.

## 2026-07-23 (cont.) — MCP mount LIVE + docs synced
- ✅ VERIFIED LIVE: https://adam-production-9618.up.railway.app/mcp/ returns 7 tools
  and current July sprints through the claude.ai-style handshake (was stale April/May
  Fly data). New deploy came up ~30s after the lockfile fix.
- ✅ Docs updated to match: in-app wiki (02-architecture, 03-repo-map, 08-deployment-
  and-ops, README — both web/content/wiki + docs/wiki mirrors), CLAUDE.md §4 + status +
  quickstart + current-state + pointers, and an OUTDATED banner on
  docs/architecture_and_logging.md (that doc predates Railway wholesale — needs a full
  rewrite, flagged separate).
- FOLLOW-UPS (Logan): (1) repoint the claude.ai connector to the Railway /mcp/ URL;
  (2) delete the Fly app adam-pipeline-cm once the connector is flipped; (3) optional:
  set a dedicated MCP_AUTH_TOKEN so the connector carries a purpose-built token, not the
  admin PIPELINE_API_KEY; (4) full rewrite of architecture_and_logging.md; (5) in-app
  wiki text goes live on the next adam-web deploy (source committed now).

## 2026-07-23 — Full-style regression (Phases 1 & 2)
- **PHASE 1 — copy, all 24 styles (copy-only, P&R "both", 4-section brief):** 23 pass · 1 warn
  · 0 FAIL · 144 concepts · **$2.86**. Every style generated; hard caps respected on selected
  concepts; combined caps (Social/Sticky) held; headline-only styles carry no subhead (strip
  works); P&R distinct; emoji varied; no dangling. Copy is FULL-LENGTH (fill: creative_headline
  97%, body_long 94%, body_short 87%, headline 85%) and brief-adherent (said "AI-skilled" 24/24,
  "AI expert" 0/24, "48 hours" 24/24). Quality reads well across styles.
  - warn: Us vs Them — 2 UNSELECTED alt concepts have a bullet 29>28 (selected ones clean).
  - caveat: description field (25-char cap) truncates with an ellipsis ~4/24.
- **PHASE 2 — image path + manifest, all 24 styles ($0 metered, Figma API only):** routing
  correct (8 skip · 8 background · 6+1 library · 3 gemini); design-direction appended to 3/3
  gemini prompts; Figma library lookup filled 26 asset picks; **P&R manifest doubling 26→52
  rows**, on-image distinct 25/26, feed 20/26; copy_review P&R columns 140/144 filled + distinct.
  Sample P&R pair genuinely differentiated (Prospecting "find fast" vs Retargeting "right now").
  - NOT exercised: actual Gemini pixel render (stage 04) — unchanged code, prompts verified.
- **NEW FOLLOW-UPS (small):**
  1. description-field (25-char) ellipsis truncation — teach it to write a complete short fragment.
  2. occasional identical P&R copy — 1/26 on-image, 6/26 feed share a line (structure fine; model
     nudge).
  3. **Gemini image cost is NOT tracked** — `_estimate_cost` prices text models only, so
     `/admin/spend` under-reports any image-generating run. Add a per-image estimate.

## 2026-07-24 — Long-body 50/50 bullet-vs-paragraph enforcement (Logan)
- FINDING (from Phase 1 samples): body_long came out 100% bulleted (112/112). The
  "required variety" instruction was soft and the model ignored it.
- FIX: deterministic per-concept format assignment in `_generate_copy_for_style` —
  each concept's body_long format assigned by GLOBAL index parity (even→emoji-bulleted,
  odd→flowing paragraph), injected into the prompt; refs instruction rewritten to
  "format is assigned per concept, follow exactly" + recompiled.
- VERIFIED: 4 previously-100%-bulleted styles regenerated → each 3 bullet / 3 paragraph,
  total 12/12 (was 0 paragraph), $0.27. Both formats high quality. Resolves the earlier
  "bullet-format variety" follow-up.

## 2026-07-27 — Sonnet 5 switch + TWO root-cause bug fixes
- **Sonnet 5 (Logan/call request):** switched copy-gen to claude-sonnet-5 via env-overridable
  _COPY_MODEL (ADAM_COPY_MODEL). BUT the naive swap BROKE copy gen: Sonnet 5 auto-thinks on
  complex prompts and returns a THINKING block as content[0], while the pipeline read
  content[0]["text"] -> KeyError -> all styles failed -> 0 concepts. FIXED with _response_text()
  (extracts the text block regardless of leading thinking block); 5 call sites routed through it.
  Re-verified: Sonnet 5 now generates all concepts. COST CAVEAT: thinking tokens make Sonnet 5
  ~2-3x the copy cost of 4.6 ($0.78 vs ~$0.27 for 3 styles) — the call assumed same/lower; the
  thinking changes real cost. Can disable thinking to cut it, at a possible quality tradeoff.
  Chat agent pinned to Sonnet 4.6 (ADAM_CHAT_MODEL) — thinking+tool-loop interaction untested.
- **Adrie's "empty body copy" bug (the active fire):** for P&R "both" runs the model
  INCONSISTENTLY nests feed copy under targeting_copy.{aud}.feed.{field} instead of flat, and the
  mirroring + manifest + review code only read the flat location -> empty body/headline fields.
  Matched her report exactly (Tweet 0/6, Notification 2/6, Talent Profile 4/6, Poll/Sticky 6/6;
  "different every time" = model varies flat vs nested). FIXED with _flatten_audience() applied at
  all 3 read sites. Verified against her real run a660373837cd: 12/12 empty-body concepts recover.
  FOLLOW-UP: also tighten the prompt so the model stops nesting under "feed" (source fix).

## 2026-07-27 (cont.) — Copy-CRAFT rewrite + Sonnet 5 config decision
- CONTEXT: Logan flagged that "Hire in 48h" is weak ad copy regardless of metrics. Fill/
  completeness are table stakes; the headlines had no craft. Root cause: the prompt is
  ~40k chars of compliance/legal with almost no push for craft, so the model played it
  safe and literal, restating the brief instead of selling it.
- FIX 1 — CRAFT BAR: added a craft directive at the TOP of the copy prompt (before the
  compliance wall): interpret don't restate, every headline needs a hook, distinct angle
  per concept, flat-vs-sharp exemplars (incl. "Hire in 48h" as an anti-example). Dramatic
  lift, validated across all 24 styles ("The role you've been stuck on? Filled", "Skip the
  bad-hire tax", "Finally automated the thing I kept putting off").
- FIX 2 — MODEL/THINKING DECISION (data-driven, 3-way A/B on all 24 styles):
  4.6 = $4.69, 23/24 clean, more varied headlines. S5 thinking-ON = $7.00. S5 thinking-OFF
  = $2.53 (CHEAPEST + 24/24 clean). Thinking adds ~3x cost with NO copy-quality gain once
  the craft prompt is in place. DECISION: Sonnet 5 + thinking OFF (ADAM_COPY_THINKING=off
  default) + craft prompt. Toggle env-overridable per call.
- FIX 3 — CASING: _to_sentence_case was lowercasing proper nouns ("friday"). Refs prompt
  fix got ~70%; added a DETERMINISTIC backstop (_fix_proper_nouns / _fix_concept_proper_nouns)
  that re-capitalizes days + Upwork AFTER sentence-casing. Verified 0/18 lowercase days.
- BILLING NOTE: heavy test-run day drained the Anthropic key mid-testing (400 "credit
  balance too low"); Logan topped it up. Be economical with test spend.
- FOLLOW-UPS: "by Friday" over-used across styles (partly the narrow test brief — a varied
  brief spreads it out; maybe a prompt nudge); Sticky Note 12-char title cap forces fragments
  ("Work…") — Adrie/Brandon design call; structured-output rebuild (robustness, step 3);
  chat agent still on 4.6 (ADAM_CHAT_MODEL).

## 2026-07-27 (cont.) — Adrie's doc explored (browser) + varied-brief validation
- EXPLORED her ADAM Test Brief gdoc (all 7 tabs) + her Sprint 9/10 reference copy deck via
  the Work-profile browser. Everything captured to docs/adrie-materials/ (expected-output
  spec, all 5 real key-messaging briefs, her brief TEMPLATE, her P&R definition + craft
  exemplars, her open issues, her Aug/Sept timeline).
- Her 7/27 failing run = a660373837cd = the nested-feed bug (FIXED earlier today). Her
  "brief section is the culprit" hunch resolved.
- NEW asks surfaced: (1) TOP 2 choices per audience per style (ADAM surfaces top 1) —
  selection change; (2) order form ends at submit (requesters can't browse sprints);
  (3) Browse thumbnails for Notification + Bespoke from Figma; (4) Chat Bubble = one
  conversation / Tweet reads like a tweet (craft nudge); (5) her updated refs land FRI
  (Prospecting/Retargeting examples 7-2026, SMB Copy Bank Phase 3) — re-ingest then.
- ✅ VARIED-BRIEF TEST (her real Sprint 10 + Meet-the-Moment briefs, P&R both, 6 styles,
  $1.66): craft HOLDS on real themes — Sprint10 output is outcome-led ("She built their
  pipeline in weeks", "This site converts. Built in days"), MTM is cost/control-led ("Only
  pay for work you need", "Nobody talks about how much a bad hire actually costs").
  Time-hook repetition collapsed to 1/8 per run (toy-brief artifact CONFIRMED). P&R feed
  36/36 present + 36/36 distinct on both runs (nested-feed fix verified on real briefs).
  Chat Bubble now reads conversational ("Budget's tight this qtr") — matches her ask.
  Sticky Note title still fragments ("Site…") — the 12-char cap decision stands (Adrie/design).
