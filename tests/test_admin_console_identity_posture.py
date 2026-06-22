"""Step 52.4 -- Admin Console identity posture view (source-level)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "IdentityPosture.tsx").read_text(encoding="utf-8")
NAV = (ADMIN / "src" / "components" / "Nav.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")


def test_static_view_present_and_report_backed() -> None:
    assert "Identity Posture" in STATIC
    assert "renderIdentity" in STATIC
    assert "/operations/identity/report" in STATIC


def test_react_page_present_and_wired() -> None:
    assert "IdentityPosture" in PAGE
    assert "getIdentityReport" in PAGE
    assert "/operations/identity/report" in OPS


def test_nav_has_identity_entry() -> None:
    assert "Identity Posture" in NAV


def test_view_shows_production_caveat_and_blockers() -> None:
    assert "NOT enabled" in STATIC or "NOT ready" in STATIC
    assert "break-glass" in STATIC.lower()
    assert "platform_admin" in STATIC.lower()
