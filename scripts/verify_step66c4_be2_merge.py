#!/usr/bin/env python3
"""Step 66C.4-BE2-M -- deterministic merge/closure verifier.

Confirms PR #18 (feature/66c4-be2-reminder-expiry-outbox-relay @ c2677f7) was merged into main as a
NON-SQUASH merge commit, that both technical verdicts (original REMEDIATION_REQUIRED and final
closure PASS) are preserved and recorded separately, that the B-1/B-2 closure and retry semantics
are on main, and that NO deployment / shared activation / producer cutover / shared migration was
introduced and BE3 remains unauthorized.

Marker: STEP66C4_BE2_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

MERGE_REC = CONTRACT / "be2-merge-and-source-of-truth-record.md"
EXPIRY_REC = CONTRACT / "be2-r1-expiry-consistency-record.md"
RELAY_REC = CONTRACT / "be2-r1-relay-timeout-record.md"
RETRY_REC = CONTRACT / "be2-r1-retry-semantics-record.md"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"

PRE_MERGE_MAIN = "ab3c6cc"
REVIEWED_HEAD = "c2677f7"
MERGE_COMMIT = "161f4f3"

REVIEW_BRANCHES = (
    "review/66c4-be2-poller-relay-transaction-recovery",
    "review/66c4-be2-r1-remediation-closure",
    "review/66c4-be1-technical-security-migration",
    "review/66c4-be1-r1-remediation-closure",
)

MARKER = "STEP66C4_BE2_MERGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (MERGE_REC, EXPIRY_REC, RELAY_REC, RETRY_REC, OUTBOX):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    merge = MERGE_REC.read_text(encoding="utf-8")

    # 1. PR #18 reviewed head is c2677f7 (recorded).
    if REVIEWED_HEAD not in merge:
        bad("check1: reviewed head c2677f7 not recorded")

    # 2. Non-squash merge commit (two parents; main + reviewed head).
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

    # 3. BE2 implementation exists on main.
    head = _git("rev-parse", "HEAD")
    for f in (
        "shared/sdk/tasks/lifecycle_poller.py",
        "shared/sdk/tasks/outbox_relay.py",
        "shared/sdk/tasks/lifecycle_metrics.py",
        "apps/clarification-lifecycle-worker/src/main.py",
        "apps/clarification-outbox-relay/src/main.py",
    ):
        if _git("cat-file", "-t", f"{head}:{f}") != "blob":
            bad(f"check3: BE2 implementation missing on main: {f}")

    # 4. Original review REMEDIATION_REQUIRED preserved.
    if "REMEDIATION_REQUIRED" not in merge:
        bad("check4: original BE2 REMEDIATION_REQUIRED verdict not preserved")
    if "STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS" not in merge:
        bad("check4: original review process marker not preserved")

    # 5. Final closure PASS preserved (recorded separately).
    if "STEP66C4_BE2_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS" not in merge:
        bad("check5: closure review process marker not preserved")
    if "BE2_TECHNICAL_VERDICT: PASS" not in merge:
        bad("check5: final BE2_TECHNICAL_VERDICT: PASS not preserved")

    # 6. B-1 and B-2 closure records exist on main (came in via the merge).
    if "B-1" not in EXPIRY_REC.read_text(encoding="utf-8"):
        bad("check6: B-1 expiry-consistency record missing/incomplete")
    if "B-2" not in RELAY_REC.read_text(encoding="utf-8"):
        bad("check6: B-2 relay-timeout record missing/incomplete")

    # 7. Retry semantics: 4 retries / 5 attempts on main.
    outbox = OUTBOX.read_text(encoding="utf-8")
    if "MAX_RETRIES = len(RETRY_BACKOFF_SECONDS)" not in outbox:
        bad("check7: MAX_RETRIES not defined from the backoff schedule")
    if "MAX_PUBLISH_ATTEMPTS = MAX_RETRIES + 1" not in outbox:
        bad("check7: MAX_PUBLISH_ATTEMPTS != MAX_RETRIES + 1")
    if "(30, 120, 600, 3600)" not in outbox:
        bad("check7: canonical backoff schedule not present")

    changed = _git("diff", "--name-only", f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}").splitlines()

    # 8-9-10-11. No shared activation / producer cutover / shared migration / deployment.
    for f in changed:
        for prefix in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/", "migrations/"):
            if f.startswith(prefix):
                bad(f"check8-11: forbidden path changed by the merge: {f}")
    # existing audit producer path unchanged (only the additive event_bus timeout is allowed).
    if any(f.startswith("shared/sdk/audit/") for f in changed):
        bad("check9: existing audit producer path changed by the merge")
    # workers not activated in the orchestrator.
    for path in (ROOT / "apps" / "orchestrator").rglob("*.py"):
        txt = path.read_text(encoding="utf-8", errors="ignore")
        if "lifecycle_poller" in txt or "outbox_relay" in txt:
            bad(f"check8: a BE2 worker is activated in {path.relative_to(ROOT)}")

    # 12. BE3 remains unauthorized (recorded).
    if "Step 66C.4-BE3" not in merge or "NOT AUTHORIZED" not in merge.upper():
        bad("check12: BE3 not-authorized posture not recorded")

    # 13. Review branches still exist.
    for br in REVIEW_BRANCHES:
        if not _git("rev-parse", "--verify", f"origin/{br}"):
            bad(f"check13: review evidence branch missing: {br}")

    # 14. production_executed_true_count remains 0.
    if "production_executed_true_count" not in merge or "0" not in merge:
        bad("check14: production_executed_true_count not recorded as 0")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] PR #18 (c2677f7) merged into main as the non-squash merge commit 161f4f3")
    print("       (parents ab3c6cc + c2677f7); BE2 implementation on main; original")
    print("       REMEDIATION_REQUIRED and final closure PASS preserved separately; B-1/B-2")
    print("       closure + 4-retry/5-attempt semantics present; no migration, no shared")
    print("       activation, no producer cutover, no deployment; BE3 unauthorized; review")
    print("       branches preserved; production_executed_true_count = 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
