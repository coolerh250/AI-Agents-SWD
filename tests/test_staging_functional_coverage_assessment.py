"""Step 65A -- Staging functional coverage & integration readiness assessment (docs)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
MATRIX = STAGING / "staging-functional-coverage-matrix.md"
GAPS = STAGING / "staging-functional-gap-register.md"
INTEG = STAGING / "staging-integration-readiness-assessment.md"
ROADMAP = STAGING / "staging-functional-validation-roadmap.md"
CRITERIA = STAGING / "staging-functional-acceptance-criteria.md"
UVP = STAGING / "staging-user-validation-points.md"
RISKS = STAGING / "staging-functional-validation-risk-register.md"
TRANSITION = STAGING / "step64-to-step65-transition-note.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (MATRIX, GAPS, INTEG, ROADMAP, CRITERIA, UVP, RISKS, TRANSITION)
DOMAINS = (
    "intake",
    "agent pipeline",
    "workflow orchestration",
    "qa / code",
    "audit",
    "governance",
    "retry",
    "external integrations",
    "admin console",
    "deployment",
)
STATUSES = (
    "staging_validated",
    "test_validated_only",
    "seeded_evidence_only",
    "mocked",
    "disabled",
    "blocked_by_credential",
    "blocked_by_authorization",
)
ROADMAP_STEPS = ("65b", "65c", "65d", "65e", "65f", "65g", "65h", "65i")


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_domains_present() -> None:
    low = MATRIX.read_text(encoding="utf-8").lower()
    for dom in DOMAINS:
        assert dom in low, dom


def test_status_values_documented() -> None:
    low = MATRIX.read_text(encoding="utf-8").lower()
    for st in STATUSES:
        assert st in low, st


def test_roadmap_covers_65b_to_65i() -> None:
    low = ROADMAP.read_text(encoding="utf-8").lower()
    for step in ROADMAP_STEPS:
        assert step in low, step


def test_step64f4_paused_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "64f.4" in low and "paused" in low
    assert "step 65" in low


def test_integration_readiness_documented() -> None:
    low = INTEG.read_text(encoding="utf-8").lower()
    assert "disabled" in low and "mock" in low


def test_user_validation_points_documented() -> None:
    low = UVP.read_text(encoding="utf-8").lower()
    assert "authoriz" in low
    assert "verdict" in low


def test_no_runtime_change_or_production_action() -> None:
    combined = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no runtime change" in combined
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
        assert "no production action" in low, p.name
        assert "production_executed_true_count=0" in low, p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step65a_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65A" in text
    assert "STAGING_FUNCTIONAL_COVERAGE_ASSESSMENT_VERIFY" in text
