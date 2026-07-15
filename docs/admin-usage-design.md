# ADAM — Usage Tracking, Feedback & Role-Gate (design)

Per-user usage/analytics, a **reliability + issue-report loop**, and simple role-based
access, fronted by an admin dashboard — modeled on the Wonder/CM Brain admin.

**Headline goal (per Logan, 2026-07-14): prove full runs complete clean.** The #1 view
is **Reliability** — % of sprints that ran end-to-end without error, plus every incident
(which stage, what error), trending over time. Two sources: **automatic** (the pipeline
already knows when a run/stage fails) and **user-reported** (a "report an issue" button).

**The issue-report → learning loop.** A user reports an issue → captured with context →
lands in a triage queue admins (Ravi + Logan) see → they distill the real ones into
`learnings.md` (which ADAM reads on every run/chat) → that class of issue stops recurring.
The scoreboard is deliberately **declining report volume over time = ADAM improving.**
The loop is **human-curated in Phase 1** (report → triage → distill), not auto — raw
reports must not auto-mutate ADAM's behavior.

## Principle: one data spine
Everything is a **view on a Postgres database**. Phase 1 stands up the DB + an
append-only **event log**; Feedback and Roles are added on the *same* DB. This is
**additive** to the current file-based sprint store (`runs/`) — no risky migration
of existing sprint data — and it's the first low-risk step of the Postgres move ADAM
needs anyway.

## Identity (interim → SSO)
No real login yet. Attribute every event to the **best-known identity we already
capture**: the order "driver"/email, the chat user, the session. `users.email` is the
key; when Upwork SSO lands it becomes the authenticated identity with **zero rework** —
every row already carries `user_email`, so backfilling is trivial.

## Stack
- **Railway Postgres** (colocated in the `angelic-liberation` project; `DATABASE_URL`
  injected into the `adam` service).
- **SQLAlchemy 2.0 (async)** + **Alembic** migrations — mature with FastAPI, portable
  to Upwork's Postgres.

## Data model

### `users`
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| email | text unique | identity key |
| name | text | |
| role | text | `admin` \| `member` (admin = Ravi + Logan; everyone at Upwork = member) |
| tags | text[] | e.g. `{dev}` — excluded from impact reports (Wonder pattern) |
| created_at | timestamptz | |
| last_seen_at | timestamptz | |

### `usage_events`  — the spine (append-only)
| col | type | notes |
|---|---|---|
| id | bigserial pk | |
| ts | timestamptz default now() | |
| user_email | text null | → users.email (null = system/unknown) |
| action | text | event type (catalog below) |
| sprint_id | text null | links to a sprint when relevant |
| meta | jsonb | action-specific payload |

Indexes: `(ts)`, `(user_email, ts)`, `(action, ts)`, `(sprint_id)`

### `issue_reports`  — the feedback → learning loop
| col | type | notes |
|---|---|---|
| id | bigserial pk | |
| ts | timestamptz default now() | |
| user_email | text null | |
| sprint_id | text null | |
| category | text null | `error` \| `wrong_output` \| `quality` \| `other` |
| description | text | what the user says went wrong |
| context | jsonb null | stage, output snapshot, what they were doing |
| status | text | `open` \| `triaged` \| `resolved` \| `learned` |
| resolution_note | text null | |

Indexes: `(ts)`, `(status)`
**Success metric = this table grows *slower* over time** (fewer reports = ADAM improving).

### roles
Just two: `admin` (Ravi + Logan) and `member` (everyone at Upwork). No granular
per-feature gating planned — a role column on `users` is the whole model.

## Event catalog (what we log)
| action | meta |
|---|---|
| `order.submitted` | platform, formats, styles[], total_assets, deliverable, brief_len |
| `gate.approved` / `gate.rejected` | gate_num, gate_name, reason? |
| `sprint.completed` / `sprint.failed` | styles, assets, duration_s, stage?, error? |
| `copy.generated` | styles, concepts, model, input_tokens, output_tokens, cost_usd |
| `image.generated` | count, method (gemini/library), model, cost_est |
| `chat.asked` | question_len, model, input_tokens, output_tokens, cost_usd, sources |
| `learnings.edited` | chars |
| `issue.reported` | category (companion to the `issue_reports` row) |
| `user.login` | (SSO, later) |

Cost tracking folds in today's `token_usage.json` → `copy.generated` / `chat.asked` meta.
Everything the dashboards need — usage per user, cost per user/sprint, throughput,
error rates, adoption — derives from this one table.

## Admin API (backend, `/admin/*`, admin-role gated)
- `GET /admin/reliability?from&to` — **headline**: % clean runs, incident list (stage, error), trend
- `GET /admin/usage?from&to&group_by` — timeseries + totals (events, active users, cost)
- `GET /admin/issues?status` — triage queue; `PATCH /admin/issues/{id}` — set status / resolution
- `POST /issues` — user-facing "report an issue" capture (not admin)
- `GET /admin/roles` ; `PATCH /admin/roles/{email}` — list users / flip admin↔member

## Admin frontend (adam-web)
New `/admin` route, tabs: **Reliability · Usage · Issues · Roles** — Reliability is the
default. Gated to admin role.

## Phasing
- **Phase 1 (now):** Postgres + `users` + `usage_events` + event helper at touchpoints
  (emphasis on run outcomes — `sprint.completed` / `sprint.failed` / stage errors) +
  fold in `token_usage` + `GET /admin/reliability` + `GET /admin/usage` + a **Reliability**
  dashboard tab. → live answer to "are runs clean?"
- **Phase 2:** `issue_reports` + `POST /issues` ("report an issue" on runs/outputs) +
  admin triage queue + one-click "distill into a learning" (append to `learnings.md`) +
  the declining-reports trend. → the feedback→learning loop.
- **Phase 3:** role enforcement (admin/member gate on `/admin/*` + approve-gate / edit-learnings)
  + Roles tab. Lands with SSO.
