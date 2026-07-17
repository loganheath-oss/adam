"""
ADAM data spine — Postgres via SQLAlchemy (sync, so it works from both the async
FastAPI endpoints and the sync pipeline code).

Phase 1: users + usage_events. Feedback + roles tables come in later phases.
Everything is best-effort: if the DB is unreachable or DATABASE_URL is unset, the
app runs exactly as before — event logging just no-ops. Nothing here is on the
request's critical path.

See docs/admin-usage-design.md for the full design.
"""

import os
import datetime
from sqlalchemy import (
    create_engine, Column, BigInteger, Text, DateTime, Index, func, select, insert,
    cast, Float,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, sessionmaker

# Railway injects DATABASE_URL as postgres://…; SQLAlchemy wants postgresql://…
_URL = os.environ.get("DATABASE_URL", "")
if _URL.startswith("postgres://"):
    _URL = _URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()
_engine = None
_Session = None


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=True)
    role = Column(Text, nullable=False, server_default="member")  # admin | member (admin = Ravi + Logan)
    tags = Column(ARRAY(Text), nullable=True)  # e.g. {dev} — excluded from impact reports
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(Text, nullable=True)  # best-known identity (SSO backfills later)
    action = Column(Text, nullable=False)      # see event catalog
    sprint_id = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)
    __table_args__ = (
        Index("ix_events_ts", "ts"),
        Index("ix_events_user_ts", "user_email", "ts"),
        Index("ix_events_action_ts", "action", "ts"),
        Index("ix_events_sprint", "sprint_id"),
    )


class IssueReport(Base):
    """User-reported issues — the feedback→learning loop. Success = this table grows
    slower over time (fewer reports = ADAM improving). Admins triage and distill the
    real ones into learnings.md (which ADAM reads on every run/chat)."""
    __tablename__ = "issue_reports"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(Text, nullable=True)
    sprint_id = Column(Text, nullable=True)
    category = Column(Text, nullable=True)      # error | wrong_output | quality | other
    description = Column(Text, nullable=False)   # what the user says went wrong
    context = Column(JSONB, nullable=True)       # stage, output snapshot, what they were doing
    status = Column(Text, nullable=False, server_default="open")  # open | triaged | resolved | learned
    resolution_note = Column(Text, nullable=True)
    __table_args__ = (
        Index("ix_issues_ts", "ts"),
        Index("ix_issues_status", "status"),
    )


def report_issue(description: str, user_email: str | None = None,
                 sprint_id: str | None = None, category: str | None = None,
                 context: dict | None = None) -> bool:
    """Capture a user-reported issue. Best-effort; returns True if stored."""
    if _Session is None:
        return False
    try:
        with _Session() as s:
            s.add(IssueReport(description=description, user_email=user_email,
                              sprint_id=sprint_id, category=category, context=context or {}))
            s.commit()
        log_event("issue.reported", user_email=user_email, sprint_id=sprint_id,
                  meta={"category": category})
        return True
    except Exception as e:
        print(f"[db] report_issue failed: {e}")
        return False


def list_issues(status: str | None = None, limit: int = 200) -> dict:
    """The triage queue + counts by status. The scoreboard is 'this shrinks over
    time' — fewer reports = ADAM improving. Best-effort."""
    if _Session is None:
        return {"enabled": False}
    try:
        with _Session() as s:
            q = select(IssueReport).order_by(IssueReport.ts.desc()).limit(limit)
            if status:
                q = q.where(IssueReport.status == status)
            rows = s.execute(q).scalars().all()
            counts = dict(s.execute(
                select(IssueReport.status, func.count()).group_by(IssueReport.status)
            ).all())
            items = [{
                "id": r.id,
                "ts": r.ts.isoformat() if r.ts else None,
                "user": r.user_email,
                "sprint_id": r.sprint_id,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                "resolution_note": r.resolution_note,
            } for r in rows]
        return {"enabled": True, "counts": counts, "open": counts.get("open", 0),
                "total": sum(counts.values()), "issues": items}
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


def update_issue(issue_id: int, status: str | None = None,
                 resolution_note: str | None = None) -> bool:
    """Triage: set status and/or a resolution note. Best-effort; False if not found."""
    if _Session is None:
        return False
    try:
        with _Session() as s:
            r = s.get(IssueReport, issue_id)
            if r is None:
                return False
            if status:
                r.status = status
            if resolution_note is not None:
                r.resolution_note = resolution_note
            s.commit()
        return True
    except Exception as e:
        print(f"[db] update_issue failed: {e}")
        return False


