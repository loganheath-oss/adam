# ADAM ← Hightouch Integration Spec

Last updated: 2026-05-29

This is the spec for connecting Upwork's Hightouch instance to ADAM as a
**custom HTTP destination**. When a row in your warehouse signals "produce
creative for this brief," Hightouch POSTs to ADAM, ADAM creates a sprint,
and the pipeline starts running.

## TL;DR for the data team

- **Destination type:** Custom HTTP / Webhook
- **Endpoint:** `POST https://<adam-host>/integrations/hightouch/brief`
- **Auth:** `Authorization: Bearer <HIGHTOUCH_API_KEY>`
- **Payload shape:** flat JSON, schema below. Map warehouse columns directly to fields.
- **Idempotency:** include an `external_id` per row; re-syncs of the same row return the existing sprint.

## Endpoint surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/integrations/hightouch/brief` | Create a sprint from a Hightouch row |
| `GET`  | `/integrations/hightouch/health` | Health probe (use for sync verification in the Hightouch UI) |
| `GET`  | `/integrations/hightouch/by-external-id/{external_id}` | Look up the sprint created for a given row |

## Auth

The endpoint expects a bearer token:

```
Authorization: Bearer <HIGHTOUCH_API_KEY>
```

The token is a shared secret. Coordinate rotation with whoever runs the
ADAM host (`HIGHTOUCH_API_KEY` env var on the server). If Upwork needs
per-row signatures (HMAC over the body), tell us — we can add that.

## Payload schema (POST /brief)

Flat JSON object. Field-by-field:

| Field | Type | Required | Example | Notes |
|---|---|---|---|---|
| `external_id` | string | strongly recommended | `"ht_cohort_q2_prospect_2026_06"` | Stable identifier from your warehouse. Re-syncs with the same value are idempotent — no duplicate sprints. |
| `delivery_date` | string `YYYY-MM-DD` | yes | `"2026-06-15"` | When the creatives need to be delivered. |
| `targeting` | enum | yes | `"Prospecting"` | One of: `Prospecting`, `Retargeting`, `Prospecting and Retargeting`. |
| `deliverable` | enum | yes | `"images-copy"` | One of: `images-copy`, `images-only`, `copy-only`. |
| `platform` | enum | yes | `"Meta"` | One of: `Meta`, `LinkedIn`, `Reddit`, `YouTube`, `3rd Party / Affiliate`, `Google / Bing`. |
| `format` | string | yes | `"Static Feed"` | Platform-specific format label (matches what the order form sends). |
| `visual_styles` | string[] | yes (≥1) | `["Lifestyle Photo", "Testimonial"]` | One or more visual style names. See "Valid visual styles" below. |
| `resolutions` | object[] | yes (≥1) | `[{"size": "1440x1440", "ratio": "1:1"}]` | Each entry needs `size` and `ratio`. |
| `quantity` | integer | yes | `3` | Concepts to generate per visual style. Positive integer. |
| `brief` | string | recommended | `"Test 'flexible work for parents' angle..."` | Free-text creative brief. If omitted, ADAM falls back to `audience_segment`. |
| `audience_segment` | string | recommended | `"Q2 prospecting parents 25-40"` | Used as both attribution and the fallback brief. |
| `driver` | string | optional | `"hightouch-auto"` | Who/what triggered the sprint. Defaults to `hightouch-auto` if omitted. |
| `carousel` | boolean | optional | `false` | Set true for carousel formats. |
| `carousel_slides` | integer | required if `carousel=true` | `5` | 2–10. |

### Valid visual styles

```
Lifestyle Photo, Photo with Text, Testimonial, Split Screen, Text Only,
Reminder, Meme,
Graphic with Text, Us vs Them, Social Media Profile, Pie Chart, Hybrid,
Search Results, Search Bar with Talent Badge, Chat Bubble, Notification,
Device UI, Platform UI, Sticky Note, Poll, Tweet / Post Mockup,
Text with Button, Talent Profile, Bespoke
```

**Note**: Only the first 7 currently produce delivery-ready creatives end to end. The others are valid for routing but require the corresponding template to be live in Figma. See `configs/template_registry.json` for current status.

### Targeting note

When `targeting = "Prospecting and Retargeting"`, also include an
`audience_segment` field — ADAM uses it as the per-batch audience.

## Example payloads

### Minimal valid

