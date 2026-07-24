#!/usr/bin/env python3
"""Step 66C.4-BE3-A -- durable authorization foundation self-verifier.

Static/structural checks that the authorization migration, model, repository, policy and service
implement the BE3-A durable-authorization foundation WITHOUT any resume/replay execution, public
endpoint, dead-outbox replay invocation, shared activation, or deployment. This marker is BE3-A
self-verification only; it is NOT an overall BE3 technical PASS (the combined independent BE3-R
review over BE3-A+B+C is still required).

Marker: STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIG = ROOT / "migrations" / "032_be3_resume_replay_authorization.sql"
MIG_DOWN = ROOT / "migrations" / "032_be3_resume_replay_authorization_down.sql"
MODEL = ROOT / "shared" / "sdk" / "tasks" / "authorization_model.py"
REPOSITORY = ROOT / "shared" / "sdk" / "tasks" / "authorization_repository.py"
POLICY = ROOT / "shared" / "sdk" / "tasks" / "authorization_policy.py"
SERVICE = ROOT / "shared" / "sdk" / "tasks" / "authorization_service.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_a_authorization_foundation.py"
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
REC = CONTRACT / "be3-a-authorization-foundation-record.md"
HANDOFF = (
    ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-a-to-be3-b-handoff.md"
)

BASE = "5745ab7"
MARKER = "STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (MIG, MIG_DOWN, MODEL, REPOSITORY, POLICY, SERVICE, TESTS, REC, HANDOFF):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    mig = MIG.read_text(encoding="utf-8")
    model = MODEL.read_text(encoding="utf-8")
    repo_src = REPOSITORY.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    # 1. Authorization migration exists (checked above) + additive (creates the table).
    if "CREATE TABLE IF NOT EXISTS resume_replay_authorizations" not in mig:
        bad("check1: migration does not create resume_replay_authorizations")

    # 2. Durable authorization schema complete.
    for col in (
        "authorization_id",
        "action_type",
        "resource_type",
        "resource_id",
        "request_id",
        "requested_by",
        "decision",
        "decided_by",
        "decision_reason_code",
        "policy_result",
        "policy_version",
        "resource_state_version",
        "expires_at",
        "consumed_at",
        "consumed_by",
        "revoked_at",
        "idempotency_key",
    ):
        if col not in mig:
            bad(f"check2: authorization schema missing column: {col}")
    for con in (
        "chk_rra_action_type",
        "chk_rra_decision",
        "chk_rra_expiry_after_request",
        "chk_rra_consume_requires_authorized",
        "chk_rra_not_consumed_and_revoked",
        "uq_rra_active_request",
    ):
        if con not in mig:
            bad(f"check2: authorization schema missing constraint/index: {con}")

    # 3. Canonical TASK_ROLES reused (no second role system).
    if "from shared.sdk.tasks.rbac import TASK_ROLES" not in policy:
        bad("check3: policy does not reuse the canonical TASK_ROLES")

    # 4. Requester/approver separation (DB constraint + policy two-person).
    if "chk_rra_replay_two_person" not in mig:
        bad("check4: DB replay two-person constraint missing")
    if "two_person_required" not in policy:
        bad("check4: policy two-person separation missing")

    # 5. Service identity restrictions.
    if "is_service_identity" not in policy or "service_identity_cannot_decide" not in policy:
        bad("check5: service-identity restriction missing")
    if "_CONSUME_ACTIONS" not in policy:
        bad("check5: consume-only restriction for service identity missing")

    # 6. Single-use consume uses CAS.
    if "async def consume" not in repo_src:
        bad("check6: repository consume missing")
    if (
        "consumed_at IS NULL" not in repo_src
        or "expires_at > statement_timestamp()" not in repo_src
    ):
        bad("check6: consume CAS guard incomplete")
    if "resource_state_version=$3" not in repo_src:
        bad("check6: consume does not bind the resource_state_version")

    # 7. Expiry / revoke / state-version checks.
    if "async def revoke" not in repo_src or "async def expire_due_authorizations" not in repo_src:
        bad("check7: revoke/expire operations missing")
    if "stale_state" not in service or "expired" not in service:
        bad("check7: service does not classify expiry/state-version failures")

    # 8. Team/project/resource isolation.
    if "_isolation_ok" not in policy or "cross_team_denied" not in policy:
        bad("check8: team/project isolation missing in policy")
    if "idx_rra_scope" not in mig:
        bad("check8: isolation scan index missing")

    # 9. Production gate not replaced by general authorization.
    if "production_approval_required" not in policy:
        bad("check9: production gate missing from policy")
    if "production_effect" not in mig:
        bad("check9: production_effect not represented in schema")

    # 10. No public endpoint: the authorization modules register no route; no app imports them.
    for token in ("APIRouter", "@app.", "@router.", "add_api_route", "FastAPI("):
        if token in service or token in repo_src or token in policy:
            bad(f"check10: an authorization module looks like an HTTP route: {token}")
    for base in (ROOT / "apps",):
        for path in base.rglob("*.py"):
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"authorization_(service|repository|policy|model)\b", txt):
                bad(
                    f"check10: an app wires an authorization module (no endpoint allowed): "
                    f"{path.relative_to(ROOT)}"
                )

    # 11. No dead-outbox replay adapter call (no actual replay_dead invocation in the new modules).
    for src, name in (
        (model, "model"),
        (repo_src, "repository"),
        (policy, "policy"),
        (service, "service"),
    ):
        if re.search(r"replay_dead\s*\(", src):
            bad(f"check11: authorization {name} calls replay_dead")

    # 12. No resume/dispatch execution.
    for banned in ("publish_audit_event", "RedisStreamEventBus", "def dispatch", "workflow_resume"):
        if banned in service or banned in repo_src:
            bad(f"check12: resume/dispatch execution present: {banned}")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 13. No shared activation/deployment.
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check13: forbidden deployment/activation path changed: {f}")
    # only ONE new migration (032); no edit to an existing migration.
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if any(not Path(f).name.startswith("032_") for f in mig_changed):
        bad(f"check13: a non-032 migration was changed: {mig_changed}")

    # 14-16. Documented posture: Draft PR not merged; BE3-B/C not implemented; combined BE3-R required.
    rec = REC.read_text(encoding="utf-8").lower()
    if "not for merge" not in rec and "not merged" not in rec:
        bad("check14: record does not state the Draft PR is not merged")
    for mod in ("authorization_resume", "resume_endpoint", "replay_endpoint"):
        if (ROOT / "shared" / "sdk" / "tasks" / f"{mod}.py").exists():
            bad(f"check15: a BE3-B/C module already exists: {mod}")
    if "be3-r" not in rec or "independent" not in rec:
        bad("check16: record does not state the combined independent BE3-R is still required")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] migration 032 durable authorization schema (single-use/time-bound/state-version-")
    print("       bound/revocable, two-person replay constraint, isolation + expiry indexes);")
    print("       canonical TASK_ROLES reused; service-identity consume-only; CAS consume with")
    print("       state-version + expiry guards; production gate intact; NO public endpoint, NO")
    print("       dead-outbox replay call, NO resume/dispatch, NO shared activation/deployment;")
    print("       Draft PR not merged; BE3-B/C not implemented; combined BE3-R still required.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-A self-verification only; overall BE3 technical closure needs the combined")
    print("        independent BE3-R review over BE3-A+B+C.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
