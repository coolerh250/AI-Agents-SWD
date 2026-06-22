"""Step 52.3 -- non-destructive session cleanup (no raw token, no production).

Marks expired ``admin_console_sessions`` rows as ``expired``; never deletes a
row, never touches an active-and-valid or revoked session, never reads a raw
token (only ``session_hash`` + ``status`` + ``expires_at``). ``plan_cleanup`` is
the pure, DB-free core used by tests/verifier; ``run_cleanup`` applies it via
asyncpg with a ``dry_run`` default.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


@dataclass
class CleanupPlan:
    active: int = 0
    expired: int = 0
    revoked: int = 0
    to_expire: list[str] = field(default_factory=list)
    dry_run: bool = True

    @property
    def total(self) -> int:
        return self.active + self.expired + self.revoked


def plan_cleanup(sessions: list[dict], now: int) -> CleanupPlan:
    """Classify session rows; an active row past its expiry is slated to expire.

    Each ``session`` is ``{status, session_hash, expires_at_epoch}``. Pure; no DB.
    """
    plan = CleanupPlan()
    for s in sessions:
        status = s.get("status")
        if status == "revoked":
            plan.revoked += 1
        elif status == "expired":
            plan.expired += 1
        elif status == "active":
            exp = s.get("expires_at_epoch")
            if exp is not None and exp <= now:
                plan.to_expire.append(s["session_hash"])
                plan.expired += 1
            else:
                plan.active += 1
    return plan


async def run_cleanup(
    database_url: str | None = None,
    *,
    dry_run: bool = True,
    now: int | None = None,
) -> CleanupPlan:
    """Apply the cleanup plan. With ``dry_run`` (default) nothing is written."""
    import asyncpg

    dsn = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    current = int(now if now is not None else time.time())
    conn = await asyncpg.connect(dsn=dsn, timeout=5)
    try:
        rows = await conn.fetch(
            "SELECT session_hash, status, "
            " CAST(EXTRACT(EPOCH FROM expires_at) AS BIGINT) AS expires_at_epoch "
            "FROM admin_console_sessions"
        )
        plan = plan_cleanup([dict(r) for r in rows], current)
        plan.dry_run = dry_run
        if not dry_run and plan.to_expire:
            await conn.execute(
                "UPDATE admin_console_sessions SET status='expired' "
                "WHERE status='active' AND expires_at <= now()"
            )
    finally:
        await conn.close()
    return plan


__all__ = ["DEFAULT_DATABASE_URL", "CleanupPlan", "plan_cleanup", "run_cleanup"]
