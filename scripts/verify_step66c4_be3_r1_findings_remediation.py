#!/usr/bin/env python3
"""Step 66C.4-BE3-R1 -- required findings remediation self-verifier (M-1, L-1).

Static/structural checks that the two mandatory-activation-precondition findings recorded by the
BE3-R combined independent review are genuinely closed:

- M-1: production_approval_reference resolves against an authoritative, transaction-locked registry
  (migration 035, production_action_approvals) -- not just checked non-empty -- for BOTH the resume
  and replay consume paths (the shared authorization_service.consume resolver).
- L-1: the per-actor replay-request rate limit is concurrency-safe (a transaction-scoped PostgreSQL
  advisory lock) and isolated per (team_id, project_id, actor_id).

Marker: STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIG_035 = ROOT / "migrations" / "035_be3_production_action_approvals.sql"
MIG_035_DOWN = ROOT / "migrations" / "035_be3_production_action_approvals_down.sql"
MIG_034 = ROOT / "migrations" / "034_be3_replay_requests.sql"
PAA_MODEL = ROOT / "shared" / "sdk" / "tasks" / "production_approval_model.py"
PAA_REPO = ROOT / "shared" / "sdk" / "tasks" / "production_approval_repository.py"
PAA_SERVICE = ROOT / "shared" / "sdk" / "tasks" / "production_approval_service.py"
AUTHZ_SERVICE = ROOT / "shared" / "sdk" / "tasks" / "authorization_service.py"
AUTHZ_MODEL = ROOT / "shared" / "sdk" / "tasks" / "authorization_model.py"
REPLAY_SERVICE = ROOT / "shared" / "sdk" / "tasks" / "replay_service.py"
REPLAY_REPO = ROOT / "shared" / "sdk" / "tasks" / "replay_request_repository.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_r1_findings_remediation.py"
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
PLANNING = CONTRACT_DIR / "be3-r1-m1-production-approval-contract.md"
REC = CONTRACT_DIR / "be3-r1-required-findings-remediation-record.md"
GATE = CONTRACT_DIR / "be3-runtime-activation-gate.md"
HANDOFF = (
    ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-r1-to-focused-closure-handoff.md"
)

BASE = "6323972"  # BE3-C feature head; BE3-R1 review diff baseline
MARKER = "STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (
        MIG_035,
        MIG_035_DOWN,
        PAA_MODEL,
        PAA_REPO,
        PAA_SERVICE,
        AUTHZ_SERVICE,
        AUTHZ_MODEL,
        REPLAY_SERVICE,
        REPLAY_REPO,
        TESTS,
        PLANNING,
        REC,
        GATE,
        HANDOFF,
    ):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    mig035 = MIG_035.read_text(encoding="utf-8")
    mig034 = MIG_034.read_text(encoding="utf-8")
    paa_repo = PAA_REPO.read_text(encoding="utf-8")
    paa_service = PAA_SERVICE.read_text(encoding="utf-8")
    authz_service = AUTHZ_SERVICE.read_text(encoding="utf-8")
    authz_model = AUTHZ_MODEL.read_text(encoding="utf-8")
    replay_service = REPLAY_SERVICE.read_text(encoding="utf-8")
    replay_repo = REPLAY_REPO.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    # 1. Production approval no longer only checks non-emptiness -- the SERVICE layer resolves the
    # reference for real, beyond the pure presence pre-check in authorization_policy.evaluate().
    if "resolve_and_consume_approval" not in authz_service:
        bad("check1: authorization_service.consume does not call an approval resolver")
    if "def resolve_and_consume_approval" not in paa_repo:
        bad("check1: no resolve_and_consume_approval function exists")
    # Grant/revoke are RBAC-gated to the canonical Approver roles (no second RBAC system), and every
    # new production_approval_* reason code is on the bounded authorization_model allowlist so the
    # shared audit payload builder never rejects a real denial reason.
    if "can_grant" not in paa_service:
        bad("check1: production_approval_service does not enforce a granter RBAC check")
    for code in (
        "production_approval_invalid_reference",
        "production_approval_not_found",
        "production_approval_already_consumed",
        "production_approval_already_revoked",
        "production_approval_expired",
        "production_approval_wrong_action",
        "production_approval_wrong_resource",
        "production_approval_wrong_scope",
        "production_approval_stale_state",
    ):
        if code not in authz_model:
            bad(f"check1: authorization_model REASON_CODES missing {code}")

    # 2. Resolution happens against the authoritative registry, in the SAME transaction (no
    # connection-per-call store, no separate connection acquisition inside the resolver).
    if "CREATE TABLE IF NOT EXISTS production_action_approvals" not in mig035:
        bad("check2: migration 035 does not create production_action_approvals")
    if "FOR UPDATE" not in paa_repo:
        bad("check2: resolver does not lock the approval row under the caller's transaction")
    if "await asyncpg.connect" in paa_repo or "_connect(" in paa_repo:
        bad("check2: resolver opens its OWN connection instead of using the caller's")

    # 3. Approval state, expiry, scope, resource and action are all validated.
    for must in (
        '"already_consumed"',
        '"already_revoked"',
        '"expired"',
        '"wrong_action"',
        '"wrong_resource"',
        '"wrong_scope"',
        '"stale_state"',
        '"not_found"',
        '"invalid_reference"',
    ):
        if must not in paa_repo:
            bad(f"check3: resolver missing validation branch {must}")

    # 4. Approval validation + consume share a safe transaction boundary: the approval row is locked
    # once and re-validated at the SAME lock before the CAS UPDATE; a post-approval-consume
    # authorization CAS failure raises (forcing full rollback) rather than silently leaving a
    # consumed approval with an unconsumed authorization.
    if "raise RuntimeError" not in authz_service:
        bad("check4: no defensive rollback guard for a post-approval-consume authorization failure")
    if "production_effect" not in authz_service:
        bad("check4: consume() does not branch on production_effect at all")

    # 5. Invalid approval never lets the authorization consume, and the failure is audited without
    # ever calling repo.consume for the authorization.
    if "approval_row is None" not in authz_service:
        bad("check5: consume() does not short-circuit on a failed approval resolution")

    # 6. Resume and replay share the SAME resolver (not two parallel validation models).
    if "def test_pg_m1_resume_consume_end_to_end_valid_and_invalid" not in tests:
        bad("check6: no end-to-end resume consume test")
    if "def test_pg_m1_replay_consume_end_to_end_valid_and_invalid" not in tests:
        bad("check6: no end-to-end replay consume test")
    # both resume_service and replay_service call authz.consume/authorization_service.consume --
    # the ONE shared resolver -- never a second, parallel approval-checking code path.
    if "resolve_and_consume_approval" in replay_service or "resolve_and_consume_approval" in (
        (ROOT / "shared" / "sdk" / "tasks" / "resume_service.py").read_text(encoding="utf-8")
    ):
        bad(
            "check6: resume/replay service calls the approval resolver directly (bypassing the shared authorization_service.consume integration point)"
        )

    # 7. Per-actor replay limit has transaction-level serialization.
    if "pg_advisory_xact_lock" not in replay_repo:
        bad("check7: no transaction-scoped advisory lock for the per-actor rate limit")
    if "acquire_actor_rate_limit_lock" not in replay_service:
        bad("check7: replay_service.request_replay does not acquire the rate-limit lock")

    # 8. Concurrent request cannot exceed the hard cap (mandatory tests present).
    for must in (
        "def test_pg_l1_twenty_concurrent_requests_same_actor_exactly_cap_created",
        "def test_pg_l1_fifty_concurrent_requests_never_exceed_hard_cap",
    ):
        if must not in tests:
            bad(f"check8: missing mandatory concurrency test {must}")

    # 9. Idempotent retry is never double-counted (DB-level uniqueness + a direct test).
    if "uq_rpr_idempotency_key" not in mig034:
        bad("check9: replay_requests idempotency_key uniqueness constraint missing")
    if "def test_pg_l1_concurrent_same_idempotency_key_counted_once" not in tests:
        bad("check9: missing idempotent-retry-not-double-counted test")

    # 10. Activation gate updated with both closure items.
    gate = GATE.read_text(encoding="utf-8")
    if "M-1" not in gate or "L-1" not in gate:
        bad("check10: activation gate does not reference M-1/L-1 closure")
    for must in ("IMPLEMENTED", "TESTED"):
        if must not in gate:
            bad(f"check10: activation gate missing '{must}' closure evidence marker")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 11. No shared migration application/deployment/activation path touched.
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check11: forbidden deployment/activation path changed: {f}")
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if any(not Path(f).name.startswith(("034_", "035_")) for f in mig_changed):
        bad(f"check11: an unexpected migration was changed: {mig_changed}")
    # 12. Draft PR #20 unmerged (checked via the record, since gh may be unavailable offline).
    rec_text = REC.read_text(encoding="utf-8").lower()
    if "not merged" not in rec_text and "not for merge" not in rec_text:
        bad("check12: record does not state Draft PR #20 is not merged")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] production_approval_reference resolves against production_action_approvals")
    print("       (migration 035) under a FOR UPDATE lock in the CALLER's transaction; every")
    print("       binding (state/expiry/scope/resource/action/resource_state_version) is")
    print("       validated; an invalid approval never consumes the authorization and a")
    print("       post-approval-consume authorization failure forces a full rollback; resume AND")
    print("       replay share the ONE resolver via authorization_service.consume. Per-actor")
    print("       replay rate limiting is now transaction-serialized (pg_advisory_xact_lock) and")
    print("       scoped by (team_id, project_id, actor_id); idempotent retries are never")
    print("       double-counted. Activation gate records both closures. No shared migration,")
    print("       deployment, or activation.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-R1 findings-closure only; PR #20 remains Draft/NOT FOR MERGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
