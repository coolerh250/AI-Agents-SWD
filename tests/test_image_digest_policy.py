"""Step 54.3 -- image digest policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "image-digest-policy.yaml"


def _p() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["imageDigestPolicy"]


def test_digest_required_before_cluster_smoke() -> None:
    p = _p()
    assert p["digestRequired"] is True
    assert "non_production_cluster_smoke" in p["requiredBefore"]


def test_latest_prohibited_registry_login_off() -> None:
    p = _p()
    assert p["latestTagAllowed"] is False
    assert p["registryLoginConfigured"] is False


def test_missing_digest_not_safe() -> None:
    p = _p()
    assert p["currentState"]["anyDigestPinned"] is False
    assert p["blockers"]
    assert p["productionReady"] is False
