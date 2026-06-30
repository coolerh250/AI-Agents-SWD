"""Step 63A -- Admin Console controlled rollout review view (read-only, no action control)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
PAGE = ADMIN / "src" / "pages" / "ControlledRolloutReview.tsx"
STATIC = ADMIN / "static" / "index.html"
OPS = ADMIN / "src" / "api" / "operations.ts"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
APP = ADMIN / "src" / "App.tsx"

SECTION = "Controlled Rollout Go / No-Go Review (Step 63A)"


def test_views_present() -> None:
    assert SECTION in PAGE.read_text(encoding="utf-8")
    assert SECTION in STATIC.read_text(encoding="utf-8")


def test_route_and_nav_registered() -> None:
    assert "/controlled-rollout-review" in APP.read_text(encoding="utf-8")
    assert "/controlled-rollout-review" in NAV.read_text(encoding="utf-8")


def test_operations_getters_present() -> None:
    ops = OPS.read_text(encoding="utf-8")
    assert "getControlledRolloutPolicy" in ops
    assert "/operations/readiness/controlled-rollout" in ops


def test_page_has_no_mutation_verb() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE)


def test_no_forbidden_control_buttons() -> None:
    page = PAGE.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"<button[^>]*>([^<]*(deploy|sync|merge|restore|failover|production approve|"
        r"production ready)[^<]*)</button>",
        re.IGNORECASE,
    )
    assert not forbidden.search(page)
