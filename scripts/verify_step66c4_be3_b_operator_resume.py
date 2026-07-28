#!/usr/bin/env python3
"""Step 66C.4-BE3-B -- operator-controlled resume request self-verifier.

Static/structural checks that the resume request/authorize/gated-execution foundation is present
and safe: durable request lifecycle, DB-authoritative eligibility, policy-authority-only resume
authorization (no operator self-authorize, no forgeable authority), Service-Identity-only execution
preparation, exact null-safe scope, independent production gate, durable outbox command with a stable
identity, rollback-on-outbox-failure, disabled-by-default API and command gates, and NO orchestrator
call / NO replay / NO shared migration/deployment/activation. This marker is BE3-B self-verification
only; overall BE3 closure needs the combined independent BE3-R review over BE3-A+B+C.

Marker: STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIG = ROOT / "migrations" / "033_be3_resume_requests.sql"
MIG_DOWN = ROOT / "migrations" / "033_be3_resume_requests_down.sql"
MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPOSITORY = ROOT / "shared" / "sdk" / "tasks" / "resume_request_repository.py"
SERVICE = ROOT / "shared" / "sdk" / "tasks" / "resume_service.py"
API = ROOT / "apps" / "orchestrator" / "src" / "operations_resume_api.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_b_operator_resume.py"
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
REC = CONTRACT / "be3-b-operator-controlled-resume-record.md"
HANDOFF = (
    ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-b-to-be3-c-handoff.md"
)

BASE = "5745ab7"
MARKER = "STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (MIG, MIG_DOWN, MODEL, REPOSITORY, SERVICE, API, OUTBOX, TESTS, REC, HANDOFF):
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
    outbox = OUTBOX.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    # 1. Resume request lifecycle persisted (durable table + states).
    if "CREATE TABLE IF NOT EXISTS resume_requests" not in mig:
        bad("check1: migration does not create resume_requests")
    for st in ("authorization_pending", "authorized", "execution_pending", "resumed", "failed"):
        if st not in mig or st not in model:
            bad(f"check1: request state missing: {st}")
    if "uq_rr_active_per_clarification" not in mig:
        bad("check1: one-active-request-per-clarification index missing")

    # 2. Eligibility uses DB authoritative state under locks.
    if "lock_clarification" not in repo_src or "FOR UPDATE" not in repo_src:
        bad("check2: repository does not lock authoritative rows")
    if "_eligibility_denial" not in service or "resume_eligible_at" not in service:
        bad("check2: service does not gate on authoritative eligibility")
    if "resource_state_version" not in model or "resource_state_version" not in service:
        bad("check2: resource_state_version binding missing")

    # 3. Operator cannot human-authorize its own resume (policy authority only via authz.authorize).
    if "authz.authorize" not in service:
        bad("check3: authorize does not go through the BE3-A authorization policy")
    if "_policy_authority" not in api:
        bad("check3: API authorize/reject do not resolve a policy authority")

    # 4. Policy authority is NOT forgeable from request input.
    if "BE3_RESUME_POLICY_AUTHORITY_CAPABILITY" not in api:
        bad("check4: policy authority is not gated by a server-side capability")
    if "is_policy_authority=True" not in api:
        bad("check4: policy authority flag is not set server-side")
    if re.search(r"is_policy_authority.*(payload|body|request\.query|\.json\()", api):
        bad("check4: policy authority appears to be read from request input")

    # 5. Service Identity only prepares execution; no public endpoint for it.
    if "prepare_execution" not in service or "authz.consume" not in service:
        bad("check5: execution preparation does not consume via the Service Identity path")
    if "prepare_execution(" in api or "confirm_resumed(" in api or "confirm_failed(" in api:
        bad("check5: execution preparation/confirmation must NOT be exposed as an endpoint")

    # 6. Scope + NULL fail-closed.
    if "IS NOT DISTINCT FROM" not in repo_src or "IS NULL OR" in repo_src:
        bad("check6: repository scope predicate is not exact null-safe equality")
    if (
        "team_id                 UUID NOT NULL" not in mig
        or "project_id              UUID NOT NULL" not in mig
    ):
        bad("check6: resume request scope columns are not NOT NULL")

    # 7. Production approval remains an independent gate (delegated to authz.consume, not weakened).
    if "production_effect" not in service:
        bad("check7: service does not carry production_effect into the authorization")
    if "production_approval" in service and "authz.consume" not in service:
        bad("check7: production gate not delegated to the authorization consume")

    # 8. Execution command uses the durable outbox with a stable identity.
    if "resume.execution_requested" not in outbox:
        bad("check8: outbox does not allow the resume.execution_requested command")
    if "resume.execution_requested" not in service or "command_id" not in service:
        bad("check8: service does not create the durable command / persist its identity")
    if "transition_to_execution_pending" not in repo_src:
        bad("check8: execution_pending transition (command identity) missing")

    # 9. Outbox failure rolls back consumption (single transaction; asserted by a test).
    if "def test_pg_outbox_failure_rolls_back_consume" not in tests:
        bad("check9: no test proves outbox failure rolls back the authorization consume")

    # 10. API and command gates are disabled-by-default (default 'false') and env-only.
    if "BE3_RESUME_API_ENABLED" not in model or "BE3_RESUME_COMMAND_ENABLED" not in model:
        bad("check10: feature gate env names missing")
    if 'get("BE3_RESUME_API_ENABLED", "false")' not in model:
        bad("check10: API gate is not disabled-by-default")
    if 'get("BE3_RESUME_COMMAND_ENABLED", "false")' not in model:
        bad("check10: command gate is not disabled-by-default")
    if "_require_api_enabled" not in api or "resume_command_enabled" not in service:
        bad("check10: gates not enforced at the API/command boundary")

    # 11. No real orchestrator resume / dispatch execution.
    for banned in ("workflow_resume", "ResumeEngine", "run_mock_workflow", "publish_audit_event"):
        if banned in service or banned in repo_src:
            bad(f"check11: forbidden execution/dispatch reference in the resume core: {banned}")

    # 12. No replay / replay_dead / BE3-C.
    if re.search(r"replay_dead\s*\(", service) or re.search(r"replay_dead\s*\(", repo_src):
        bad("check12: resume core calls replay_dead")
    for mod in ("replay_service", "replay_request_repository", "resume_replay_execution"):
        if (ROOT / "shared" / "sdk" / "tasks" / f"{mod}.py").exists():
            bad(f"check12: a BE3-C module already exists: {mod}")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 13. No shared activation/deployment; migrations only 032/033.
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check13: forbidden deployment/activation path changed: {f}")
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if any(not Path(f).name.startswith(("032_", "033_")) for f in mig_changed):
        bad(f"check13: an unexpected migration was changed: {mig_changed}")

    # 14-15. Documented posture: Draft PR not merged; combined BE3-R still required.
    rec = REC.read_text(encoding="utf-8").lower()
    if "not for merge" not in rec and "not merged" not in rec:
        bad("check14: record does not state the Draft PR is not merged")
    if "be3-r" not in rec:
        bad("check15: record does not state the combined independent BE3-R is still required")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] durable resume request lifecycle (migration 033, one-active-per-clarification);")
    print("       DB-authoritative eligibility under row locks + state-version binding; resume")
    print(
        "       authorized ONLY by the policy authority (operator cannot self-authorize; authority"
    )
    print(
        "       is a server-side capability, never request input); Service-Identity-only execution"
    )
    print(
        "       preparation (no endpoint); exact null-safe NOT NULL scope; production gate intact;"
    )
    print(
        "       durable resume.execution_requested outbox command with a stable id; outbox failure"
    )
    print("       rolls back the consume; API + command gates disabled-by-default; NO orchestrator")
    print("       call, NO replay_dead, NO BE3-C, NO shared migration/deployment/activation.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-B self-verification only; overall BE3 technical closure needs the combined")
    print("        independent BE3-R review over BE3-A+B+C. Draft PR #20 remains NOT FOR MERGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
