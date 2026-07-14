"""Step 66UI.2-FE.1-V -- Product Owner UI validation record (docs-only checks).

Documentation/validation-record stage: no runtime code, no backend, no
frontend runtime, no database, no workflow execution, no external action, no
production action, no PR merge. This file follows the repo's
tests/test_stepNN_*.py convention and checks only the committed record docs
on the current checkout.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "product-owner-ui-validation-record.md",
    "fe1-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui2-fe1-product-owner-validation.md",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_validation_result_visible_with_accepted_gap() -> None:
    text = _norm(_all_text())
    assert "visible_with_accepted_gap" in text


def test_demo_evidence_deferral_recorded_non_blocking() -> None:
    text = _norm(_all_text())
    assert "demo evidence" in text
    assert "accepted_deferred_non_blocking" in text
    assert "blocks fe.1: no" in text


def test_delivery_package_conflict_closed() -> None:
    text = _norm(_all_text())
    assert "delivery package" in text
    assert "closed" in text


def test_seven_nav_groups_and_placeholders_recorded() -> None:
    text = _norm(_all_text())
    for group in (
        "overview",
        "team work",
        "deliveries",
        "operator center",
        "governance",
        "platform ops",
        "settings",
    ):
        assert group in text, group
    assert "66d" in text
    assert "66c.4" in text
    assert "no workflow action available" in text


def test_safety_posture_recorded() -> None:
    text = _norm(_all_text())
    assert "no workflow dispatch" in text
    assert "no workflow resume" in text
    assert "no production action" in text
    assert "no external action" in text


def test_merge_not_claimed() -> None:
    text = _norm(_all_text())
    assert "not yet granted" in text
    assert "explicit merge authorization still required" in text
    assert "merge authorization is granted" not in text


def test_no_runtime_or_backend_change_claimed() -> None:
    text = _norm(_all_text())
    assert "no database changed" in text or "database changed: no" in text
    assert "no backend changed" in text or "backend changed: no" in text


def test_deployment_rollback_recorded() -> None:
    text = _norm(_all_text())
    assert "rolled back" in text or "rollback" in text
    assert "production_executed_true_count" in text


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["fe1-product-owner-validation"].read_text(encoding="utf-8")
    assert "STEP66UI2_FE1_PRODUCT_OWNER_VALIDATION_VERIFY: PASS" in text
