"""Step 51.4 -- Admin Console Runtime Baseline view present + wired."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "RuntimeBaseline.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
APP = ADMIN / "src" / "App.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"


def test_static_fallback_has_runtime_view() -> None:
    s = STATIC.read_text(encoding="utf-8")
    assert "Runtime Baseline" in s
    assert "renderRuntime" in s
    assert "/operations/runtime/report" in s


def test_react_runtime_page_present_and_wired() -> None:
    assert PAGE.is_file()
    assert "getRuntimeReport" in PAGE.read_text(encoding="utf-8")
    assert "/operations/runtime/report" in OPS.read_text(encoding="utf-8")
    assert "RuntimeBaseline" in APP.read_text(encoding="utf-8")
    assert "/runtime" in APP.read_text(encoding="utf-8")


def test_nav_has_runtime_entry() -> None:
    assert "Runtime Baseline" in NAV.read_text(encoding="utf-8")


def test_runtime_view_shows_production_caveat() -> None:
    for f in (STATIC, PAGE):
        t = f.read_text(encoding="utf-8")
        assert "Production is NOT ready" in t
        assert "no cluster connected" in t.lower() or "no cluster" in t.lower()