def list_users(limit: int = 500) -> dict:
    """All known users + their roles (admin | member) for the Roles tab. Users are
    created automatically the first time they're seen in an event. Best-effort."""
    if _Session is None:
        return {"enabled": False}
    try:
        with _Session() as s:
            rows = s.execute(
                select(User).order_by(User.role, User.last_seen_at.desc())
            ).scalars().all()
            counts = dict(s.execute(select(User.role, func.count()).group_by(User.role)).all())
            users = [{
                "email": u.email, "name": u.name, "role": u.role,
                "tags": u.tags or [],
                "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            } for u in rows[:limit]]
        return {"enabled": True, "counts": counts, "users": users}
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


def set_role(email: str, role: str) -> bool:
    """Set a user's role (admin | member); creates the user if unseen. Best-effort."""
    if _Session is None or role not in ("admin", "member") or not email:
        return False
    try:
        with _Session() as s:
            u = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if u is None:
                s.add(User(email=email, role=role))
            else:
                u.role = role
            s.commit()
        return True
    except Exception as e:
        print(f"[db] set_role failed: {e}")
        return False


def ensure_admins(emails) -> None:
    """Seed admin role for the known admins (Ravi + Logan) from ADMIN_EMAILS on
    startup, so they're admin even before they've been seen. Best-effort."""
    for e in emails:
        if (e or "").strip():
            set_role(e.strip(), "admin")


def is_admin(email: str | None) -> bool:
    """Role check for future per-route enforcement (activates once SSO gives a
    per-user identity). Best-effort; False if unknown."""
    if _Session is None or not email:
        return False
    try:
        with _Session() as s:
            u = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
            return bool(u and u.role == "admin")
    except Exception:
        return False


def db_enabled() -> bool:
    return bool(_URL)


def init_db() -> bool:
    """Connect + create tables. Safe to call on startup; returns False if no DB configured."""
    global _engine, _Session
    if not _URL:
        print("[db] DATABASE_URL not set — usage tracking disabled (app runs normally).")
        return False
    try:
        _engine = create_engine(_URL, pool_pre_ping=True, pool_size=5, max_overflow=5,
                                pool_recycle=1800, connect_args={"connect_timeout": 5})
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
        Base.metadata.create_all(_engine)
        print("[db] connected; schema ensured (users, usage_events).")
        # Seed the known admins (Ravi + Logan) from ADMIN_EMAILS so they're admin
        # before they've been seen. RBAC enforcement per-route activates with SSO.
        admins = os.environ.get("ADMIN_EMAILS", "")
        if admins:
            ensure_admins(admins.split(","))
        return True
    except Exception as e:
        print(f"[db] init failed ({e}); usage tracking disabled.")
        _engine = _Session = None
        return False


def log_deploy_once(deployment_id: str, meta: dict) -> bool:
    """Record a deploy.detected event, but only ONCE per Railway deployment — so a
    behavior change in August can be correlated with the code that shipped it, while
    plain container restarts (same deployment_id) don't spam the timeline. Returns
    True if a new deploy was recorded. Best-effort."""
    if _Session is None or not deployment_id:
        return False
    try:
        with _Session() as s:
            existing = s.execute(
                select(func.count()).select_from(UsageEvent)
                .where(UsageEvent.action == "deploy.detected",
                       UsageEvent.meta["deployment_id"].astext == deployment_id)
            ).scalar() or 0
            if existing:
                return False
            s.add(UsageEvent(action="deploy.detected",
                             meta={**meta, "deployment_id": deployment_id}))
            s.commit()
        return True
    except Exception as e:
        print(f"[db] log_deploy_once failed: {e}")
        return False


def log_event(action: str, user_email: str | None = None,
              sprint_id: str | None = None, meta: dict | None = None) -> None:
    """Append one usage event + bump the user's last_seen. Best-effort — never raises."""
    if _Session is None:
        return
    try:
        with _Session() as s:
            s.add(UsageEvent(action=action, user_email=user_email,
                             sprint_id=sprint_id, meta=meta or {}))
            if user_email:
                # upsert user (create on first sight, bump last_seen thereafter)
                u = s.execute(select(User).where(User.email == user_email)).scalar_one_or_none()
                now = datetime.datetime.now(datetime.timezone.utc)
                if u is None:
                    s.add(User(email=user_email, last_seen_at=now))
                else:
                    u.last_seen_at = now
            s.commit()
    except Exception as e:
        print(f"[db] log_event({action}) failed: {e}")


def session():
    """Yield a session for admin read queries. Returns None if DB disabled."""
    return _Session() if _Session is not None else None


def _since(days: int):
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)


def reliability_summary(since_days: int = 30) -> dict:
    """The headline view: are runs completing clean? Counts runs started
    (order.submitted) vs the LATEST terminal outcome per sprint (completed/failed),
    plus a recent incident list. Best-effort; {'enabled': False} if DB is off."""
    if _Session is None:
        return {"enabled": False}
    since = _since(since_days)
    try:
        with _Session() as s:
            runs = s.execute(
                select(func.count()).select_from(UsageEvent)
                .where(UsageEvent.action == "order.submitted", UsageEvent.ts >= since)
            ).scalar() or 0

            # Latest terminal outcome per sprint (ts desc → first seen per sprint wins).
            rows = s.execute(
                select(UsageEvent.sprint_id, UsageEvent.action, UsageEvent.ts)
                .where(UsageEvent.action.in_(["sprint.completed", "sprint.failed"]),
                       UsageEvent.ts >= since, UsageEvent.sprint_id.isnot(None))
                .order_by(UsageEvent.sprint_id, UsageEvent.ts.desc())
            ).all()
            latest = {}
            for sid, action, _ts in rows:
                latest.setdefault(sid, action)
            completed = sum(1 for a in latest.values() if a == "sprint.completed")
            failed = sum(1 for a in latest.values() if a == "sprint.failed")
            resolved = completed + failed

            incidents = s.execute(
                select(UsageEvent.sprint_id, UsageEvent.ts, UsageEvent.user_email, UsageEvent.meta)
                .where(UsageEvent.action == "sprint.failed", UsageEvent.ts >= since)
                .order_by(UsageEvent.ts.desc()).limit(25)
            ).all()

        return {
            "enabled": True,
            "since_days": since_days,
            "runs_started": runs,
            "completed": completed,
            "failed": failed,
            "clean_rate": round(completed / resolved, 4) if resolved else None,
            "incidents": [
                {"sprint_id": sid, "ts": ts.isoformat() if ts else None,
                 "user": ue, "stage": (m or {}).get("stage"),
                 "state": (m or {}).get("state"), "error": (m or {}).get("error")}
                for sid, ts, ue, m in incidents
            ],
        }
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


# Approximate per-model pricing ($ per 1M tokens) for the spend breakdown. "Approximate"
# is the explicit ask (Ravi, 2026-07-16) — figures are directional, for budgeting and
# usage-approval conversations, not billing. Unknown models fall back to Sonnet rates.
_PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
}
_PRICING_DEFAULT = (3.0, 15.0)


