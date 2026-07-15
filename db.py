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
        return True
    except Exception as e:
        print(f"[db] init failed ({e}); usage tracking disabled.")
        _engine = _Session = None
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
