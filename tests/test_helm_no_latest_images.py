"""Step 51.1 -- no component uses the floating ':latest' image tag."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _load(name: str) -> dict:
    with (CHART / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_values_no_latest_tag() -> None:
    comps = _load("values.yaml")["components"]
    for name, comp in comps.items():
        assert str(comp["image"]["tag"]) != "latest", name


def test_catalog_no_latest_tag() -> None:
    comps = _load("component-catalog.yaml")["components"]
    for name, comp in comps.items():
        assert str(comp["image"]["tag"]) != "latest", name


def test_all_images_have_explicit_tag() -> None:
    comps = _load("values.yaml")["components"]
    for name, comp in comps.items():
        tag = comp["image"].get("tag")
        assert tag, f"{name} has empty image tag"
        assert str(tag).strip() != "", name
