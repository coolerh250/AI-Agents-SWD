"""Step 52.3 -- non-destructive session cleanup planner."""

from __future__ import annotations

from shared.sdk.identity import plan_cleanup


def _sessions() -> list[dict]:
    return [
        {"status": "active", "session_hash": "valid", "expires_at_epoch": 1000},
        {"status": "active", "session_hash": "stale", "expires_at_epoch": 100},
        {"status": "expired", "session_hash": "old", "expires_at_epoch": 10},
        {"status": "revoked", "session_hash": "rev", "expires_at_epoch": 10},
    ]


def test_preserves_active_valid() -> None:
    plan = plan_cleanup(_sessions(), now=500)
    assert plan.active == 1
    assert "valid" not in plan.to_expire


def test_only_stale_active_expire() -> None:
    plan = plan_cleanup(_sessions(), now=500)
    assert plan.to_expire == ["stale"]


def test_counts_expired_and_revoked() -> None:
    plan = plan_cleanup(_sessions(), now=500)
    assert plan.revoked == 1
    assert plan.expired == 2  # already-expired + newly-stale


def test_dry_run_default() -> None:
    assert plan_cleanup(_sessions(), now=500).dry_run is True


def test_no_raw_token_in_module() -> None:
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "shared" / "sdk" / "identity" / "session_cleanup.py"
    ).read_text(encoding="utf-8")
    assert "raw_token" not in src and "token_value" not in src