def _model_cost(model: str, it: int, ot: int) -> float:
    pin, pout = _PRICING.get(model, _PRICING_DEFAULT)
    return it / 1_000_000 * pin + ot / 1_000_000 * pout


def spend_summary(since_days: int = 30, monthly_budget: float = 0.0) -> dict:
    """Token + cost analytics (Ravi's ask, 2026-07-16: definitive spend data to share,
    set an API-key budget, justify usage approvals). Aggregates every event carrying
    meta.cost_usd into window totals + by-day / by-user / by-model breakdowns, plus a
    month-to-date figure against an optional budget with an end-of-month projection.
    Best-effort; {'enabled': False} if DB is off."""
    if _Session is None:
        return {"enabled": False}
    now = datetime.datetime.now(datetime.timezone.utc)
    since = _since(since_days)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        with _Session() as s:
            rows = s.execute(
                select(UsageEvent.ts, UsageEvent.user_email, UsageEvent.meta)
                .where(UsageEvent.ts >= min(since, month_start),
                       UsageEvent.meta["cost_usd"].isnot(None))
                .order_by(UsageEvent.ts.asc())
            ).all()

        total = {"cost": 0.0, "in": 0, "out": 0, "runs": 0}
        by_day, by_user, by_model = {}, {}, {}
        mtd_cost = 0.0
        for ts, user, m in rows:
            m = m or {}
            cost = float(m.get("cost_usd") or 0.0)
            it, ot = int(m.get("input_tokens") or 0), int(m.get("output_tokens") or 0)
            if ts and ts >= month_start:
                mtd_cost += cost
            if not (ts and ts >= since):
                continue  # older than the window — counted only toward MTD above
            total["cost"] += cost; total["in"] += it; total["out"] += ot; total["runs"] += 1
            day = ts.date().isoformat()
            d = by_day.setdefault(day, {"day": day, "cost": 0.0, "in": 0, "out": 0, "runs": 0})
            d["cost"] += cost; d["in"] += it; d["out"] += ot; d["runs"] += 1
            uk = user or "unknown"
            u = by_user.setdefault(uk, {"user": uk, "cost": 0.0, "in": 0, "out": 0, "runs": 0})
            u["cost"] += cost; u["in"] += it; u["out"] += ot; u["runs"] += 1
            for model, bm in (m.get("by_model") or {}).items():
                mit, mot = int(bm.get("input_tokens") or 0), int(bm.get("output_tokens") or 0)
                g = by_model.setdefault(model, {"model": model, "cost": 0.0, "in": 0, "out": 0})
                g["in"] += mit; g["out"] += mot; g["cost"] += _model_cost(model, mit, mot)

        def _round(rows_, keys=("cost",)):
            for r in rows_:
                for k in keys:
                    r[k] = round(r[k], 4)
            return rows_

        days_in_month = 31
        nxt = month_start.replace(day=28) + datetime.timedelta(days=4)
        days_in_month = (nxt.replace(day=1) - datetime.timedelta(days=1)).day
        day_of_month = now.day
        projected = round(mtd_cost / day_of_month * days_in_month, 2) if day_of_month else mtd_cost

        return {
            "enabled": True,
            "since_days": since_days,
            "total_cost_usd": round(total["cost"], 2),
            "total_input_tokens": total["in"],
            "total_output_tokens": total["out"],
            "runs": total["runs"],
            "by_day": _round(sorted(by_day.values(), key=lambda r: r["day"])),
            "by_user": _round(sorted(by_user.values(), key=lambda r: -r["cost"])),
            "by_model": _round(sorted(by_model.values(), key=lambda r: -r["cost"])),
            "month_to_date_usd": round(mtd_cost, 2),
            "monthly_budget_usd": round(float(monthly_budget or 0), 2),
            "budget_pct": round(mtd_cost / monthly_budget * 100, 1) if monthly_budget else None,
            "projected_month_usd": projected,
        }
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


