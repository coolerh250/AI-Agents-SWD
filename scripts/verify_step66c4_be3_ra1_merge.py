#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1M -- RA-1 migration-readiness-foundation merge self-verifier.

Confirms the controlled merge of Draft PR #21 into canonical main: merge-commit shape, ancestry,
review-evidence preservation, findings-closed recording, and the binding post-merge safety posture
(no shared apply, no deployment, no runtime activation, no RA-2 authorization). Live `git`/`gh`
checks only -- does not touch any shared database, deploy anything, or start any runtime service.

Marker: STEP66C4_BE3_RA1_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOT = (
    ROOT
    / "docs"
    / "contracts"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-ra1-merge-source-of-truth.md"
)
EVIDENCE = ROOT / "docs" / "test" / "step66c4-be3-ra1-merge-evidence.md"
RUNNER = ROOT / "shared" / "sdk" / "backup_dr" / "migration_runner.py"
RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
MIGRATIONS = ROOT / "migrations"

PRE_MERGE_MAIN = "18f11fe"
FEATURE_HEAD = "97e56d4"
REVIEW_HEAD = "1f3a66f"
MERGE_COMMIT = "48004e3"
EVIDENCE_COMMITS = ("352d546", "9cd841f", "800035b", "1f3a66f")
INTEGRATION_ONLY_COMMITS = ("19cff82", "07f839f", "7c6b830")

MARKER = "STEP66C4_BE3_RA1_MERGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _is_ancestor(commit: str, ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, ref], cwd=ROOT, capture_output=True
        ).returncode
        == 0
    )


