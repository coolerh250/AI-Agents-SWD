"""Step 54.2 -- scan exclusion policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scan-exclusion-policy.yaml"


def _p() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["exclusionPolicy"]


def test_explicit_and_reasoned() -> None:
    p = _p()
    assert p["explicitOnly"] is True
    assert p["reasonRequired"] is True
    for ex in p["exclusions"]:
        assert ex.get("reason")


def test_must_not_hide_sensitive() -> None:
    mnh = set(_p()["mustNotHide"])
    assert {
        "production_code",
        "secret_like_files",
        "dockerfiles",
        "requirements_or_package_files",
        "helm_or_gitops_manifests",
    } <= mnh


def test_secret_fixture_classification_is_informational() -> None:
    c = _p()["secretFixtureClassification"]
    assert c["classifyAs"] == "informational"
    assert c["globs"]
    assert any("tests/" in g for g in c["globs"])
