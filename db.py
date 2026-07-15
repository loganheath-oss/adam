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
    create_engine, Column, BigInteger, Text, DateTime, Index, func, select, insert
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


def db_enabled() -> bool:
    return bool(_URL)


def init_db() -> bool:
    """Connect + create tables. Safe to call on startup; returns False if no DB configured."""
    global _engine, _Session
    if not _URL:
        print("[db] DATABASE_URL not set — usage tracking disabled (app runs normally).")
        return False
    try:
        _engine = create_engine(_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)
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