```json
{
  "external_id": "ht_demo_001",
  "delivery_date": "2026-06-15",
  "targeting": "Prospecting",
  "deliverable": "images-copy",
  "platform": "Meta",
  "format": "Static Feed",
  "visual_styles": ["Lifestyle Photo"],
  "resolutions": [{"size": "1440x1440", "ratio": "1:1"}],
  "quantity": 3,
  "brief": "Flexible work angle for new parent audience"
}
```

### Realistic prospecting campaign

```json
{
  "external_id": "ht_prospect_parents_q2_2026",
  "delivery_date": "2026-06-15",
  "driver": "hightouch-auto",
  "targeting": "Prospecting",
  "deliverable": "images-copy",
  "audience_segment": "Parents 25-40, US, household income $75k+",
  "brief": "Position Upwork as the platform that gives parents control over their schedule. Lead with autonomy, not income. No hard sell.",
  "platform": "Meta",
  "format": "Static Feed",
  "visual_styles": ["Lifestyle Photo", "Testimonial"],
  "resolutions": [
    {"size": "1440x1440", "ratio": "1:1"},
    {"size": "1080x1350", "ratio": "4:5"}
  ],
  "quantity": 3
}
```

## Response shapes

### `POST /brief` — 201 Created (new sprint)

```json
{
  "ok": true,
  "duplicate": false,
  "external_id": "ht_prospect_parents_q2_2026",
  "sprint_id": "2026-06-meta-9a3b",
  "status_url": "/sprints/2026-06-meta-9a3b",
  "chat_url": "/sprints/2026-06-meta-9a3b/chat"
}
```

### `POST /brief` — 200 OK (duplicate, idempotent return)

```json
{
  "ok": true,
  "duplicate": true,
  "external_id": "ht_prospect_parents_q2_2026",
  "sprint_id": "2026-06-meta-9a3b",
  "status_url": "/sprints/2026-06-meta-9a3b",
  "chat_url": "/sprints/2026-06-meta-9a3b/chat"
}
```

### `POST /brief` — 400 Bad Request

```json
{
  "detail": {
    "error": "payload_validation_failed",
    "details": [
      "Missing required field: delivery_date",
      "batches[0]: unknown platform 'Instagram'"
    ]
  }
}
```

## Recommended Hightouch sync configuration

- **Sync mode:** "Insert" or "Insert + Update." ADAM is idempotent on
  `external_id`, so either is safe.
- **Schedule:** event-driven (trigger when a cohort hits a threshold) or
  scheduled (daily/weekly). Both work.
- **Error handling:** treat any non-2xx response as a sync failure and retry
  on Hightouch's default schedule. ADAM returns specific 4xx errors when the
  payload is malformed.
- **Column mapping:** all fields above are simple JSON paths. Use Hightouch's
  expression editor for date formatting (warehouse timestamps → `YYYY-MM-DD`).

## After the sprint is created

The response includes a `chat_url`. Drop it in a Slack message, an email,
or wherever the reviewing team lives — clicking it opens the ADAM chat with
the sprint pre-loaded, ready for gate-by-gate review.

If you'd rather not surface the URL, the reviewer can also list sprints at
`/sprints` (or the agent UI at `/sprints/<id>/chat`).

## Things to coordinate before turning this on

1. **API key.** Generate a shared secret, store it as `HIGHTOUCH_API_KEY` on the ADAM host AND in Hightouch's destination config.
2. **Host.** Pick which ADAM host Hightouch points at: production Replit deployment, Fly.io fallback, or a dedicated host once Upwork promotes ADAM to production.
3. **Volume / rate limits.** Today the pipeline runs each sprint as a subprocess on the host. At >1 sprint/min the host will need a real job queue. Start with a sane Hightouch rate limit (e.g., 1/min) and revisit if volume grows.
4. **Notification path.** Who finds out when a Hightouch-triggered sprint creates? Slack webhook, email, or just trust the warehouse table to track it. Decide upstream.

## Local testing

```bash
export HIGHTOUCH_API_KEY="test-secret"
curl -s -X POST http://localhost:5000/integrations/hightouch/brief \
  -H "Authorization: Bearer test-secret" \
  -H "Content-Type: application/json" \
  -d @docs/hightouch_sample_brief.json | jq
```

Then check `runs/<sprint_id>/` to see the order.json and pipeline.log.

A sample brief is at `docs/hightouch_sample_brief.json`.
