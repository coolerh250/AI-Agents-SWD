"""Step 54.3 -- Admin Console SBOM / container security section (source-level)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SecurityPosture.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

FORBIDDEN = re.compile(
    r"(generate\s*sbom|pull\s*image|scan\s*image|login\s*registry|push\s*image|"
    r"sign\s*image|attest\s*image)",
    re.IGNORECASE,
)


def test_static_section_present_and_wired() -> None:
    s = STATIC.read_text(encoding="utf-8")
    assert "SBOM / Image Digest / Container Security" in s
    assert "/operations/security/sbom/status" in s


def test_react_section_present_and_wired() -> None:
    assert "SBOM / Image Digest / Container Security" in PAGE.read_text(encoding="utf-8")
    assert "/operations/security/sbom/status" in OPS.read_text(encoding="utf-8")


def test_no_mutation_button_in_section() -> None:
    s = STATIC.read_text(encoding="utf-8")
    block = s[
        s.find("SBOM / Image Digest / Container Security") : s.find(
            "async function refreshSafetyPill"
        )
    ]
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
        assert not FORBIDDEN.search(m.group(1)), m.group(1)


def test_react_no_mutation_verb() -> None:
    assert not re.search(
        r"\.(post|put|patch|delete)\s*\(", PAGE.read_text(encoding="utf-8"), re.IGNORECASE
    )
