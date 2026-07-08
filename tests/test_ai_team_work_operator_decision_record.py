"""Step 66A.2 -- AI Agents Team Work operator decision record (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

RECORD = TEST / "ai-team-work-operator-decision-record.md"
WHITELIST = TEST / "ai-team-work-web-research-source-whitelist-proposal.md"
SCOPE = TEST / "ai-team-work-mvp-scope-lock.md"
BLUEPRINT = TEST / "ai-team-work-step66a3-blueprint-inputs.md"
REGISTER = TEST / "ai-team-work-decision-register.md"

DOCS = (RECORD, WHITELIST, SCOPE, BLUEPRINT, REGISTER)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_d1_to_d14_present() -> None:
    rec = RECORD.read_text(encoding="utf-8").lower()
    for i in range(1, 15):
        assert f"d{i}" in rec, f"D{i}"


def test_exact_key_decisions() -> None:
    rec = RECORD.read_text(encoding="utf-8").lower()
    assert "d7 is b" in rec
    assert "d9 is a" in rec
    assert "d10 is c" in rec
    assert "d11 is c" in rec


def test_recorded_values_present() -> None:
    rec = RECORD.read_text(encoding="utf-8").lower()
    for phrase in (
        "conservative rbac",
        "software delivery + documentation + platform improvement",
        "clarification_expired",
        "escalate",
        "archive",
        "max 3 per delivery",
        "platform admin / agent operator only",
        "full chat-style agent workroom",
    ):
        assert phrase in rec, phrase


def test_claude_did_not_change_decisions() -> None:
    rec = RECORD.read_text(encoding="utf-8").lower()
    assert "claude code did not change operator decisions" in rec
    assert "recorded exactly" in rec


def test_whitelist_is_proposal_not_final() -> None:
    wl = WHITELIST.read_text(encoding="utf-8").lower()
    assert "top-10" in wl or "top 10" in wl
    assert "pending operator confirmation" in wl
    assert "final whitelist is not approved" in wl or "not an approved final whitelist" in wl
    assert "no web browsing" in wl or "no browsing" in wl
    assert "missing capability" in wl
    rows = len(re.findall(r"^\|\s*\d+\s*\|", WHITELIST.read_text(encoding="utf-8"), re.MULTILINE))
    assert rows >= 10, rows


def test_scope_lock_and_out_of_scope() -> None:
    assert "mvp scope lock" in SCOPE.read_text(encoding="utf-8").lower()
    assert "out-of-scope" in _all_low()


def test_blueprint_inputs_sections() -> None:
    bp = BLUEPRINT.read_text(encoding="utf-8").lower()
    for need in (
        "acceptance criteria",
        "implementation risks",
        "required backend",
        "required apis",
    ):
        assert need in bp, need


def test_documentation_only_posture() -> None:
    low = _all_low()
    assert "no ui implementation" in low
    assert "no backend implementation" in low
    assert "no runtime change" in low
    assert "no workflow execution" in low
    assert "no external action" in low
    assert "no production action" in low


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for p in DOCS:
        assert not shapes.search(p.read_text(encoding="utf-8")), p.name
