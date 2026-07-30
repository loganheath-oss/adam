"""Atomic, cross-process sprint state — the ONE way to read, write, and claim
`pipeline_state.json`.

Why this exists (architecture audit, 2026-07-30): sprint state had four writers
across three entry surfaces (HTTP approve, chat tool, MCP connector, CLI) and
two processes, guarded by a single asyncio lock that only the HTTP path used,
with bare `write_text` everywhere. Consequences that actually shipped: a second
approver could run the same stage twice (double spend, interleaved writes), and
a crash mid-write left a torn JSON file that 500'd every sprint surface.

Guarantees:
- `write_state` is atomic (temp file on the same volume + fsync + os.replace),
  so a crash/ENOSPC mid-write can never leave a torn file.
- `read_state` is tolerant: a corrupt file reads as a visible
  `{"state": "corrupt", ...}` pseudo-state instead of raising, so one bad file
  can't take down a listing page — and the damage is SEEN instead of skipped.
- `claim` / `claim_gate` are compare-and-set under an flock file lock, which
  serializes competing writers across BOTH threads and processes (the MCP
  connector shells a subprocess; asyncio/threading locks can't reach it).
  Exactly one approver wins; every other one loses deterministically.

Every approval/resume dispatch point MUST go through `claim_gate`/`claim`
before running a stage. Plain status updates (progress, error states) go
through `write_state`.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def sprint_lock(sprint_dir: Path | str):
    """Exclusive cross-process lock for one sprint's state (blocking flock)."""
    sprint_dir = Path(sprint_dir)
    fd = open(sprint_dir / ".state.lock", "a")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            fd.close()


def read_state(sprint_dir: Path | str) -> dict:
    """Tolerant read. Missing file -> {"state": "unknown"}; torn/corrupt file ->
    {"state": "corrupt", "error": ...} so surfaces render the damage instead of
    500ing on it."""
    p = Path(sprint_dir) / "pipeline_state.json"
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else {"state": "corrupt",
                                                    "error": "state file is not an object"}
    except FileNotFoundError:
        return {"state": "unknown"}
    except Exception as exc:
        return {"state": "corrupt", "error": f"unreadable pipeline_state.json: {exc}"}


def write_state(sprint_dir: Path | str, data: dict) -> None:
    """Atomic replace. The temp file lives in the sprint dir (same volume) so
    os.replace is atomic; fsync so a crash can't reorder the rename before the
    contents are durable."""
    sprint_dir = Path(sprint_dir)
    data.setdefault("sprint_id", sprint_dir.name)
    data.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    fd, tmp = tempfile.mkstemp(dir=sprint_dir, prefix=".state_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, sprint_dir / "pipeline_state.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def claim(sprint_dir: Path | str, from_states: set[str], to_state: dict) -> tuple[bool, str]:
    """Compare-and-set under the cross-process lock: if the current state is in
    `from_states`, write `to_state` and win. Returns (won, prior_state)."""
    sprint_dir = Path(sprint_dir)
    with sprint_lock(sprint_dir):
        cur = read_state(sprint_dir).get("state", "unknown")
        if cur not in from_states:
            return False, cur
        write_state(sprint_dir, dict(to_state))
        return True, cur


def claim_gate(sprint_dir: Path | str, gate: int) -> tuple[bool, str]:
    """The gate-approval CAS: awaiting_gate_N -> resuming_gate_N. Call this at
    EVERY dispatch point (HTTP route, chat tool, MCP tool, CLI) before running
    the stage; only the winner proceeds."""
    return claim(sprint_dir, {f"awaiting_gate_{gate}"},
                 {"state": f"resuming_gate_{gate}"})
