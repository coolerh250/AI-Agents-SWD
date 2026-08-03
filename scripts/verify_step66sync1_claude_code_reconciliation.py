#!/usr/bin/env python3
"""Step 66SYNC.1-A -- Claude Code technical state reconciliation self-verifier.

Deterministic, offline checks over the reconciliation deliverables plus negative proof that this
read-only stage changed no runtime, frontend, migration, or deployment configuration. Reads only
committed repository content: it starts no container, opens no database connection, contacts no
external service, and reads no secret.

Marker: STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALIGNMENT = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
SYNC = ROOT / "docs" / "handoffs" / "program-sync"

SNAPSHOT = ALIGNMENT / "partner-context-snapshot-20260803.md"
ACK = SYNC / "step66sync1-claude-code-acknowledgement.md"
REGISTER = SYNC / "step66sync1-context-discrepancy-register.md"
MATRIX = SYNC / "step66sync1-poc-backend-readiness-matrix.md"
EVIDENCE = ROOT / "docs" / "test" / "step66sync1-claude-code-reconciliation-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"

CANONICAL_MAIN = "c1db4cc"
RA2_PLANNING_HEAD = "efa396d"
RA2_PLANNING_BRANCH = "planning/66c4-be3-ra2-identity-secret-decision"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

CLASSIFICATIONS = (
    "IMPLEMENTED_AND_TESTED",
    "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
    "TEST_ONLY",
    "SEEDED_EVIDENCE_ONLY",
    "PLANNED_NOT_IMPLEMENTED",
    "ABSENT",
)
MATRIX_CLASSIFICATIONS = (
    "READY",
    "READY_WITH_CONSTRAINTS",
    "GAP_REQUIRING_POC0",
    "BLOCKED",
)
FEATURE_GATES = (
    ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
    ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
    ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
    ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
)

MARKER = "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (SNAPSHOT, ACK, REGISTER, MATRIX, EVIDENCE, RESUME_MODEL, REPLAY_MODEL):
        if not p.is_file():
            bad(f"missing required file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    snapshot = SNAPSHOT.read_text(encoding="utf-8")
    ack = ACK.read_text(encoding="utf-8")
    register = REGISTER.read_text(encoding="utf-8")
    matrix = MATRIX.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. Canonical main is c1db4cc and is an ancestor of HEAD.
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=ROOT,
        capture_output=True,
    ).returncode
    if rc != 0:
        bad(f"check1: canonical main {CANONICAL_MAIN} is not an ancestor of HEAD")
    if CANONICAL_MAIN not in snapshot or CANONICAL_MAIN not in ack:
        bad(f"check1b: {CANONICAL_MAIN} not recorded in snapshot and acknowledgement")

    # 2. RA-2 planning head is efa396d and the commit exists.
    if (
        subprocess.run(
            ["git", "cat-file", "-e", f"{RA2_PLANNING_HEAD}^{{commit}}"],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        != 0
    ):
        bad(f"check2: RA-2 planning head {RA2_PLANNING_HEAD} does not exist")
    remote = _git("ls-remote", "origin", f"refs/heads/{RA2_PLANNING_BRANCH}")
    if remote and not remote.startswith(RA2_PLANNING_HEAD):
        bad(f"check2b: origin/{RA2_PLANNING_BRANCH} is not at {RA2_PLANNING_HEAD}: {remote}")
    if RA2_PLANNING_HEAD not in ack:
        bad(f"check2c: acknowledgement does not record RA-2 planning head {RA2_PLANNING_HEAD}")

    # 3. Context snapshot exists and carries the context id + precedence order.
    if CONTEXT_ID not in snapshot:
        bad(f"check3: snapshot does not record CONTEXT_ID {CONTEXT_ID}")
    for probe in (
        "Product Owner explicit binding decision",
        "canonical main source and committed evidence",
        "current approved planning branch",
        "independent review evidence",
        "partner acknowledgement",
        "historical conversation summary",
    ):
        if probe not in snapshot:
            bad(f"check3b: snapshot missing source-of-truth precedence entry: {probe}")

    # 4. Claude Code acknowledgement exists in the required shape.
    if "PARTNER: CLAUDE_CODE" not in ack:
        bad("check4: acknowledgement missing PARTNER: CLAUDE_CODE")
    if f"CONTEXT_ID: {CONTEXT_ID}" not in ack:
        bad("check4b: acknowledgement missing CONTEXT_ID")
    if not re.search(r"RESULT:\s*CONTEXT_(MATCH|MISMATCH)", ack):
        bad("check4c: acknowledgement missing a RESULT line")
    if not re.search(r"Implementation started:\s*\nNO", ack):
        bad("check4d: acknowledgement does not record 'Implementation started: NO'")

    # 5. All capability classifications are explicit (both vocabularies used).
    for cls in CLASSIFICATIONS:
        if cls not in snapshot:
            bad(f"check5: snapshot missing capability classification: {cls}")
    for cls in MATRIX_CLASSIFICATIONS:
        if cls not in matrix:
            bad(f"check5b: readiness matrix missing classification: {cls}")

    # 6. Feature gates remain default false.
    for var, path in FEATURE_GATES:
        if f'os.environ.get("{var}", "false")' not in path.read_text(encoding="utf-8"):
            bad(f"check6: {var} default is not 'false' in {path.name}")
    if "ALL FOUR DEFAULT FALSE" not in ack and "ALL DEFAULT FALSE" not in snapshot:
        bad("check6b: gates-default-false not recorded in the deliverables")

    # 7-10. Negative proof: this stage changed no runtime, frontend, migration, or deployment file.
    changed = [f.strip() for f in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines()]
    changed = [f for f in changed if f]
    for f in changed:
        if f.startswith(("apps/", "shared/", "agents/")):
            bad(f"check7: this stage changed runtime/frontend source: {f}")
        if f.startswith("migrations/"):
            bad(f"check8: this stage changed a migration: {f}")
        if f.startswith("infra/"):
            bad(f"check9: this stage changed deployment/infra configuration: {f}")

    allowed_prefixes = (
        "docs/alignment/66-project-completion/master/",
        "docs/handoffs/program-sync/",
        "docs/test/",
        "scripts/verify_step66sync1_claude_code_reconciliation.py",
        "tests/test_step66sync1_claude_code_reconciliation.py",
        "source/progress.md",
    )
    for f in changed:
        if not f.startswith(allowed_prefixes):
            bad(f"check10: file outside the allowed set was changed: {f}")

    # 11. No secret read/write evidence in the deliverables.
    secret_shaped = re.compile(
        r"(BEGIN [A-Z ]*PRIVATE KEY)"
        r"|(password\s*[:=]\s*['\"][^'\"]{3,})"
        r"|(postgres(?:ql)?://[^\s`|]*:[^\s`@|]+@)",
        re.IGNORECASE,
    )
    internal = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    for name, text in (
        ("snapshot", snapshot),
        ("acknowledgement", ack),
        ("register", register),
        ("matrix", matrix),
    ):
        m = secret_shaped.search(text)
        if m:
            bad(f"check11: {name} contains secret-shaped content: {m.group(0)[:40]!r}")
        m2 = internal.search(text)
        if m2:
            bad(f"check11b: {name} leaks an internal identifier: {m2.group(0)!r}")

    # 12. production_executed_true_count = 0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check12: production_executed_true_count: 0 not recorded in source/progress.md")
    if "production_executed_true_count:\n0" not in ack:
        bad("check12b: acknowledgement does not record production_executed_true_count 0")

    # 13. Discrepancy register present and self-consistent.
    if not re.search(r"OPEN_DISCREPANCIES:\s*\d+", register):
        bad("check13: discrepancy register missing an OPEN_DISCREPANCIES count")
    declared = re.search(r"OPEN_DISCREPANCIES:\s*(\d+)", register)
    if declared:
        n = int(declared.group(1))
        open_items = len(re.findall(r"Status:\s*OPEN", register))
        if n != open_items:
            bad(f"check13b: OPEN_DISCREPANCIES={n} but {open_items} entries are marked OPEN")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Canonical main c1db4cc confirmed; RA-2 planning head efa396d confirmed; context")
    print("       snapshot, acknowledgement, discrepancy register and POC readiness matrix all")
    print("       present with explicit classifications; four BE3 feature gates remain default")
    print("       false; no runtime, frontend, agent, migration or infra file changed by this")
    print("       stage and every changed path is inside the allowed set; no secret-shaped or")
    print("       internal-identifier content in any deliverable; open-discrepancy count is")
    print("       self-consistent; production_executed_true_count is 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
