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
- ⬜ **Phase 3:** RBAC (admin/member) — absorbs B's "submitters can't see sprints"; Roles tab; SSO.

## Roadmap anchors (Adrie's doc)
- **July:** Logan UI + troubleshooting, final tests/fixes, updated ad examples, SMB copy bank,
  quotes handling, key-messaging template, technical home.
- **August:** updated copy instructions, template-size reuse audit, Paid Acq platform Qs,
  creative-team delivery grid, color + illustration additions.
- **September:** review August, apply fixes, extend ADAM to all platforms.
