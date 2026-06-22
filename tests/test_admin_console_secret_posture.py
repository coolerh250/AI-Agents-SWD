"""Step 53 -- Admin Console secret posture view (source-level, read-only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "SecretPosture.tsx").read_text(encoding="utf-8")
NAV = (ADMIN / "src" / "components" / "Nav.tsx").read_text(encoding="utf-8")
OPS = (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")

_FORBIDDEN = re.compile(
    r"(reveal|copy|upload|rotate|configure|test\s*secret|show\s*secret|view\s*secret)",
    re.IGNORECASE,
)
_MUTATION = re.compile(r"\.(post|put|patch|delete)\s*\(", re.IGNORECASE)


def _static_block() -> str:
    s = STATIC.find("async function renderSecrets")
    e = STATIC.find("async function refreshSafetyPill")
    return STATIC[s:e]


def test_view_present_and_report_backed() -> None:
    assert "Secret Posture" in STATIC and "renderSecrets" in STATIC
    assert "/operations/secrets/report" in STATIC
    assert "getSecretReport" in PAGE
    assert "/operations/secrets/report" in OPS
    assert "Secret Posture" in NAV


def test_no_forbidden_button() -> None:
    for text in (_static_block(), PAGE):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            assert not _FORBIDDEN.search(m.group(1)), m.group(1)


def test_no_mutation_verb() -> None:
    assert not _MUTATION.search(_static_block())
    assert not _MUTATION.search(PAGE)


def test_production_caveat_and_no_password_input() -> None:
    assert "NOT configured" in STATIC or "NOT ready" in STATIC
    assert 'type="password"' not in _static_block().lower()
