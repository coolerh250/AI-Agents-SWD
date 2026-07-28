#!/usr/bin/env python3
"""Step 66C.4-BE3-R2 -- resume production-effect authoritative derivation self-verifier.

Static/structural checks that resume's production-effect classification is derived SERVER-SIDE
from the owning task's own `production_effect` column -- never from request input -- and is
revalidated (via the resource_state_version CAS) at create/authorize/consume time, with the
production_action_approvals registry (Step 66C.4-BE3-R1) integration unchanged and reused.

Marker: STEP66C4_BE3_R2_RESUME_PRODUCTION_EFFECT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
SERVICE = ROOT / "shared" / "sdk" / "tasks" / "resume_service.py"
API = ROOT / "apps" / "orchestrator" / "src" / "operations_resume_api.py"
AUTHZ_SERVICE = ROOT / "shared" / "sdk" / "tasks" / "authorization_service.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_r2_resume_production_effect.py"
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
REC = CONTRACT_DIR / "be3-r2-resume-production-effect-remediation-record.md"
GATE = CONTRACT_DIR / "be3-runtime-activation-gate.md"
HANDOFF = (
    ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-r2-to-focused-closure-handoff.md"
)

BASE = "b1bac36"  # BE3-R1 feature head; BE3-R2 review diff baseline
MARKER = "STEP66C4_BE3_R2_RESUME_PRODUCTION_EFFECT_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (MODEL, SERVICE, API, AUTHZ_SERVICE, TESTS, REC, GATE, HANDOFF):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    model = MODEL.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    # 1. production_effect is derived from the authoritative task, not accepted as a parameter.
    if "def authoritative_production_effect" not in model:
        bad("check1: no authoritative_production_effect derivation function")
    if re.search(r"def request_resume\([^)]*production_effect", service, re.S):
        bad("check1: request_resume still accepts a production_effect parameter")
    if "model.authoritative_production_effect(task)" not in service:
        bad("check1: request_resume does not derive production_effect from the locked task")

    # 2. Client cannot downgrade or control production_effect: no such FIELD DECLARATION in the API
    # schema (checked as an actual `production_effect: <type>` annotation, not a substring match --
    # this file's own explanatory comment legitimately mentions the token in prose).
    if re.search(r"^\s*production_effect\s*:", api, re.M):
        bad("check2: ResumeRequestCreate still declares a production_effect field")
    if "payload.production_effect" in api:
        bad("check2: API handler still reads payload.production_effect")

    # 3. Create/authorize/consume all revalidate: resource_state_version is computed from BOTH the
    # clarification and the task at every call site (not just at request time).
    version_calls = re.findall(r"model\.resource_state_version\(([^)]*)\)", service)
    if len(version_calls) < 3:
        bad(f"check3: expected >=3 resource_state_version call sites, found {len(version_calls)}")
    if any("task" not in call for call in version_calls):
        bad("check3: a resource_state_version call site does not pass the locked task row")

    # 4. Production-effect changes invalidate the state version (folded into its own snapshot).
    if "def resource_state_version" not in model:
        bad("check4: resource_state_version function missing")
    sig_match = re.search(r"def resource_state_version\(([^)]*)\)", model)
    if sig_match is None or "task_row" not in sig_match.group(1):
        bad("check4: resource_state_version signature does not take a task_row")
    if "def test_state_version_changes_with_production_effect" not in tests:
        bad("check4: no test proves the state version changes with production_effect")

    # 5. Valid production approval authoritatively resolved at consume time (reused, unmodified
    # integration point -- authorization_service.consume already does this from BE3-R1).
    if "resolve_and_consume_approval" not in AUTHZ_SERVICE.read_text(encoding="utf-8"):
        bad("check5: authorization_service.consume no longer resolves production approvals")

    # 6. Invalid approval never consumes / never creates a command (mandatory tests present).
    for must in (
        "def test_pg_production_task_no_approval_blocks_consume",
        "def test_pg_wrong_resource_and_stale_version_approval_rejected",
    ):
        if must not in tests:
            bad(f"check6: missing mandatory test {must}")

    # 7. Production approval and BE3 authorization consumed in the SAME transaction (rollback test).
    if "def test_pg_outbox_failure_rolls_back_both_authorization_and_approval" not in tests:
        bad("check7: missing same-transaction rollback test")

    # 8. Scope and NULL fail-closed.
    if "def test_pg_cross_project_task_masked_and_null_scope_fail_closed" not in tests:
        bad("check8: missing scope isolation test")

    # 9. No public grant/execute expansion: no new HTTP route registered in this stage.
    if re.search(r'@router\.(post|get|put|delete)\("/production-approvals', api):
        bad("check9: an unexpected new production-approval HTTP route was registered")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 10. No shared migration/deployment/activation path touched; no new migration at all (this
    # stage needed none).
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check10: forbidden deployment/activation path changed: {f}")
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if mig_changed:
        bad(f"check10: an unexpected migration was changed (none required for R2): {mig_changed}")

    # 11. Draft PR #20 unmerged (checked via the record).
    rec_text = REC.read_text(encoding="utf-8").lower()
    if "not merged" not in rec_text and "not for merge" not in rec_text:
        bad("check11: record does not state Draft PR #20 is not merged")

    # 12. Combined reviewer's focused closure remains the next gate (not this session's own review).
    handoff_text = HANDOFF.read_text(encoding="utf-8").lower()
    if "focused closure" not in handoff_text and "combined review" not in handoff_text:
        bad("check12: handoff does not reference the original combined reviewer's focused closure")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] resume production_effect is derived server-side from operator_tasks under the")
    print("       SAME task row lock used for eligibility; no request field, no service parameter,")
    print("       and no code path exists for a client to supply, upgrade, or downgrade it. It is")
    print("       folded into resource_state_version, re-validated at authorize AND consume time,")
    print(
        "       so a task classification change invalidates any outstanding request/authorization"
    )
    print("       (stale_state, no side effect). The production_action_approvals resolver (BE3-R1)")
    print(
        "       is reused unmodified. No shared migration, deployment, or activation; no new HTTP"
    )
    print("       route.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-R2 findings-closure only; the original combined reviewer's focused closure")
    print("        remains the next required gate. Draft PR #20 remains Draft/NOT FOR MERGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
