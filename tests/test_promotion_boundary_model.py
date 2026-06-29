"""Step 60 -- promotion boundary model (production forbidden, no auto-promotion)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "infra" / "release" / "promotion-boundary-model.yaml"


def _pb() -> dict:
    return (yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}).get("promotionBoundary", {})


def test_production_transition_forbidden() -> None:
    prod = [t for t in _pb().get("transitions", []) if t.get("to") == "production"]
    assert prod
    for t in prod:
        assert t.get("allowed") is False
        assert t.get("requiresFutureProductionPhase") is True


def test_no_auto_transition() -> None:
    assert all(t.get("auto") is not True for t in _pb().get("transitions", []))


def test_forbidden_list() -> None:
    forbidden = _pb().get("forbidden", [])
    assert "productionPromotion" in forbidden
    assert "autoPromotion" in forbidden
