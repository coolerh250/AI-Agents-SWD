"""Step 54.4 -- Admin Console integrated security view."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "SecurityPosture.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")

SECTION = "Threat Model / Release Risk / Evidence (Step 54.4)"
FORBIDDEN = re.compile(
    r"(generate\s*evidence|approve\s*release|enable\s*gate|create\s*pr|sync\s*argocd|deploy)",
    re.IGNORECASE,
)


def test_section_present_static_and_react() -> None:
    assert SECTION in STATIC
    assert SECTION in PAGE
    assert "/operations/security/step54/status" in STATIC
    assert "getSecurityStep54Status" in OPS


def test_no_mutation_buttons() -> None:
    block = STATIC[STATIC.find(SECTION) :]
    for text in (block, PAGE):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            assert not FORBIDDEN.search(m.group(1)), m.group(1)


def test_react_page_no_mutation_verb() -> None:
    assert not re.search(r"\.(post|put|patch|delete)\s*\(", PAGE, re.IGNORECASE)
