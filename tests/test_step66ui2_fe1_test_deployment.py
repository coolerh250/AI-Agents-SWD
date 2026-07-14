"""Step 66UI.2-FE.1-D -- Test runtime deployment record (docs-only checks).

Deployment-record stage: this file itself changes no runtime code. It
confirms the deployment record docs exist and state the required facts:
deployment source/environment, Product Owner authorization, UI verification
results, safety posture, and rollback status.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "test-runtime-deployment-record": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "test-runtime-deployment-record.md",
    "fe1-test-runtime-deployment": ROOT
    / "docs"
    / "test"
    / "step66ui2-fe1-test-runtime-deployment.md",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_deployed_source_is_main() -> None:
    text = _norm(_all_text())
    assert "origin/main" in text
    assert "ac11bea" in text


def test_test_runtime_only_scope() -> None:
    text = _norm(_all_text())
    assert "test runtime only" in text
    assert "no staging" in text


def test_seven_nav_groups_verified() -> None:
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


def test_delivery_package_under_platform_ops() -> None:
    text = _norm(_all_text())
    assert "delivery package" in text
    assert "platform ops" in text


def test_placeholder_stages_recorded() -> None:
    text = _norm(_all_text())
    assert "66d" in text
    assert "66c.4" in text
    assert "no workflow action available" in text


def test_demo_evidence_gap_accepted_non_blocking() -> None:
    text = _norm(_all_text())
    assert "demo evidence" in text
    assert "accepted" in text and "deferred" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count before: 0" in text.replace(
        "production_executed_true_count  before", "production_executed_true_count before"
    )


def test_no_production_or_external_action_claimed() -> None:
    text = _norm(_all_text())
    assert "no production action" in text or "production action: no" in text
    assert "workflow dispatch" in text


def test_rollback_status_recorded() -> None:
    text = _norm(_all_text())
    assert "rollback" in text
    assert "not required" in text


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
    text = REVIEW_DOCS["fe1-test-runtime-deployment"].read_text(encoding="utf-8")
    assert "STEP66UI2_FE1_TEST_DEPLOYMENT_VERIFY: PASS" in text
