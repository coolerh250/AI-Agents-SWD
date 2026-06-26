"""Step 56 -- Admin Console non-production ArgoCD view (read-only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "apps" / "admin-console" / "static" / "index.html"
PAGE = ROOT / "apps" / "admin-console" / "src" / "pages" / "RuntimeBaseline.tsx"
OPS = ROOT / "apps" / "admin-console" / "src" / "api" / "operations.ts"

SECTION = "Non-production ArgoCD Manual Sync (Step 56)"


def test_section_present_static_and_react() -> None:
    assert SECTION in STATIC.read_text(encoding="utf-8")
    assert SECTION in PAGE.read_text(encoding="utf-8")
    assert "/operations/gitops/nonprod-argocd/" in OPS.read_text(encoding="utf-8")
    assert "getNonprodArgocdSync" in OPS.read_text(encoding="utf-8")


def test_no_mutation_buttons_or_verbs() -> None:
    page = PAGE.read_text(encoding="utf-8")
    static = STATIC.read_text(encoding="utf-8")
    forbidden = re.compile(r"(sync|install|delete|rollback|promote|prune)", re.IGNORECASE)
    for text in (page, static):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            assert not forbidden.search(m.group(1)), m.group(1)
    assert re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE) is None
