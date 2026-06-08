"""Stage 33 -- operations view exposes the real-delivery policy snapshot.

Cheap structural assertions on the orchestrator's operations.py to make
sure the Stage 33 fields are present and that the worker /status
fetcher is wired up. The HTTP integration is exercised by
verify_real_discord_delivery_filter.sh at runtime.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_safety_includes_stream_delivery_policy_flags():
    src_text = _read_operations()
    assert '"real_discord_stream_delivery_default_blocked"' in src_text
    assert '"real_discord_stream_delivery_policy_enforced"' in src_text


def test_real_integrations_payload_includes_policy_snapshot():
    src_text = _read_operations()
    assert "notification_worker_real_delivery_policy" in src_text
    assert "real_delivery_allowlist" in src_text
    assert "real_delivery_denylist" in src_text
    assert "real_delivery_allowed_count" in src_text
    assert "real_delivery_blocked_count" in src_text
    assert "last_real_delivery_block_reason" in src_text


def test_real_integrations_fetches_notification_worker_status():
    src_text = _read_operations()
    # The fetcher target -- if the URL ever changes we want the test to
    # flag it as a deliberate decision.
    assert "http://notification-worker:8008/status" in src_text


def test_audit_decision_types_include_stage33_filters():
    src_text = _read_operations()
    assert "discord_real_delivery_blocked" in src_text
    assert "discord_real_delivery_skipped" in src_text
