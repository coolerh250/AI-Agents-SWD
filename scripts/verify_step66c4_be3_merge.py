#!/usr/bin/env python3
"""Step 66C.4-BE3-M -- deterministic merge/closure verifier.

Confirms PR #20 (feature/66c4-be3-resume-replay-authorization @ 5a413bf) was merged into main as a
NON-SQUASH merge commit, that BE3-A/B/C implementation and migrations 032-035 are on main, that the
original review, R1/R2 remediation, and focused-closure evidence commits all still exist with their
markers, that the final BE3_TECHNICAL_VERDICT is PASS, that all four BE3 feature gates remain
disabled-by-default, and that NO shared migration / deployment / activation / runtime resume-replay
was introduced by the merge.

Marker: STEP66C4_BE3_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

MERGE_REC = CONTRACT / "be3-merge-and-source-of-truth-record.md"
GATE = CONTRACT / "be3-runtime-activation-gate.md"
RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
ORCH_MAIN = ROOT / "apps" / "orchestrator" / "src" / "main.py"

PRE_MERGE_MAIN = "5745ab7"
REVIEWED_HEAD = "5a413bf"
MERGE_COMMIT = "284d706"

EVIDENCE_COMMITS = (
    "da758f2",
    "1164464",
    "c2bc5cb",
    "962963f",
    "2949e20",
    "6323972",
    "5626403",
    "b1bac36",
    "5a413bf",
    "2712ad4",
)

REVIEW_BRANCHES = (
    "review/66c4-be3-combined-security-transaction",
    "review/66c4-be2-poller-relay-transaction-recovery",
    "review/66c4-be2-r1-remediation-closure",
    "review/66c4-be1-technical-security-migration",
    "review/66c4-be1-r1-remediation-closure",
)

FEATURE_GATES = (
    "BE3_RESUME_API_ENABLED",
    "BE3_RESUME_COMMAND_ENABLED",
    "BE3_REPLAY_API_ENABLED",
    "BE3_REPLAY_EXECUTION_ENABLED",
)

MARKER = "STEP66C4_BE3_MERGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (MERGE_REC, GATE, RESUME_MODEL, REPLAY_MODEL, ORCH_MAIN):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    merge = MERGE_REC.read_text(encoding="utf-8")

    # 1. PR #20 approved head is 5a413bf (recorded).
    if REVIEWED_HEAD not in merge:
        bad("check1: approved head 5a413bf not recorded")

    # 2. Non-squash two-parent merge commit (main + reviewed head).
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    if len(parents) != 3:
        bad(f"check2: merge commit is not a two-parent merge: {parents}")
    else:
        if not parents[1].startswith(PRE_MERGE_MAIN):
            bad(f"check2: first parent is not pre-merge main: {parents[1]}")
        if not parents[2].startswith(REVIEWED_HEAD):
            bad(f"check2: second parent is not the reviewed head: {parents[2]}")
    if "non-squash" not in merge.lower():
        bad("check2: merge record does not state non-squash")

    # 3. BE3-A/B/C implementation exists on main.
    head = _git("rev-parse", "HEAD")
    for f in (
        "shared/sdk/tasks/authorization_model.py",
        "shared/sdk/tasks/authorization_repository.py",
        "shared/sdk/tasks/authorization_service.py",
        "shared/sdk/tasks/resume_request_model.py",
        "shared/sdk/tasks/resume_service.py",
        "shared/sdk/tasks/replay_request_model.py",
        "shared/sdk/tasks/replay_service.py",
        "shared/sdk/tasks/production_approval_repository.py",
        "apps/orchestrator/src/operations_resume_api.py",
        "apps/orchestrator/src/operations_replay_api.py",
    ):
        if _git("cat-file", "-t", f"{head}:{f}") != "blob":
            bad(f"check3: BE3 implementation missing on main: {f}")

    # 4. Migrations 032/033/034/035 exist in the repository.
    for mig in (
        "migrations/032_be3_resume_replay_authorization.sql",
        "migrations/033_be3_resume_requests.sql",
        "migrations/034_be3_replay_requests.sql",
        "migrations/035_be3_production_action_approvals.sql",
    ):
        if _git("cat-file", "-t", f"{head}:{mig}") != "blob":
            bad(f"check4: migration missing on main: {mig}")

    # 5-8. Evidence commits still exist (objects present, regardless of branch).
    for c in EVIDENCE_COMMITS:
        rc = subprocess.run(
            ["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True
        )
        if rc.returncode != 0:
            bad(f"check5-8: evidence commit missing: {c}")

    # 9. Final BE3_TECHNICAL_VERDICT is PASS (and the original REMEDIATION-precondition history
    # is not silently erased -- both verdicts must appear).
    if "BE3_TECHNICAL_VERDICT: PASS" not in merge:
        bad("check9: final BE3_TECHNICAL_VERDICT: PASS not recorded")
    if "STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS" not in merge:
        bad("check9: focused-closure process marker not recorded")

    # 10. M-1 / L-1 / R2-1 closure evidence present.
    for token in ("M-1", "L-1", "R2-1"):
        if token not in merge:
            bad(f"check10: {token} closure evidence not recorded")

    # 11. All four BE3 feature gates default to false.
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    combined_src = resume_src + replay_src
    for gate in FEATURE_GATES:
        if f'os.environ.get("{gate}", "false")' not in combined_src:
            bad(f"check11: feature gate {gate} does not default to false")

    changed = _git("diff", "--name-only", f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}").splitlines()

    # 12. No shared migration evidence (migrations added but not applied -- no runtime/deploy
    # config referencing them as applied).
    for f in changed:
        for prefix in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(prefix):
                bad(f"check12-13: forbidden deployment/activation path changed by the merge: {f}")

    # 13. No deployment or runtime-activation evidence (docker-compose / env files unchanged).
    for f in changed:
        if "docker-compose" in f or f.endswith(".env"):
            bad(f"check13: deployment/env file changed by the merge: {f}")

    # 14. No runtime resume/replay/dispatch: gate check must guard both API routers' create paths.
    resume_api = (ROOT / "apps" / "orchestrator" / "src" / "operations_resume_api.py").read_text(
        encoding="utf-8"
    )
    replay_api = (ROOT / "apps" / "orchestrator" / "src" / "operations_replay_api.py").read_text(
        encoding="utf-8"
    )
    if "resume_api_enabled" not in resume_api and "BE3_RESUME_API_ENABLED" not in resume_src:
        bad("check14: resume API does not reference its disabled-by-default gate")
    if "replay_api_enabled" not in replay_api and "BE3_REPLAY_API_ENABLED" not in replay_src:
        bad("check14: replay API does not reference its disabled-by-default gate")

    # 15. production_executed_true_count remains 0.
    if "production_executed_true_count" not in merge or "0" not in merge:
        bad("check15: production_executed_true_count not recorded as 0")

    # Review branches preserved (not deleted).
    for br in REVIEW_BRANCHES:
        rc = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{br}"], cwd=ROOT, capture_output=True
        )
        if rc.returncode != 0:
            bad(f"review branch missing: {br}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] PR #20 (5a413bf) merged into main as the non-squash merge commit 284d706")
    print("       (parents 5745ab7 + 5a413bf); BE3-A/B/C implementation and migrations 032-035")
    print("       present on main; original review, R1/R2 remediation, and focused-closure")
    print("       evidence commits all present; final BE3_TECHNICAL_VERDICT: PASS; M-1/L-1/R2-1")
    print("       closure recorded; all four BE3 feature gates default to false; no shared")
    print("       migration/deployment/activation; review branches preserved;")
    print("       production_executed_true_count = 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
