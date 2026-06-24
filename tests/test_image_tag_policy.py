"""Step 54.3 -- image tag policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "image-tag-policy.yaml"


def _p() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["imageTagPolicy"]


def test_latest_prohibited_no_auto_rewrite() -> None:
    p = _p()
    assert p["latestTagProhibited"] is True
    assert p["autoTagRewriteAllowed"] is False
    assert p["digestRequiredBeforeClusterSmoke"] is True


def test_placeholder_tag_not_deployable() -> None:
    p = _p()
    assert p["currentState"]["placeholderTagInUse"] is True
    assert p["currentState"]["placeholderTagDeployable"] is False
    assert p["currentState"]["latestTagDetected"] is False
    assert p["productionReady"] is False
