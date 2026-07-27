# Adrie's expected output per run ("Looking to receive", 7/27 issue tab)

For EVERY ad style requested, a run must deliver:

1. **Top 2 copy choices per audience** — 2 for Prospecting AND 2 for Retargeting per ad
   style (currently ADAM surfaces top 1 per audience → GAP, needs selection change).
2. **Long and short body copy** — ~50% of long-body versions as bullet lists with emojis /
   checkmarks (✅ shipped: deterministic 50/50 split, 2026-07-27).
3. **Long and short headlines** (✅ was the nested-feed bug; fixed 2026-07-27).
4. **On-creative copy matching every ad style type** (✅ same nested-feed bug; fixed).

Her 7/27 failing run: 2026-07-meta-a660373837cd (6 styles: Notification, Talent Profile,
Text with Button and Cursor, Tweet / Post Mockup, Poll, Sticky Note; Sprint 1 brief).
Root cause of items 3+4 and "no body copy on Tweet": model nested feed copy under
targeting_copy.{aud}.feed.* — reader-side fix (_flatten_audience) deployed 2026-07-27.

## Her P&R craft definition (from her Claude project instructions)
"If Targeting is 'Prospecting and Retargeting': Generate separate concepts for each,
clearly labeled. Prospecting concepts should focus on awareness and first impressions.
Retargeting concepts should acknowledge familiarity and drive toward conversion."

## Her craft exemplars (Do column)
- "Post a job today. Get proposals by tomorrow."
- "Find the right fit — on your terms."
- "Your next hire is already on Upwork."
- "Whatever the project, there's a freelancer for it."
- "Need a developer this week? They're already on Upwork."

## Naming note (her comment)
ADAM's "Creative Headline" == her "Text_On_Visual". Keep the mapping stable in review CSVs.

## New/open asks from her issues tab (2026-07-27)
- Order form Browse dropdown: pull thumbnails for Notification + Bespoke styles from Figma
  (Notification tile is blank).
- Order form should END at submit — requesters must not access sprints; Paid Acq will
  copy the request link into Slack instead.
- Chat Bubble on-visual should read as one CONVERSATION (not headline-bubble + chat-bubble).
- Tweet / Post Mockup on-visual reads like a headline; should read like a tweet.

## Her refs updates landing Friday (replaces our stale refs)
- Prospecting ad copy examples Updated 7-2026 (PDF)
- Retargeting ad copy examples Updated 7-2026 (PDF)
- SMB Copy Bank Phase 3 Final (PDF)  [ours is Phase 1]
- Quotes/testimonial instructions (WIP)

## Timeline (her To-dos tab)
- FRI 7/31: final tests+fixes, updated example docs; MON: her key-messaging template test;
  THU: Sarah R briefing-workflow call. AUG: platform expansion (Elise builds all platform
  templates, first 2 wks); Aug 4 placeholder: quick-drop CSV for deliverables grid.
  SEPT: Logan applies platform updates.