def digest(since_days: int = 7, monthly_budget: float = 0.0) -> dict:
    """A period summary for async catch-up — the automated version of Bree's manual
    August change log / Logan's September review. Composes reliability + spend with
    period-specific counts (new issues, degraded assemblies, deploys, errors) so one
    screen answers 'what happened this week'. Best-effort."""
    if _Session is None:
        return {"enabled": False}
    since = _since(since_days)
    try:
        rel = reliability_summary(since_days)
        spend = spend_summary(since_days, monthly_budget)
        issues = list_issues()
        with _Session() as s:
            counts = dict(s.execute(
                select(UsageEvent.action, func.count())
                .where(UsageEvent.ts >= since).group_by(UsageEvent.action)
            ).all())
            degraded = s.execute(
                select(func.count()).select_from(UsageEvent)
                .where(UsageEvent.action == "assembly.completed", UsageEvent.ts >= since,
                       UsageEvent.meta["degraded"].astext == "true")
            ).scalar() or 0
            errors = s.execute(
                select(func.count()).select_from(UsageEvent)
                .where(UsageEvent.action.like("error.%"), UsageEvent.ts >= since)
            ).scalar() or 0
            deploys = s.execute(
                select(UsageEvent.ts, UsageEvent.meta)
                .where(UsageEvent.action == "deploy.detected", UsageEvent.ts >= since)
                .order_by(UsageEvent.ts.desc()).limit(30)
            ).all()
        return {
            "enabled": True,
            "since_days": since_days,
            "orders": counts.get("order.submitted", 0),
            "completed": rel.get("completed", 0),
            "failed": rel.get("failed", 0),
            "clean_rate": rel.get("clean_rate"),
            "incidents": (rel.get("incidents") or [])[:10],
            "assemblies": counts.get("assembly.completed", 0),
            "assemblies_degraded": degraded,
            "issues_new": counts.get("issue.reported", 0),
            "issues_open": issues.get("open") if issues.get("enabled") else None,
            "errors": errors,
            "spend_usd": spend.get("total_cost_usd", 0.0),
            "spend_by_user": (spend.get("by_user") or [])[:8],
            "month_to_date_usd": spend.get("month_to_date_usd"),
            "projected_month_usd": spend.get("projected_month_usd"),
            "monthly_budget_usd": spend.get("monthly_budget_usd"),
            "deploys": [
                {"ts": t.isoformat() if t else None,
                 "sha": (m or {}).get("sha"), "message": (m or {}).get("message"),
                 "service": (m or {}).get("service")}
                for t, m in deploys
            ],
        }
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


