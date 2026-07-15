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
- ⬜ **End at Submit — submitters can't reach `/sprints`.** Paid Acq copies the request link
  into Slack. Ties into the admin RBAC work (member role). Gating `/sprints` is a quick win
  even before full roles.
- ⬜ **Add Key Messaging themes into the Additional Info area** (Sprint 9: AI + Specialization
  block — top L1/L3 categories, hypothesis, sample copy). Prefill/help text in the form.
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
- ⬜ **Prospecting vs Retargeting.** The July instructions say generate **separate labeled
  concept sets** when Targeting = "Prospecting and Retargeting". ADAM currently only feeds
  one example set as context (picks Prospecting when both are present) — it does NOT honor
  the split. Decision: implement the labeled split, or accept "one request → a prospecting +
  a retargeting version in the same style"?
- ℹ️ Adrie noted the legal self-flag on competitor-comparison copy is a human-in-the-loop
  solve — nothing to fix.

## E. Admin / usage / reliability (separate build, design in docs/admin-usage-design.md)
- 🔨 Phase 1: Postgres + usage_events + reliability view. `db.py` written; not yet wired into
  the pipeline touchpoints. RBAC (member/admin) phase absorbs B's "submitters can't see sprints".

## Roadmap anchors (Adrie's doc)
- **July:** Logan UI + troubleshooting, final tests/fixes, updated ad examples, SMB copy bank,
  quotes handling, key-messaging template, technical home.
- **August:** updated copy instructions, template-size reuse audit, Paid Acq platform Qs,
  creative-team delivery grid, color + illustration additions.
- **September:** review August, apply fixes, extend ADAM to all platforms.
