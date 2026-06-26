"""Step 57 -- Admin Console multi-project view (read + audited writes; no prod buttons)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
PAGE = (ADMIN / "src" / "pages" / "MultiProjectDelivery.tsx").read_text(encoding="utf-8")
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")
ACTION = (ADMIN / "src" / "operator" / "actionClient.ts").read_text(encoding="utf-8")

SECTION = "Multi-project Delivery"


def test_section_present_static_and_react() -> None:
    assert SECTION in PAGE
    assert SECTION in STATIC
    assert "getDeliveryProjects" in OPS
    for fn in ("createProject", "createWorkItem", "dispatchWorkItem"):
        assert fn in ACTION


def test_no_forbidden_buttons() -> None:
    forbidden = re.compile(
        r"(production deploy|pull request|github pr|argocd sync|external send|"
        r"production approve|production[- ]ready|promote)",
        re.IGNORECASE,
    )
    # Scope the static check to the renderMultiProject function (the nav label also
    # contains SECTION, which would otherwise pull in unrelated sections' buttons).
    start = STATIC.find("function renderMultiProject")
    end = STATIC.find("async function renderProjects", start)
    block = STATIC[start:end] if start >= 0 else ""
    for text in (PAGE, block):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            assert not forbidden.search(m.group(1)), m.group(1)


def test_writes_go_through_csrf_client_not_read_client() -> None:
    # Page must not add a mutation verb to the GET-only api client.
    assert re.search(r"\bclient\.(post|put|patch|delete)\b", PAGE) is None
    assert "operatorActions" in PAGE
