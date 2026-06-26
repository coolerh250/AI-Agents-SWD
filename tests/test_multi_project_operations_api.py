"""Step 57 -- multi-project operations API surface."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "apps" / "orchestrator" / "src" / "multi_project_api.py").read_text(encoding="utf-8")


def test_read_endpoints_get_only() -> None:
    gets = re.findall(r'@router\.get\("([^"]*)"\)', API)
    for p in (
        "/projects",
        "/work-items/{work_item_id}/events",
        "/work-items/{work_item_id}/dispatches",
        "/projects/{project_id}/delivery-state",
    ):
        assert p in gets


def test_write_endpoints_present() -> None:
    posts = re.findall(r'@router\.post\("([^"]*)"\)', API)
    assert "/projects" in posts
    assert "/projects/{project_id}/work-items" in posts
    assert "/work-items/{work_item_id}/dispatch" in posts


def test_prefix_is_delivery_namespace() -> None:
    assert 'prefix="/operations/delivery"' in API