def main() -> int:  # noqa: C901
    for p in (SOT, EVIDENCE, RUNNER, RESUME_MODEL, REPLAY_MODEL):
        if not p.is_file():
            bad(f"missing required file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    sot = SOT.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. PR #21 state is MERGED.
    gh = subprocess.run(
        ["gh", "pr", "view", "21", "--json", "state,mergeCommit,headRefOid"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    pr: dict[str, object] = {}
    if gh.returncode == 0:
        pr = json.loads(gh.stdout)
        if pr.get("state") != "MERGED":
            bad(f"check1: PR #21 state is {pr.get('state')!r}, not MERGED")
    else:
        bad("check1: could not query PR #21 via gh (gh CLI unavailable or auth missing)")

    merge_oid = ""
    mc = pr.get("mergeCommit")
    if isinstance(mc, dict):
        merge_oid = str(mc.get("oid", ""))
    if not merge_oid.startswith(MERGE_COMMIT):
        bad(f"check1b: PR #21 mergeCommit.oid {merge_oid!r} does not start with {MERGE_COMMIT}")

    # 2/3/4. Merge is a non-squash two-parent commit; parent 1 = pre-merge main, parent 2 = feature head.
    parents_raw = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT)
    parents = parents_raw.split()
    if len(parents) != 2:
        bad(f"check2: merge commit does not have exactly two parents: {parents}")
    else:
        if not parents[0].startswith(PRE_MERGE_MAIN):
            bad(f"check3: parent 1 {parents[0]!r} does not start with {PRE_MERGE_MAIN}")
        if not parents[1].startswith(FEATURE_HEAD):
            bad(f"check4: parent 2 {parents[1]!r} does not start with {FEATURE_HEAD}")

    # 5. Approved feature head is a main ancestor.
    if not _is_ancestor(FEATURE_HEAD, "origin/main"):
        bad(f"check5: {FEATURE_HEAD} is not an ancestor of origin/main")

    # 6. Review branch head is NOT a main ancestor.
    if _is_ancestor(REVIEW_HEAD, "origin/main"):
        bad(f"check6: review branch head {REVIEW_HEAD} IS an ancestor of origin/main")

    # Reviewer-only integration commits must also not be main ancestors.
    for c in INTEGRATION_ONLY_COMMITS:
        if _is_ancestor(c, "origin/main"):
            bad(f"check6b: reviewer-only integration commit {c} IS an ancestor of origin/main")

    # 7. Review evidence commits still exist.
    for c in EVIDENCE_COMMITS:
        rc = subprocess.run(
            ["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True
        ).returncode
        if rc != 0:
            bad(f"check7: evidence commit {c} does not exist")

    # 8. Final RA1_TECHNICAL_VERDICT recorded as PASS.
    if "RA1_TECHNICAL_VERDICT: PASS" not in sot:
        bad("check8: source-of-truth record does not record RA1_TECHNICAL_VERDICT: PASS")

    # 9. H-1/M-1/M-2A/M-2B/M-3A/M-3B all recorded CLOSED.
    for finding in ("H-1", "M-1", "M-2A", "M-2B", "M-3A", "M-3B"):
        if not re.search(rf"{re.escape(finding)}\s+CLOSED", sot):
            bad(f"check9: {finding} not recorded CLOSED in source-of-truth record")

    # 10. Migrations 031-035 exist in the repository but no shared-apply record.
    for v in ("031", "032", "033", "034", "035"):
        matches = list(MIGRATIONS.glob(f"{v}_*.sql"))
        if not matches:
            bad(f"check10: migration {v} not found under migrations/")
    if "NOT APPLIED" not in sot:
        bad("check10b: source-of-truth record does not state migrations are NOT APPLIED")

    # 11. Four BE3 feature gates remain default false.
    if 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' not in resume_src:
        bad("check11: BE3_RESUME_API_ENABLED default is not 'false' in resume_request_model.py")
    if 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' not in resume_src:
        bad("check11: BE3_RESUME_COMMAND_ENABLED default is not 'false' in resume_request_model.py")
    if 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' not in replay_src:
        bad("check11: BE3_REPLAY_API_ENABLED default is not 'false' in replay_request_model.py")
    if 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' not in replay_src:
        bad(
            "check11: BE3_REPLAY_EXECUTION_ENABLED default is not 'false' in replay_request_model.py"
        )

    # 12. No deployment or runtime activation recorded.
    if "NOT DEPLOYED" not in sot or "NOT ACTIVATED" not in sot:
        bad("check12: source-of-truth record does not state NOT DEPLOYED / NOT ACTIVATED")

    # 13. No poller/relay/worker/consumer started.
    if "none started" not in sot.lower() and "none started" not in evidence.lower():
        bad("check13: no record of 'none started' for worker/relay/consumer")

    # 14. No runtime resume/replay/dispatch executed.
    if "none executed" not in sot.lower():
        bad("check14: no record of 'none executed' for resume/replay/dispatch")

    # 15. Gates 1/2/6 remain PENDING RUNTIME/SHARED EXECUTION.
    for gate in ("Gate 1", "Gate 2", "Gate 6"):
        if f"{gate} -- PENDING RUNTIME/SHARED EXECUTION" not in sot:
            bad(f"check15: {gate} not recorded PENDING RUNTIME/SHARED EXECUTION")

    # 16. RA-2 still not authorized.
    if "RA-2: NOT AUTHORIZED" not in sot:
        bad("check16: RA-2 not recorded NOT AUTHORIZED")

    # 17. PR #21 source-of-truth status is merged.
    if "PR #21" not in sot or "MERGED" not in sot:
        bad("check17: source-of-truth record does not record PR #21 as MERGED")

    # 18. production_executed_true_count=0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check18: production_executed_true_count: 0 not recorded in source/progress.md")
    if (
        "production_executed_true_count:      0" not in sot
        and "production_executed_true_count: 0" not in sot
    ):
        bad("check18b: production_executed_true_count: 0 not recorded in source-of-truth record")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] PR #21 MERGED via a two-parent, non-squash merge commit with the exact required")
    print("       parent order; approved feature head is a main ancestor; review branch and its")
    print("       reviewer-only integration commits are NOT main ancestors; all review evidence")
    print("       commits still exist; H-1/M-1/M-2A/M-2B/M-3A/M-3B recorded CLOSED with a final")
    print("       RA1_TECHNICAL_VERDICT: PASS; migrations 031-035 present but not shared-applied;")
    print("       all four feature gates remain default false; no deployment/runtime activation;")
    print(
        "       Gates 1/2/6 remain PENDING RUNTIME/SHARED EXECUTION; RA-2 remains NOT AUTHORIZED;"
    )
    print("       production_executed_true_count is 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
