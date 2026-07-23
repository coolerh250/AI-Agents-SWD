#!/usr/bin/env python3
"""Step 66C.4-BE1-M -- merge and technical-closure verifier.

Confirms the BE1 foundation was merged to main as a non-squash merge commit with full review
traceability, that the technical-closure evolution is recorded without conflating review process
markers and technical verdicts, and that nothing was deployed, migrated on a shared DB, or
activated (scheduler/relay/producer/dispatch/resume). Static/structural + git checks only.

Marker: STEP66C4_BE1_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
DECISIONS = (
    ROOT / "docs" / "decisions" / "66c4-reminder-expiry-controlled-resume-product-decisions.md"
)

MERGE_REC = CONTRACT_DIR / "be1-merge-record.md"
CLOSURE_REC = CONTRACT_DIR / "be1-technical-closure-record.md"
SOT_REC = CONTRACT_DIR / "be1-source-of-truth-record.md"
SOT_CANON = CONTRACT_DIR / "contract-source-of-truth-record.md"
DEFERRED = CONTRACT_DIR / "be1-deferred-low-findings.md"
TEST_REC = ROOT / "docs" / "test" / "step66c4-be1-merge-record.md"
STORE = ROOT / "shared" / "sdk" / "tasks" / "workroom_store.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
MIG_UP = ROOT / "migrations" / "031_clarification_lifecycle_outbox_foundation.sql"
PROGRESS = ROOT / "source" / "progress.md"
NEXT_SEQ = (
    ROOT
    / "docs"
    / "alignment"
    / "66-project-completion"
    / "master"
    / "next-executable-stage-sequence.md"
)
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be1-merge"

REVIEWED_HEAD = "0bb9944"
PRE_MERGE_MAIN = "e03c22d"
MERGE_COMMIT = "8080141"
ORIG_BE1 = "d2467f5"
ORIG_REVIEW = "f5417f4"
CLOSURE_REVIEW = "2e1c369"

MARKER = "STEP66C4_BE1_MERGE_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:
    docs = [
        MERGE_REC,
        CLOSURE_REC,
        SOT_REC,
        DEFERRED,
        TEST_REC,
        STAGE_DIR / "stage-manifest.yaml",
        STAGE_DIR / "context-receipt.md",
        STAGE_DIR / "stage-gate-report.md",
    ]
    for p in docs + [STORE, OUTBOX, MIG_UP, PROGRESS, NEXT_SEQ, DECISIONS, SOT_CANON]:
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    merge = MERGE_REC.read_text(encoding="utf-8")
    closure = CLOSURE_REC.read_text(encoding="utf-8")
    sot = SOT_REC.read_text(encoding="utf-8")
    store = STORE.read_text(encoding="utf-8")
    outbox = OUTBOX.read_text(encoding="utf-8")
    up = MIG_UP.read_text(encoding="utf-8")
    progress = PROGRESS.read_text(encoding="utf-8")
    nextseq = NEXT_SEQ.read_text(encoding="utf-8")

    # 1-2. Reviewed head + non-squash merge commit recorded.
    for token in (REVIEWED_HEAD, PRE_MERGE_MAIN, MERGE_COMMIT):
        if token not in merge:
            bad(f"check1/2: merge record does not record commit {token}")
    if "non-squash" not in merge.lower():
        bad("check2: non-squash merge not recorded")

    # 3. BE1 implementation exists on main (this working tree is main post-merge).
    head = _git("rev-parse", "HEAD")
    for f in (
        "migrations/031_clarification_lifecycle_outbox_foundation.sql",
        "shared/sdk/tasks/lifecycle_outbox.py",
    ):
        if not _git("cat-file", "-t", f"{head}:{f}"):
            bad(f"check3: BE1 file not present on main: {f}")

    # 3b. The merge commit is a real two-parent merge of pre-merge main + reviewed head.
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    if len(parents) != 3:
        bad(f"check3b: {MERGE_COMMIT} is not a two-parent merge commit (parents={parents})")
    else:
        if not parents[1].startswith(PRE_MERGE_MAIN) or not parents[2].startswith(REVIEWED_HEAD):
            bad(f"check3b: merge parents are not {PRE_MERGE_MAIN}+{REVIEWED_HEAD}: {parents[1:]}")

    # 4-5. Original review + closure review commits recorded.
    for token in (ORIG_BE1, ORIG_REVIEW, CLOSURE_REVIEW):
        if token not in merge or token not in closure:
            bad(f"check4/5: evidence commit not recorded: {token}")

    # 6-7. Both verdicts preserved and kept separate.
    if "BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED" not in closure:
        bad("check6: original REMEDIATION_REQUIRED verdict not preserved")
    if "BE1_TECHNICAL_VERDICT: PASS" not in closure:
        bad("check7: final PASS verdict not preserved")
    if "STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS" not in merge:
        bad("check6/7: review process marker not recorded separately")

    # 8. Contract + six PO decisions unchanged by the merge stage vs the pre-record merged tree.
    # (The decisions file must be identical to its state at the merge commit.)
    if _git(
        "diff",
        "--name-only",
        MERGE_COMMIT,
        "--",
        "docs/decisions/66c4-reminder-expiry-controlled-resume-product-decisions.md",
    ):
        bad("check8: PO decisions changed after the merge commit")

    # 9. Runtime Compatibility Gate still present, and the source-of-truth record states the
    # not-deployed runtime status.
    if "Runtime Compatibility Gate" not in SOT_CANON.read_text(encoding="utf-8"):
        bad("check9: BE1 Runtime Compatibility Gate missing from canonical source-of-truth record")
    if "NOT DEPLOYED" not in sot or "NOT RUNTIME VALIDATED" not in sot:
        bad("check9: source-of-truth record does not state NOT DEPLOYED / NOT RUNTIME VALIDATED")

    # 10. Deadline uses statement_timestamp().
    if "due_at > statement_timestamp()" not in store or "due_at > now()" in store:
        bad("check10: deadline predicate on main is not statement_timestamp()")

    # 11. Migration durability fields.
    for col in ("available_at", "dead_at", "last_error"):
        if col not in up:
            bad(f"check11: migration 031 missing durability field {col}")

    # 12. Positive allowlist exists.
    if "ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE" not in outbox or "PROHIBITED_PAYLOAD_KEYS" in outbox:
        bad("check12: positive payload allowlist not in effect")

    # 13-15. No live producer / scheduler / relay / resume-dispatch added anywhere runtime.
    offenders = []
    for base in (ROOT / "apps", ROOT / "shared"):
        for path in base.rglob("*.py"):
            if path == OUTBOX or "__pycache__" in str(path):
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in txt or "clarification_lifecycle_outbox" in txt:
                offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        bad(f"check13: live runtime references to the outbox: {offenders}")
    for banned in ("while True", "asyncio.sleep", "create_task(", "XREADGROUP", "FOR UPDATE"):
        if banned in outbox:
            bad(f"check14: outbox module contains a relay/scheduler construct: {banned}")

    # 16-17. No deployment change and no shared migration execution recorded.
    if _git(
        "diff",
        "--name-only",
        f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}",
        "--",
        "infra",
        "helm",
        "k8s",
        ".github/workflows",
    ):
        bad("check16: merge changed a deployment path")
    if "Shared database migration 031 executed:       NO" not in merge:
        bad("check17: merge record does not state migration 031 was not executed on a shared DB")

    # 18-19. Status lines.
    if "MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED" not in progress:
        bad("check18: progress.md does not mark BE1 MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED")
    low = progress.lower()
    if "be2" not in low or "not authorized" not in low:
        bad("check19: progress.md does not mark BE2 NOT AUTHORIZED")
    if "not authorized" not in nextseq.lower():
        bad("check19: next-executable-stage-sequence does not mark BE2 unauthorized")

    # 20. Evidence branches preserved (exist on origin).
    for br in (
        "review/66c4-be1-technical-security-migration",
        "review/66c4-be1-r1-remediation-closure",
    ):
        if not _git("rev-parse", "--verify", f"origin/{br}"):
            bad(f"check20: review evidence branch missing: {br}")

    # 21. production_executed_true_count remains 0 (recorded).
    if (
        "production_executed_true_count: 0" not in merge.replace("\n", " ")
        and "production_executed_true_count:               0" not in merge
    ):
        bad("check21: production_executed_true_count 0 not recorded")

    # 22. progress.md references the merge stage.
    if "66c.4-be1-m" not in low:
        bad("check22: progress.md does not reference Stage 66C.4-BE1-M")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] PR #17 (head 0bb9944) merged to main as a non-squash two-parent merge commit")
    print(
        "       8080141; BE1 implementation on main; original REMEDIATION_REQUIRED and final PASS"
    )
    print(
        "       verdicts both preserved and kept separate from review process markers; contract +"
    )
    print(
        "       PO decisions + Runtime Compatibility Gate intact; statement_timestamp() deadline;"
    )
    print(
        "       durability fields present; positive allowlist; no live producer/scheduler/relay; no"
    )
    print(
        "       deployment or shared migration; BE1 MERGED/NOT DEPLOYED/NOT RUNTIME VALIDATED; BE2"
    )
    print("       NOT AUTHORIZED; review evidence branches preserved; production count 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
