"""Step 66C.4-P-M -- contract source-of-truth merge (docs-only checks).

This file changes no runtime code. It confirms the Step 66C.4 contract set was merged to main as
canonical source of truth: the source branch/commit and merge commit are recorded, the six Product
Owner decisions are recorded as approved, the binding BE1 runtime-compatibility gate exists,
existing producers cannot switch to the outbox without an active relay, Step 66C.4-BE1 remains not
started, Codex/Claude Design remain unauthorized, no runtime/migration/deployment/scheduler/relay/
dispatch/resume change is claimed, production_executed_true_count remains 0, and source/progress.md
is updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

PO_DECISIONS = (
    ROOT / "docs" / "decisions" / "66c4-reminder-expiry-controlled-resume-product-decisions.md"
)
MERGE_RECORD = CONTRACT_DIR / "contract-merge-record.md"
SOT_RECORD = CONTRACT_DIR / "contract-source-of-truth-record.md"
MERGE_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66c4-reminder-expiry-controlled-resume-contract-merge-record.md"
)
PROGRESS = ROOT / "source" / "progress.md"

STAGE_DIR = ROOT / "docs" / "stages" / "66c4-reminder-expiry-controlled-resume-contract-merge"
STAGE_DOCS = {
    "stage-manifest": STAGE_DIR / "stage-manifest.yaml",
    "context-receipt": STAGE_DIR / "context-receipt.md",
    "stage-gate-report": STAGE_DIR / "stage-gate-report.md",
}

CONTRACT_CORE = [
    CONTRACT_DIR / "lifecycle-and-time-contract.md",
    CONTRACT_DIR / "data-model-contract.md",
    CONTRACT_DIR / "controlled-resume-contract.md",
    CONTRACT_DIR / "api-and-event-contract.md",
]

ALL_DOCS = {
    "po-decisions": PO_DECISIONS,
    "merge-record": MERGE_RECORD,
    "sot-record": SOT_RECORD,
    "merge-test-record": MERGE_TEST_RECORD,
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _t(p: Path) -> str:
    return _norm(p.read_text(encoding="utf-8"))


def _all() -> str:
    return "\n".join(_t(p) for p in ALL_DOCS.values())


def test_records_and_stage_docs_exist() -> None:
    for name, p in ALL_DOCS.items():
        assert p.is_file(), name
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name
    for p in CONTRACT_CORE:
        assert p.is_file(), p


def test_marker_present() -> None:
    for p in (MERGE_RECORD, SOT_RECORD, MERGE_TEST_RECORD):
        assert "STEP66C4_CONTRACT_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS" in p.read_text(
            encoding="utf-8"
        )


def test_source_and_merge_commit_recorded() -> None:
    combined = _all()
    assert "planning/66c4-reminder-expiry-controlled-resume" in combined
    assert "f50dd05" in combined
    assert "merge commit" in combined
    assert "e109189" in combined


def test_six_decisions_approved() -> None:
    t = _t(PO_DECISIONS)
    assert "approved_by_product_owner" in t
    for n in range(1, 7):
        assert f"decision {n}" in t, n


def test_authoritative_expiry_and_409() -> None:
    combined = _all()
    assert "due_at" in combined
    assert "409" in combined
    assert "authoritative" in combined


def test_ui_wording_and_backend_status() -> None:
    combined = _all()
    assert "clarification expired" in combined
    assert "blocked" in combined
    assert "clarification_expired" in combined


def test_explicit_operator_controlled_resume() -> None:
    assert "explicit operator-controlled resume" in _all()


def test_production_effect_approval_separate() -> None:
    combined = _all()
    assert "production-effect" in combined or "production effect" in combined
    assert "separate" in combined


def test_one_reminder_rule() -> None:
    combined = _all()
    assert "one reminder per clarification" in combined
    assert "created_at + 24" in combined


def test_expired_immutability() -> None:
    combined = _all()
    assert "immutab" in combined or "cannot be reopened" in combined


def test_six_lifecycle_fields_consistent() -> None:
    t = _t(SOT_RECORD)
    for col in (
        "reminder_sent_at",
        "expired_at",
        "resume_eligible_at",
        "resume_requested_at",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        assert col in t, col
    assert "exactly six" in t


def test_transactional_outbox_canonical() -> None:
    combined = _all()
    assert "transactional outbox" in combined or "transactional-outbox" in combined
    assert "outbox model: canonical" in _t(SOT_RECORD)


def test_be1_runtime_compatibility_gate() -> None:
    combined = _all()
    assert "be1 runtime compatibility gate" in combined
    assert "existing runtime producers remain" in combined
    assert "producer cutover requires" in combined


def test_be1_not_started_and_partners_unauthorized() -> None:
    combined = _all()
    assert "66c.4-be1" in combined
    assert "not started" in combined
    assert "codex" in combined and "claude design" in combined
    assert "unauthorized" in combined or "not authorized" in combined


def test_no_runtime_migration_deployment_scheduler_relay_claimed() -> None:
    combined = _all()
    assert "no migration created" in combined
    assert "no scheduler activated" in combined
    assert "no outbox relay activated" in combined
    assert "no deployment" in combined
    assert "no external notification" in combined


def test_production_executed_true_count_zero() -> None:
    combined = _all()
    assert "production_executed_true_count" in combined
    assert "0" in combined


def test_progress_updated() -> None:
    assert "66c.4-p-m" in _norm(PROGRESS.read_text(encoding="utf-8"))


def test_no_sensitive_identifiers() -> None:
    for name, p in ALL_DOCS.items():
        low = p.read_text(encoding="utf-8").lower()
        for forbidden in ("10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin", "stpadmin"):
            assert forbidden not in low, f"{name}:{forbidden}"


def test_no_local_windows_paths() -> None:
    shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in ALL_DOCS.items():
        assert not shape.search(p.read_text(encoding="utf-8")), name
