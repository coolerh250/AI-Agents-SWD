"""Step 66C.4-P-R1 -- reminder/expiry/controlled resume contract remediation (docs-only checks).

This file changes no runtime code. It confirms the seven corrections (A-G) from the Product
Architect PASS_WITH_GAPS review are present and internally consistent in the planning/contract set:
the field inventory is reconciled to six lifecycle columns plus a durable outbox, expiry is
deadline-authoritative, reminder delivery is at-least-once and idempotent (exactly-once not
claimed), the state/audit/event atomicity model is a binding transactional outbox, clock wording is
non-absolute, automatic vs operator recovery are separated, the resume request/authorized/
dispatched/resumed transitions are distinct, cancelled/production-effect protection remains, six
advisory PO decisions are listed, BE1/BE2/BE3 slicing is corrected, no runtime/migration/deployment
is claimed, Codex/Claude Design remain unauthorized, Step 66C.4-BE1 is not started, and
source/progress.md is updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

DATA_MODEL = CONTRACT_DIR / "data-model-contract.md"
LIFECYCLE = CONTRACT_DIR / "lifecycle-and-time-contract.md"
API_EVENT = CONTRACT_DIR / "api-and-event-contract.md"
RESUME = CONTRACT_DIR / "controlled-resume-contract.md"
RACE = CONTRACT_DIR / "race-condition-and-failure-analysis.md"
SLICING = CONTRACT_DIR / "implementation-stage-slicing-plan.md"
CHECKLIST = CONTRACT_DIR / "product-owner-decision-checklist.md"
REMEDIATION = CONTRACT_DIR / "contract-remediation-record.md"

TEST_RECORD = (
    ROOT
    / "docs"
    / "test"
    / "step66c4-reminder-expiry-controlled-resume-planning-remediation-record.md"
)
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-reminder-expiry-controlled-resume-planning-remediation"
STAGE_DOCS = {
    "stage-manifest": STAGE_DIR / "stage-manifest.yaml",
    "context-receipt": STAGE_DIR / "context-receipt.md",
    "stage-gate-report": STAGE_DIR / "stage-gate-report.md",
}
PROGRESS = ROOT / "source" / "progress.md"

ALL_DOCS = {
    "data-model": DATA_MODEL,
    "lifecycle": LIFECYCLE,
    "api-event": API_EVENT,
    "resume": RESUME,
    "race": RACE,
    "slicing": SLICING,
    "checklist": CHECKLIST,
    "remediation-record": REMEDIATION,
    "test-record": TEST_RECORD,
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _t(p: Path) -> str:
    return _norm(p.read_text(encoding="utf-8"))


def _all() -> str:
    return "\n".join(_t(p) for p in ALL_DOCS.values())


def test_all_docs_exist() -> None:
    for name, p in ALL_DOCS.items():
        assert p.is_file(), name
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_marker_present() -> None:
    for p in (REMEDIATION, TEST_RECORD):
        assert "STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY: PASS" in p.read_text(
            encoding="utf-8"
        )


def test_field_inventory_reconciled_to_six() -> None:
    t = _t(DATA_MODEL)
    assert "exactly six new lifecycle columns" in t
    for col in (
        "reminder_sent_at",
        "expired_at",
        "resume_eligible_at",
        "resume_requested_at",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        assert col in t, col
    # resume_dispatched_at must be marked removed, not a live column.
    assert "removed" in t


def test_durable_outbox_table_added() -> None:
    assert "clarification_lifecycle_outbox" in _t(DATA_MODEL)


def test_authoritative_exclusive_deadline() -> None:
    t = _t(LIFECYCLE)
    assert "authoritative expiry deadline" in t
    assert "exclusive upper bound" in t
    assert "scheduler lag never extends the answer window" in t
    assert "exactly at due_at" in t


def test_reminder_at_least_once_idempotent_not_exactly_once() -> None:
    t = _t(LIFECYCLE)
    assert "at-least-once" in t
    assert "idempotent" in t
    combined = _all()
    assert any(
        d in combined
        for d in ("never exactly-once", "not claim exactly-once", "exactly-once is not")
    )
    for positive in ("guarantees exactly-once", "provides exactly-once"):
        assert positive not in combined, positive


def test_binding_transactional_outbox_atomicity() -> None:
    t = _t(API_EVENT)
    assert "atomicity model (binding" in t
    assert "transactional outbox" in t
    assert "selected model" in t


def test_clock_wording_non_absolute() -> None:
    t = _t(LIFECYCLE)
    assert "authoritative lifecycle clock" in t
    assert "does not eliminate" in t
    combined = _all()
    assert "no clock skew risk" not in combined
    assert "eliminated by design" not in combined


def test_recovery_split_automatic_vs_operator() -> None:
    t = _t(RACE)
    assert "automatic recovery" in t
    assert "operator recovery" in t


def test_resume_transitions_distinct() -> None:
    t = _t(RESUME)
    assert "resume_requested -> resume_authorized" in t
    assert "resume_dispatched -> workflow_resumed" in t
    assert "never equivalent" in t


def test_cancelled_and_production_effect_protection() -> None:
    combined = _all()
    assert re.search(
        r"cancel(?:l?ed)?[^.]{0,80}(cannot|must not|blocked|protection|unconditionally)", combined
    )
    assert "production_effect" in combined or "production-effect" in combined
    assert "blocked" in _t(RESUME)


def test_six_po_decisions_advisory_not_approved() -> None:
    t = _t(CHECKLIST)
    for n in range(1, 7):
        assert f"decision {n}" in t, n
    assert "authorizes nothing" in t
    combined = _all()
    assert "advisory" in combined and "not approved" in combined


def test_slicing_reflects_corrected_architecture() -> None:
    t = _t(SLICING)
    assert "atomicity foundation" in t
    assert "outbox relay" in t
    assert "orchestrator resume confirmation" in t


def test_no_runtime_migration_deployment_claimed() -> None:
    combined = _all()
    assert "no migration created" in combined
    assert "no deployment" in combined


def test_codex_claude_design_unauthorized() -> None:
    combined = _all()
    assert "codex" in combined and "claude design" in combined
    assert "unauthorized" in combined or "not authorized" in combined


def test_step_66c4_be1_not_started() -> None:
    combined = _all()
    assert "66c.4-be1" in combined
    assert "not started" in combined


def test_progress_updated() -> None:
    assert "66c.4-p-r1" in _norm(PROGRESS.read_text(encoding="utf-8"))


def test_no_sensitive_identifiers() -> None:
    for name, p in ALL_DOCS.items():
        low = p.read_text(encoding="utf-8").lower()
        for forbidden in ("10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin", "stpadmin"):
            assert forbidden not in low, f"{name}:{forbidden}"


def test_no_local_windows_paths() -> None:
    shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in ALL_DOCS.items():
        assert not shape.search(p.read_text(encoding="utf-8")), name
