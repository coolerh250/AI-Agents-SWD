"""Step 52.3 -- session concurrency policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "session-concurrency-policy.yaml"


def _c() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["sessionConcurrency"]


def test_recorded_not_enforced() -> None:
    assert _c()["currentBehavior"] == "recorded_not_enforced"


def test_production_policy_required_deferred() -> None:
    p = _c()["productionPolicy"]
    assert p["required"] is True
    assert p["maxConcurrentSessions"] is None
    assert p["enforcement"] == "deferred_to_production_auth"


def test_suspicious_patterns_listed() -> None:
    pats = _c()["suspiciousPatterns"]
    assert "excessive_active_sessions" in pats
    assert "role_escalation_during_session" in pats


def test_not_production_ready() -> None:
    s = yaml.safe_load(F.read_text(encoding="utf-8"))["status"]
    assert s["productionReady"] is False
