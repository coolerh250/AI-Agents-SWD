"""Step 54.1 -- Admin Console security posture view (source-level)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SecurityPosture.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
APP = ADMIN / "src" / "App.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

FORBIDDEN = re.compile(
    r"(run\s*scan|upload\s*source|connect\s*scanner|configure\s*scanner|"
    r"create\s*pr|push\s*image|production\s*gate)",
    re.IGNORECASE,
)


def test_static_view_present_and_report_backed() -> None:
    src = STATIC.read_text(encoding="utf-8")
    assert "Security / Supply Chain" in src
    assert "renderSecurity" in src
    assert "/operations/security/report" in src


def test_react_view_wired() -> None:
    assert PAGE.is_file()
    assert "Security / Supply Chain" in NAV.read_text(encoding="utf-8")
    assert "SecurityPosture" in APP.read_text(encoding="utf-8")
    assert "/operations/security/report" in OPS.read_text(encoding="utf-8")


def test_no_mutation_button_in_static_view() -> None:
    src = STATIC.read_text(encoding="utf-8")
    block = src[
        src.find("async function renderSecurity") : src.find("async function refreshSafetyPill")
    ]
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
        assert not FORBIDDEN.search(m.group(1)), m.group(1)


def test_no_mutation_verb_in_react_page() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE)
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", page, re.IGNORECASE):
        assert not FORBIDDEN.search(m.group(1)), m.group(1)
