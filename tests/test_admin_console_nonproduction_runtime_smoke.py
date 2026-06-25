"""Step 55 -- Admin Console non-production runtime smoke view."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "RuntimeBaseline.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")

SECTION = "Non-production Runtime Smoke (Step 55)"
FORBIDDEN = re.compile(
    r"(deploy|helm\s*install|cleanup|kubectl\s*exec|argocd\s*sync|uninstall)", re.IGNORECASE
)


def test_section_present() -> None:
    assert SECTION in STATIC
    assert SECTION in PAGE
    assert "/operations/runtime/nonprod-smoke/readiness" in STATIC
    assert "getNonprodSmokeReadiness" in OPS


def test_no_mutation_buttons() -> None:
    block = STATIC[STATIC.find(SECTION) :]
    for text in (block, PAGE):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            assert not FORBIDDEN.search(m.group(1)), m.group(1)


def test_no_mutation_verb() -> None:
    assert not re.search(r"\.(post|put|patch|delete)\s*\(", PAGE, re.IGNORECASE)
