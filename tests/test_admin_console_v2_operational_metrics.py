"""Step 58 -- Admin Console v2 operational metrics view (read-only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "apps" / "admin-console" / "static" / "index.html"
PAGE = ROOT / "apps" / "admin-console" / "src" / "pages" / "OperationalMetrics.tsx"
OPS = ROOT / "apps" / "admin-console" / "src" / "api" / "operations.ts"

SECTION = "Operational Metrics (Admin Console v2, Step 58)"


def test_section_present_static_and_react() -> None:
    assert SECTION in STATIC.read_text(encoding="utf-8")
    assert SECTION in PAGE.read_text(encoding="utf-8")
    ops = OPS.read_text(encoding="utf-8")
    assert "getMetricsOverview" in ops and "/operations/metrics/" in ops


def test_no_mutation_verbs_or_forbidden_buttons() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE) is None
    forbidden = re.compile(
        r"(deploy|argocd\s*sync|create\s*pr|external\s*send|production\s*approve|production\s*ready)",
        re.IGNORECASE,
    )
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", page, re.IGNORECASE):
        assert not forbidden.search(m.group(1)), m.group(1)
