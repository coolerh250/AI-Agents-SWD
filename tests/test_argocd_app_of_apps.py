"""Step 51.3 -- non-production app-of-apps includes dev+test only."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AOA = ROOT / "infra" / "gitops" / "argocd" / "app-of-apps" / "non-production.yaml"


def _a() -> dict:
    return yaml.safe_load(AOA.read_text(encoding="utf-8"))


def test_kind_application() -> None:
    assert _a()["kind"] == "Application"


def test_includes_dev_test_only() -> None:
    inc = _a()["spec"]["source"]["directory"]["include"]
    assert "dev.yaml" in inc and "test.yaml" in inc


def test_excludes_staging_production() -> None:
    inc = _a()["spec"]["source"]["directory"]["include"]
    assert "staging" not in inc
    assert "production" not in inc


def test_no_auto_sync() -> None:
    sp = _a()["spec"].get("syncPolicy", {}) or {}
    assert "automated" not in sp


def test_excludes_annotations() -> None:
    ann = _a()["metadata"]["annotations"]
    assert ann["ai-agents-swd/excludes-production"] == "true"
    assert ann["ai-agents-swd/do-not-sync"] == "true"
