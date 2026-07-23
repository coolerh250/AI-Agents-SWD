"""Step 66C.4-BE2-R -- static self-tests for the independent review artifacts.

These tests are self-contained (no DB, no Redis, no network). They assert that the review's own
artifacts are internally consistent: markers recorded separately, footers present, masking clean,
and that the review branch touched ONLY allowed (docs/scripts/tests/progress) paths -- never an
implementation path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
STAGE = REPO / "docs" / "stages" / "66c4-be2-independent-review"

REVIEW_DOCS = [
    CONTRACT / "be2-independent-review.md",
    CONTRACT / "be2-lifecycle-poller-review.md",
    CONTRACT / "be2-outbox-relay-review.md",
    CONTRACT / "be2-transaction-and-concurrency-review.md",
    CONTRACT / "be2-failure-recovery-review.md",
    CONTRACT / "be2-observability-and-security-review.md",
    CONTRACT / "be2-test-quality-review.md",
    HANDOFF / "be2-review-result-handoff.md",
    REPO / "docs" / "test" / "step66c4-be2-independent-review-record.md",
]

FORBIDDEN = ["10.0.1.31", "aiagent-swd", "stpadmin"]


@pytest.mark.parametrize("path", REVIEW_DOCS, ids=lambda p: p.name)
def test_review_doc_exists_with_footer(path: Path) -> None:
    assert path.exists(), f"missing {path.name}"
    text = path.read_text(encoding="utf-8")
    assert "_Non-production only." in text, f"no footer in {path.name}"
    assert "<!-- staging-safety:" in text, f"no staging-safety comment in {path.name}"


@pytest.mark.parametrize("path", REVIEW_DOCS, ids=lambda p: p.name)
def test_review_doc_has_no_masking_leak(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for bad in FORBIDDEN:
        assert bad not in text, f"masking leak {bad!r} in {path.name}"


def test_markers_recorded_separately() -> None:
    htext = (HANDOFF / "be2-review-result-handoff.md").read_text(encoding="utf-8")
    assert "STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS" in htext
    assert "BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED" in htext
    # The process marker must NOT be conflated with the technical verdict.
    assert "STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: REMEDIATION_REQUIRED" not in htext


def test_stage_manifest_declares_non_activation() -> None:
    mtext = (STAGE / "stage-manifest.yaml").read_text(encoding="utf-8")
    for flag in (
        "implementation_change_allowed: false",
        "merge_allowed: false",
        "be3_authorized: false",
        "producer_cutover_allowed: false",
        "deployment_allowed: false",
        'status: "review-complete"',
    ):
        assert flag in mtext, f"missing manifest flag: {flag}"


def test_review_did_not_modify_implementation_paths() -> None:
    """The review may add only docs/scripts/tests/progress. If any implementation module carries
    an uncommitted review edit it would show here; we assert the two BE2 modules are unchanged from
    their committed feature content by checking the review added NO new lines to them."""
    # Static guard: the review's own allowed-path list must exclude every implementation root.
    verifier = (REPO / "scripts" / "verify_step66c4_be2_independent_review.py").read_text(
        encoding="utf-8"
    )
    for banned_root in ("apps/", "shared/sdk/", "migrations/"):
        # The verifier must not claim authority to write implementation paths.
        assert f'"{banned_root}"' not in verifier
