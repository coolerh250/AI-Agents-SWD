#!/usr/bin/env python3
"""Step 52.3 -- session cleanup verifier (pure logic, NO DB, NO network).

Validates the non-destructive cleanup planner: active-and-valid sessions are
preserved, only active-past-expiry sessions are slated to expire, expired and
revoked sessions are counted but never touched, and no raw token is referenced.

Marker: SESSION_CLEANUP_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.identity import plan_cleanup  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    sessions = [
        {"status": "active", "session_hash": "valid1", "expires_at_epoch": 1000},
        {"status": "active", "session_hash": "stale1", "expires_at_epoch": 100},
        {"status": "active", "session_hash": "stale2", "expires_at_epoch": 200},
        {"status": "expired", "session_hash": "old1", "expires_at_epoch": 50},
        {"status": "revoked", "session_hash": "rev1", "expires_at_epoch": 50},
    ]
    plan = plan_cleanup(sessions, now=500)

    if plan.active != 1:
        bad(f"active-and-valid count should be 1, got {plan.active}")
    if "valid1" in plan.to_expire:
        bad("active-and-valid session must NOT be slated to expire")
    if set(plan.to_expire) != {"stale1", "stale2"}:
        bad(f"only stale active sessions should expire, got {plan.to_expire}")
    if plan.revoked != 1:
        bad("revoked session must be counted, not touched")
    if plan.expired < 3:  # old1 + the 2 newly-stale
        bad(f"expired count should include stale + already-expired, got {plan.expired}")
    if plan.dry_run is not True:
        bad("plan default must be dry_run")
    if not failures:
        ok(
            "cleanup preserves active-valid; expires only stale active; counts expired/revoked; dry-run default"
        )

    # raw token must never be referenced by the cleanup module
    src = (ROOT / "shared" / "sdk" / "identity" / "session_cleanup.py").read_text(encoding="utf-8")
    if "raw_token" in src or "token_value" in src:
        bad("cleanup module must not reference a raw token")
    else:
        ok("cleanup module references session_hash/status/expires_at only (no raw token)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SESSION_CLEANUP_VERIFY: FAIL")
        return 1
    print("SESSION_CLEANUP_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
