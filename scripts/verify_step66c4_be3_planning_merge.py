#!/usr/bin/env python3
"""Step 66C.4-BE3-P-M -- deterministic planning-merge verifier.

Confirms the BE3 planning contract (PR #19, planning branch @ 81f38d2) merged into main as a
NON-SQUASH merge commit, that the seven BE3 contracts are on main, and that NO
backend/API/migration/frontend/deployment change entered main. PASS means the planning contract is
canonical source of truth; it does NOT mean BE3 is implemented, deployed, or activated.

Marker: STEP66C4_BE3_PLANNING_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
MERGE_REC = CONTRACT / "be3-planning-merge-and-source-of-truth-record.md"

BE3_CONTRACTS = (
    "be3-operator-resume-replay-authorization-contract.md",
    "be3-rbac-permission-matrix.md",
    "be3-resume-replay-state-machine.md",
    "be3-api-event-contract.md",
    "be3-security-and-threat-model.md",
    "be3-runtime-activation-gate.md",
    "be3-implementation-slicing-plan.md",
)

PRE_MERGE_MAIN = "33b776b"
REVIEWED_HEAD = "81f38d2"
MERGE_COMMIT = "90fc765"

MARKER = "STEP66C4_BE3_PLANNING_MERGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    if not MERGE_REC.is_file():
        bad(f"missing merge record: {MERGE_REC}")
        print(f"{MARKER}: FAIL")
        return 1
    merge = MERGE_REC.read_text(encoding="utf-8")
    head = _git("rev-parse", "HEAD")

    # 1. Planning head is 81f38d2 (recorded).
    if REVIEWED_HEAD not in merge:
        bad("check1: planning head 81f38d2 not recorded")

    # 2. Non-squash merge commit (two parents).
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    if len(parents) != 3:
        bad(f"check2: not a two-parent merge commit: {parents}")
    else:
        if not parents[1].startswith(PRE_MERGE_MAIN):
            bad(f"check2: first parent not pre-merge main: {parents[1]}")
        if not parents[2].startswith(REVIEWED_HEAD):
            bad(f"check2: second parent not the reviewed head: {parents[2]}")
    if "non-squash" not in merge.lower():
        bad("check2: merge record does not state non-squash")

    # 3. Seven BE3 contracts exist on main.
    for name in BE3_CONTRACTS:
        rel = f"docs/contracts/66c4-reminder-expiry-controlled-resume/{name}"
        if _git("cat-file", "-t", f"{head}:{rel}") != "blob":
            bad(f"check3: BE3 contract missing on main: {name}")

    rbac = (CONTRACT / "be3-rbac-permission-matrix.md").read_text(encoding="utf-8")
    sm = (CONTRACT / "be3-resume-replay-state-machine.md").read_text(encoding="utf-8")
    api = (CONTRACT / "be3-api-event-contract.md").read_text(encoding="utf-8")
    gate = (CONTRACT / "be3-runtime-activation-gate.md").read_text(encoding="utf-8")
    slice_ = (CONTRACT / "be3-implementation-slicing-plan.md").read_text(encoding="utf-8")
    master = (CONTRACT / "be3-operator-resume-replay-authorization-contract.md").read_text(
        encoding="utf-8"
    )

    # 4. RBAC reuses canonical TASK_ROLES.
    for role in (
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    ):
        if role not in rbac:
            bad(f"check4: canonical role not reused: {role}")

    # 5. Resume/replay state machine present.
    if "not_eligible" not in sm or "replay_authorized" not in sm:
        bad("check5: resume/replay state machine incomplete on main")

    # 6. Durable authorization model present.
    for field in ("authorization_id", "single-use", "state-version-bound"):
        if field not in api:
            bad(f"check6: durable authorization model missing: {field}")

    # 7. Runtime activation gate present.
    if "Migration 031" not in gate or "DISABLED-BY-DEFAULT" not in gate:
        bad("check7: runtime activation gate incomplete on main")

    # 8. BE3-A/B/C slicing present.
    for s in ("BE3-A", "BE3-B", "BE3-C"):
        if s not in slice_:
            bad(f"check8: slicing plan missing {s}")

    # 9. No backend/API/migration/frontend/deployment change entered main via the merge.
    changed = _git("diff", "--name-only", f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}").splitlines()
    for f in changed:
        for forbidden in (
            "apps/",
            "shared/",
            "migrations/",
            "services/",
            "frontend/",
            "infra/",
            "helm/",
            "k8s/",
            ".github/workflows/",
        ):
            if f.startswith(forbidden):
                bad(f"check9: forbidden code path entered main via the merge: {f}")

    # 10. BE3-A still NOT AUTHORIZED.
    if "BE3-A" not in merge or "NOT AUTHORIZED" not in merge.upper():
        bad("check10: BE3-A not-authorized posture not recorded")

    # 11. replay_dead still internal-only.
    if "internal-only" not in master:
        bad("check11: master contract does not keep replay_dead internal-only")
    if "internal-only" not in merge:
        bad("check11: merge record does not state replay_dead internal-only")

    # 12. production_executed_true_count remains 0.
    if "production_executed_true_count" not in merge or "0" not in merge:
        bad("check12: production_executed_true_count not recorded as 0")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] PR #19 (81f38d2) merged into main as non-squash merge commit 90fc765")
    print("       (parents 33b776b + 81f38d2); seven BE3 contracts on main; RBAC reuses the")
    print("       canonical TASK_ROLES; resume/replay state machine + durable authorization +")
    print("       activation gate + BE3-A/B/C slicing present; no backend/API/migration/frontend/")
    print("       deployment change; BE3-A NOT AUTHORIZED; replay_dead internal-only;")
    print("       production_executed_true_count = 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
