"""Step 66C.4-BE3-P -- planning-contract tests.

Static tests over the committed BE3-P contract artifacts. No DB, no network, no runtime. They assert
the resume/replay authorization contract is complete and that this planning stage introduced NO
backend/API/migration/frontend/deployment code.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"

MASTER = CONTRACT / "be3-operator-resume-replay-authorization-contract.md"
RBAC = CONTRACT / "be3-rbac-permission-matrix.md"
SM = CONTRACT / "be3-resume-replay-state-machine.md"
API = CONTRACT / "be3-api-event-contract.md"
SEC = CONTRACT / "be3-security-and-threat-model.md"
GATE = CONTRACT / "be3-runtime-activation-gate.md"
SLICE = CONTRACT / "be3-implementation-slicing-plan.md"
HANDOFF_DOC = HANDOFF / "be3-implementation-handoff.md"

BASE = "33b776b"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing: {p}"
    return p.read_text(encoding="utf-8")


def test_all_be3p_artifacts_exist() -> None:
    for p in (MASTER, RBAC, SM, API, SEC, GATE, SLICE, HANDOFF_DOC):
        assert p.is_file(), p


def test_rbac_reuses_six_canonical_roles_and_covers_actions() -> None:
    t = _read(RBAC)
    for role in (
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    ):
        assert role in t, role
    for action in (
        "request resume",
        "authorize resume",
        "execute resume",
        "request replay",
        "authorize replay",
        "execute replay",
        "override policy",
        "view authorization evidence",
    ):
        assert action in t, action
    # Boundaries: two-person replay + service-identity execute-only.
    assert "two-person" in t
    assert "requester_principal != approver_principal" in t
    assert "can never" in t  # service identity cannot request/authorize


def test_resume_and_replay_state_machines_complete() -> None:
    t = _read(SM)
    for st in (
        "not_eligible",
        "eligible",
        "request_pending",
        "authorization_pending",
        "authorized",
        "execution_pending",
        "resumed",
        "rejected",
        "canceled",
        "expired",
        "failed",
    ):
        assert st in t, st
    for st in ("replay_requested", "replay_authorized", "replayed", "replay_failed"):
        assert st in t, st
    for field in ("Actor", "Precondition", "Idem key", "Tx boundary", "Audit event", "Failure"):
        assert field in t, field
    assert "attempts NOT reset" in t or "attempts are never reset" in t


def test_durable_authorization_model_and_semantics() -> None:
    t = _read(API)
    for field in (
        "authorization_id",
        "action_type",
        "resource_id",
        "authorized_by",
        "decision_reason_code",
        "policy_version",
        "expires_at",
        "consumed_at",
        "idempotency_key",
    ):
        assert field in t, field
    for sem in (
        "single-use",
        "time-bounded",
        "state-version-bound",
        "resource-bound",
        "action-bound",
    ):
        assert sem in t, sem
    assert "revocation" in t or "revoke" in t


def test_api_contract_defines_errors_and_routes() -> None:
    t = _read(API)
    for token in ("403", "404", "409", "idempotency", "no-side-effect"):
        assert token in t, token
    assert "/operations/resume-requests" in t
    assert "/operations/replay-requests" in t


def test_event_contract_and_single_destination() -> None:
    t = _read(API)
    for ev in (
        "resume.requested",
        "resume.authorized",
        "resume.execution_requested",
        "resume.resumed",
        "replay.requested",
        "replay.authorized",
        "replay.executed",
    ):
        assert ev in t, ev
    assert "single durable destination" in t.lower() or "one durable destination" in t.lower()
    assert "exactly-once is NOT claimed" in t


def test_concurrency_cases_present() -> None:
    t = _read(API)
    for scen in (
        "two operators request the same resume",
        "authorization expires during execution",
        "resume executes twice",
        "replay executes twice",
        "orchestrator ack lost",
    ):
        assert scen in t, scen


def test_activation_gate_complete_and_disabled_by_default() -> None:
    t = _read(GATE)
    for pre in (
        "Migration 031",
        "BE3 authorization migration",
        "Lifecycle poller deployed",
        "Outbox relay deployed",
        "Rollback tested",
        "Producer cutover plan approved",
        "Runtime E2E",
        "Product Owner deployment authorization",
    ):
        assert pre in t, pre
    assert "DISABLED-BY-DEFAULT" in t


def test_replay_stays_internal_only() -> None:
    assert "internal-only" in _read(MASTER)
    assert "public replay endpoint" in _read(SEC)
    assert "internal adapter only" in _read(SLICE)


def test_slicing_plan_matches_new_verification_policy() -> None:
    t = _read(SLICE)
    for s in ("BE3-A", "BE3-B", "BE3-C", "BE3-R", "BE3-M"):
        assert s in t, s
    assert "one independent" in t.lower()
    assert "focused closure" in t
    for field in ("Allowed files", "Forbidden files", "Entry criteria", "Exit criteria", "Risk"):
        assert field in t, field


def test_no_backend_api_migration_frontend_deployment_code_changed() -> None:
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{BASE}...HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.split()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.split()
    for f in changed + untracked:
        for forbidden in ("apps/", "shared/", "migrations/", "frontend/", "services/", "infra/"):
            assert not f.startswith(forbidden), f"planning stage changed code path: {f}"
