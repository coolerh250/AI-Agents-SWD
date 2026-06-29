"""Step 60 -- Admin Console release governance view present + no forbidden controls."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "ReleaseGovernance.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")

SECTION = "Release Governance (Step 60)"


def test_section_present_in_both_views() -> None:
    assert SECTION in STATIC
    assert SECTION in PAGE


def test_getters_present() -> None:
    assert "getReleasePolicy" in OPS
    assert "/operations/release/" in OPS


def test_no_forbidden_control_buttons() -> None:
    pat = re.compile(
        r"(production\s*deploy|deploy\s*now|argocd\s*sync|merge|github\s*release|image\s*push|"
        r"production\s*approve)",
        re.IGNORECASE,
    )
    for text in (STATIC, PAGE):
        block = text[text.find(SECTION) :]
        for mtch in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            assert not pat.search(mtch.group(1))


def test_react_page_has_no_mutation_verb() -> None:
    assert re.search(r"\.(post|put|patch|delete)\s*\(", PAGE, re.IGNORECASE) is None
