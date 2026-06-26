"""Step 59 -- Admin Console sandbox GitHub view present + no forbidden controls."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "SandboxGithub.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")

SECTION = "Sandbox GitHub Draft PR (Step 59)"


def test_section_present_in_both_views() -> None:
    assert SECTION in STATIC
    assert SECTION in PAGE


def test_getters_present() -> None:
    assert "getSandboxGithubPolicy" in OPS
    assert "/operations/github/sandbox-draft-pr/" in OPS


def test_no_forbidden_control_buttons() -> None:
    for text in (STATIC, PAGE):
        block = text[text.find(SECTION) :]
        for mtch in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            assert not re.search(
                r"(merge|ready[\s-]*for[\s-]*review|workflow\s*dispatch|production\s*deploy)",
                mtch.group(1),
                re.IGNORECASE,
            )


def test_no_token_or_repo_input() -> None:
    for text in (STATIC, PAGE):
        block = text[text.find(SECTION) :]
        assert re.search(r"<input[^>]*(token|owner|repo)[^>]*>", block, re.IGNORECASE) is None


def test_react_page_has_no_mutation_verb() -> None:
    assert re.search(r"\.(post|put|patch|delete)\s*\(", PAGE, re.IGNORECASE) is None