def activity_feed(since_days: int = 30, limit: int = 100, offset: int = 0,
                  action: str | None = None, user_email: str | None = None,
                  sprint_id: str | None = None) -> dict:
    """Chronological event feed (newest first) — every logged event, filterable.
    This is the 'what happened, in order' view that aggregate counts can't give:
    built for August (team self-diagnosis in the moment + Logan's September
    reconstruction). `action` supports a trailing '*' prefix match (e.g. 'error.*').
    Best-effort; {'enabled': False} if DB is off."""
    if _Session is None:
        return {"enabled": False}
    since = _since(since_days)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    try:
        with _Session() as s:
            q = select(UsageEvent).where(UsageEvent.ts >= since)
            if action:
                q = (q.where(UsageEvent.action.like(action[:-1] + "%"))
                     if action.endswith("*") else q.where(UsageEvent.action == action))
            if user_email:
                q = q.where(UsageEvent.user_email == user_email)
            if sprint_id:
                q = q.where(UsageEvent.sprint_id == sprint_id)
            total = s.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
            rows = s.execute(
                q.order_by(UsageEvent.ts.desc(), UsageEvent.id.desc())
                 .limit(limit).offset(offset)
            ).scalars().all()
            events = [{
                "id": r.id,
                "ts": r.ts.isoformat() if r.ts else None,
                "action": r.action,
                "user": r.user_email,
                "sprint_id": r.sprint_id,
                "meta": r.meta or {},
            } for r in rows]
            # Distinct actions in-window, for the filter dropdown.
            actions = [a for (a,) in s.execute(
                select(UsageEvent.action).where(UsageEvent.ts >= since)
                .group_by(UsageEvent.action).order_by(UsageEvent.action)
            ).all()]
        return {"enabled": True, "since_days": since_days, "total": total,
                "limit": limit, "offset": offset,
                "returned": len(events), "events": events, "actions": actions}
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}


def usage_summary(since_days: int = 30) -> dict:
    """Companion view: total events, active users, and a per-action breakdown.
    Best-effort; {'enabled': False} if DB is off."""
    if _Session is None:
        return {"enabled": False}
    since = _since(since_days)
    try:
        with _Session() as s:
            total = s.execute(
                select(func.count()).select_from(UsageEvent).where(UsageEvent.ts >= since)
            ).scalar() or 0
            active_users = s.execute(
                select(func.count(func.distinct(UsageEvent.user_email)))
                .where(UsageEvent.ts >= since, UsageEvent.user_email.isnot(None))
            ).scalar() or 0
            by_action = s.execute(
                select(UsageEvent.action, func.count())
                .where(UsageEvent.ts >= since)
                .group_by(UsageEvent.action).order_by(func.count().desc())
            ).all()
            # Total spend: sum meta.cost_usd across events that carry it.
            cost = s.execute(
                select(func.coalesce(func.sum(cast(UsageEvent.meta["cost_usd"].astext, Float)), 0.0))
                .where(UsageEvent.ts >= since, UsageEvent.meta["cost_usd"].isnot(None))
            ).scalar() or 0.0
        return {
            "enabled": True,
            "since_days": since_days,
            "total_events": total,
            "active_users": active_users,
            "total_cost_usd": round(float(cost), 2),
            "by_action": {a: n for a, n in by_action},
        }
    except Exception as e:
        return {"enabled": True, "error": f"query failed: {e}"}
