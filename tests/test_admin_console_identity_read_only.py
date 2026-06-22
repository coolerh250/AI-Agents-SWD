"""Step 52.4 -- Admin Console identity view has no mutation controls."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = (ADMIN / "static" / "index.html").read_text(encoding="utf-8")
PAGE = (ADMIN / "src" / "pages" / "IdentityPosture.tsx").read_text(encoding="utf-8")

_FORBIDDEN_BUTTON = re.compile(
    r"(login|connect|configure|toggle|editor|activate|force\s*logout|logout\s*all|"
    r"upload|client\s*secret|break[_-]?glass)",
    re.IGNORECASE,
)
_MUTATION = re.compile(r"\.(post|put|patch|delete)\s*\(", re.IGNORECASE)


def _static_identity_block() -> str:
    start = STATIC.find("async function renderIdentity")
    end = STATIC.find("async function refreshSafetyPill")
    return STATIC[start:end]


def test_static_identity_view_has_no_forbidden_button() -> None:
    block = _static_identity_block()
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
        assert not _FORBIDDEN_BUTTON.search(m.group(1)), m.group(1)


def test_react_identity_view_has_no_forbidden_button() -> None:
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", PAGE, re.IGNORECASE):
        assert not _FORBIDDEN_BUTTON.search(m.group(1)), m.group(1)


def test_no_mutation_verb_in_identity_views() -> None:
    assert not _MUTATION.search(_static_identity_block())
    assert not _MUTATION.search(PAGE)


def test_no_token_or_secret_input() -> None:
    block = _static_identity_block().lower()
    assert 'type="password"' not in block
    assert "client_secret" not in block
