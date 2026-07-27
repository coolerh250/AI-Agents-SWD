#!/usr/bin/env python3
"""Step 66C.4-BE3-C -- authorized dead-event replay self-verifier.

Static/structural checks that the two-person-controlled dead-event replay foundation is present and
safe: durable replay-request lifecycle, canonical TASK_ROLES reuse, requester/approver two-person
control, Service-Identity-only execution, single-use/state-bound/time-bound authorization (BE3-A,
unchanged), dead-only eligibility, exact null-safe scope, preserved original event identity/attempts,
replay_dead called ONLY via the authorized internal adapter, execution gate disabled-by-default,
mandatory destination readiness, independent production gate, atomic replay+audit transaction, NO
public execute endpoint, and NO shared migration/deployment/activation.

Marker: STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIG = ROOT / "migrations" / "034_be3_replay_requests.sql"
MIG_DOWN = ROOT / "migrations" / "034_be3_replay_requests_down.sql"
MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
REPOSITORY = ROOT / "shared" / "sdk" / "tasks" / "replay_request_repository.py"
SERVICE = ROOT / "shared" / "sdk" / "tasks" / "replay_service.py"
API = ROOT / "apps" / "orchestrator" / "src" / "operations_replay_api.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
POLICY = ROOT / "shared" / "sdk" / "tasks" / "authorization_policy.py"
AUTHZ_SERVICE = ROOT / "shared" / "sdk" / "tasks" / "authorization_service.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_c_authorized_replay.py"
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
REC = CONTRACT / "be3-c-authorized-dead-event-replay-record.md"
HANDOFF = (
    ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-abc-to-combined-review-handoff.md"
)

BASE = "5745ab7"
MARKER = "STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (
        MIG,
        MIG_DOWN,
        MODEL,
        REPOSITORY,
        SERVICE,
        API,
        OUTBOX,
        POLICY,
        AUTHZ_SERVICE,
        TESTS,
        REC,
        HANDOFF,
    ):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    mig = MIG.read_text(encoding="utf-8")
    model = MODEL.read_text(encoding="utf-8")
    repo_src = REPOSITORY.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")
    authz_service = AUTHZ_SERVICE.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    # 1. Replay request lifecycle durable.
    if "CREATE TABLE IF NOT EXISTS replay_requests" not in mig:
        bad("check1: migration does not create replay_requests")
    for st in (
        "authorization_pending",
        "authorized",
        "executed",
        "rejected",
        "canceled",
        "expired",
    ):
        if st not in mig or st not in model:
            bad(f"check1: replay request state missing: {st}")
    if "uq_rpr_active_per_event" not in mig:
        bad("check1: one-active-replay-request-per-event index missing")

    # 2. Canonical TASK_ROLES reused (no second RBAC).
    if "_APPROVER_ROLES" not in api or "reviewer_approver" not in api:
        bad("check2: replay API does not reuse the canonical approver roles")
    if "from shared.sdk.tasks.rbac import TASK_ROLES" not in policy:
        bad("check2: policy does not reuse the canonical TASK_ROLES")

    # 3. Requester/Approver two-person control.
    if "two_person_required" not in policy:
        bad("check3: two-person policy check missing")
    if "requester_cannot_approve" not in service:
        bad("check3: replay service does not surface the two-person denial")
    if "def test_pg_requester_cannot_self_approve" not in tests:
        bad("check3: no test proves the requester cannot self-approve a replay")

    # 4. Service Identity only executes.
    if "authz.consume" not in service or "is_service_identity" not in policy:
        bad("check4: execution does not consume via the Service Identity path")
    if "execute_authorized_replay(" in api:
        bad("check4: execution must NOT be exposed as an endpoint (found a call in the API module)")

    # 5. Authorization single-use/state-bound/time-bound (BE3-A, reused unchanged).
    if "consumed_at IS NULL" not in (
        ROOT / "shared" / "sdk" / "tasks" / "authorization_repository.py"
    ).read_text(encoding="utf-8"):
        bad("check5: authorization consume CAS guard missing")
    # 5b. request_authorization's create_request runs inside its own savepoint, so a concurrent
    # loser's UniqueViolationError never poisons a caller's outer transaction (BE3-C composability;
    # replay has no pre-authorization claim gate like resume's clarification CAS).
    if "async with conn.transaction():" not in authz_service:
        bad("check5: request_authorization does not savepoint-protect create_request")

    if "async def request_replay" not in service or "async with conn.transaction():" not in service:
        bad("check5: replay_service does not savepoint-protect its own request path")

    # 6. Only-dead eligibility.
    if 'status == "dead"' not in service and '!= "dead"' not in service:
        bad("check6: replay eligibility does not gate on dead state")
    if "already_published" not in model or "not_dead" not in model:
        bad("check6: dead-only reason codes missing")

    # 7. Scope + NULL fail-closed.
    if "IS NOT DISTINCT FROM" not in repo_src or "IS NULL OR" in repo_src:
        bad("check7: repository scope predicate is not exact null-safe equality")
    if (
        "team_id                 UUID NOT NULL" not in mig
        or "project_id              UUID NOT NULL" not in mig
    ):
        bad("check7: replay request scope columns are not NOT NULL")

    # 8. Original event identity preserved.
    if "def replay_dead_row" not in repo_src:
        bad("check8: transaction-aware replay adapter missing")
    if "def test_pg_valid_execution_preserves_identity_and_increments_episode" not in tests:
        bad("check8: no test proves original event identity is preserved")

    # 9. Attempts not reset.
    if "plan_replay_state" not in repo_src:
        bad("check9: replay adapter does not reuse the attempts-preserving plan_replay_state")
    if "NOT reset" not in repo_src and "does NOT reset attempts" not in repo_src:
        bad("check9: attempts-preserving semantics undocumented")

    # 10. replay_dead called ONLY via the authorized internal adapter.
    if "async def replay_dead(" in service or "async def replay_dead(" in api:
        bad("check10: a parallel replay_dead definition exists outside the repository adapter")
    if re.search(r"outbox_relay\.replay_dead\s*\(", service):
        bad("check10: service calls the RELAY's OWN self-transactional replay_dead")

    # 11. Execution gate disabled-by-default.
    if 'get("BE3_REPLAY_EXECUTION_ENABLED", "false")' not in model:
        bad("check11: execution gate is not disabled-by-default")
    if "def test_pg_execution_gate_disabled_no_consume_no_mutation" not in tests:
        bad("check11: no test proves the execution gate blocks consume/mutation")

    # 12. Destination readiness mandatory.
    if "readiness_provider" not in service or "READINESS_READY" not in model:
        bad("check12: execution does not require destination readiness")
    if "def default_destination_readiness" not in model:
        bad("check12: no default (never-ready) readiness provider")
    if "def test_pg_destination_unavailable_blocks_no_consume_no_mutation" not in tests:
        bad("check12: no test proves destination-not-ready blocks execution")

    # 13. Production approval remains independent.
    if "production_approval_required" not in policy:
        bad("check13: production approval gate missing from policy")
    if "def test_pg_production_effect_derived_not_client_trusted" not in tests:
        bad("check13: no test proves production_effect is server-derived, not client-trusted")

    # 14. Replay + audit transaction atomic.
    if "def test_pg_execution_failure_rolls_back_consume" not in tests:
        bad("check14: no test proves a post-consume execution failure rolls back the consume")
    if "def test_pg_audit_insertion_failure_rolls_back_execution" not in tests:
        bad("check14: no test proves an audit-insertion failure rolls back the whole execution")

    # 15. No public execute endpoint (a real @router.<verb>("/execute"...) registration, not prose).
    for banned in ('"/execute', "'/execute", '"/replay-now', "'/replay-now"):
        if banned in api:
            bad(f"check15: replay API appears to register an execute route: {banned}")
    if "execute_authorized_replay(" in api:
        bad("check15: replay API calls execute_authorized_replay directly")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 16. No shared DB migration/deployment/activation.
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check16: forbidden deployment/activation path changed: {f}")
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if any(not Path(f).name.startswith(("032_", "033_", "034_")) for f in mig_changed):
        bad(f"check16: an unexpected migration was changed: {mig_changed}")
    for banned in ("workflow_resume", "run_mock_workflow"):
        if banned in service or banned in api:
            bad(f"check16: forbidden execution/dispatch reference: {banned}")

    # 17-18. Draft PR unmerged; combined BE3-R the next required gate.
    rec = REC.read_text(encoding="utf-8").lower()
    if "not for merge" not in rec and "not merged" not in rec:
        bad("check17: record does not state the Draft PR is not merged")
    if "be3-r" not in rec:
        bad(
            "check18: record does not state the combined independent BE3-R is the next required gate"
        )
    handoff = HANDOFF.read_text(encoding="utf-8").lower()
    if "be3-r" not in handoff:
        bad("check18: BE3-A/B/C to combined review handoff does not name BE3-R as next")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] durable replay_requests lifecycle (migration 034, one-active-per-event);")
    print("       canonical TASK_ROLES reused (Approver: reviewer_approver/platform_admin);")
    print("       requester != approver two-person control (policy + DB constraint, unchanged")
    print("       from BE3-A); Service-Identity-only execution (no endpoint); dead-only")
    print("       eligibility; exact null-safe NOT NULL scope; transaction-aware replay_dead_row")
    print("       adapter preserves event_id/idempotency_key/payload/created_at and does NOT")
    print("       reset attempts; execution gate disabled-by-default; destination readiness is")
    print("       mandatory (never assumed ready); production gate independent; consume + replay")
    print("       + audit commit/rollback atomically; NO public execute endpoint; NO shared")
    print("       migration/deployment/activation.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-C self-verification only; overall BE3 technical closure needs the combined")
    print("        independent BE3-R review over BE3-A+B+C. Draft PR #20 remains NOT FOR MERGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
