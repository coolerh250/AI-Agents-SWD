"""Step 54.2 -- Admin Console scan posture section (source-level)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SecurityPosture.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

FORBIDDEN = re.compile(
    r"(run\s*scan|upload\s*source|connect\s*scanner|configure\s*scanner|create\s*pr|release\s*gate)",
    re.IGNORECASE,
)


def test_static_scan_section_present_and_wired() -> None:
    s = STATIC.read_text(encoding="utf-8")
    assert "Local Scan Toolchain Baseline" in s
    assert "/operations/security/scans/status" in s


def test_react_scan_section_present_and_wired() -> None:
    assert "Local Scan Toolchain Baseline" in PAGE.read_text(encoding="utf-8")
    assert "/operations/security/scans/status" in OPS.read_text(encoding="utf-8")


def test_no_mutation_button_in_scan_block() -> None:
    s = STATIC.read_text(encoding="utf-8")
    block = s[s.find("Local Scan Toolchain Baseline") : s.find("async function refreshSafetyPill")]
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
        assert not FORBIDDEN.search(m.group(1)), m.group(1)


def test_react_page_no_mutation_verb() -> None:
    assert not re.search(
        r"\.(post|put|patch|delete)\s*\(", PAGE.read_text(encoding="utf-8"), re.IGNORECASE
    )
