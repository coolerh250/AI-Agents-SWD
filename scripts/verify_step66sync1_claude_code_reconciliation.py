#!/usr/bin/env python3
"""Step 66SYNC.1-A / A1 -- Claude Code reconciliation and context-taxonomy self-verifier.

Deterministic, offline checks over the reconciliation deliverables plus negative proof that this
read-only stage changed no runtime, frontend, migration, or deployment configuration. Reads only
committed repository content: it starts no container, opens no database connection, contacts no
external service, and reads no secret.

Step 66SYNC.1-A1 adds the synchronization-taxonomy checks: a canonical context mismatch (which
blocks partner synchronization) must be distinguished from an open Product Owner decision (which
does not), and D-1/D-2/D-3 must be classified as the latter without any of them being decided.

Markers: STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS | FAIL
         STEP66SYNC1_A1_CONTEXT_TAXONOMY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: this stage's rejection window ends where an authorized successor
# milestone takes over. Without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import successor_window_end  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def successor_window_end(_baseline: str = "") -> str:
        """Strictest fallback: with no lifecycle module the window stays HEAD-relative."""
        return "HEAD"

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

# Step 66D-ALIGN1-RM1 fixed stage boundary. This stage's scope is the frozen commit
# range below -- never "baseline -> current HEAD". Later authorized stages advance
# main; they cannot widen, narrow or drift what THIS stage is proven to have changed.
# The expected path set is the immutable manifest of that range. Both values are
# cross-checked against the RM1 stage-boundary manifest.
STAGE_BASELINE = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
STAGE_HEAD = "828ea900d53edab6f8441f50723e52955a1049e1"
EXPECTED_STAGE_PATHS = (
    "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md",
    "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
    "scripts/verify_step66sync1_claude_code_reconciliation.py",
    "source/progress.md",
    "tests/test_step66sync1_claude_code_reconciliation.py",
)

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

TAXONOMY_CATEGORIES = (
    "CANONICAL_CONTEXT_MISMATCH",
    "OPEN_PRODUCT_OWNER_DECISION",
    "TECHNICAL_GAP",
    "IMPLEMENTATION_GAP",
)
PO_DECISION_IDS = ("D-1", "D-2", "D-3")

MARKER = "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY"
TAXONOMY_MARKER = "STEP66SYNC1_A1_CONTEXT_TAXONOMY_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "c1db4ccbfd88fa775e4761c932835896b9b980ed"


def check_runtime_guard_current_state() -> None:
    """Reject runtime/frontend/infra paths introduced at any point after this stage's baseline."""
    changed = [
        line
        for line in _git(
            "diff", "--name-only", RUNTIME_GUARD_ANCHOR,
            successor_window_end(RUNTIME_GUARD_ANCHOR)
        ).splitlines()
        if line.strip()
    ]
    offenders = [
        path
        for path in changed
        if path.startswith(("apps/", "agents/", "services/", "shared/", "migrations/", "infra/"))
        or path.endswith((".tsx", ".jsx", ".vue", ".yaml", ".yml", ".sql"))
        or "docker-compose" in path
        or path.startswith(("helm/", "k8s/", "charts/"))
    ]
    if offenders:
        bad(
            f"runtime-guard: protected path present after this stage: {', '.join(sorted(offenders))}"
        )


def main() -> int:  # noqa: C901
    for p in (SNAPSHOT, ACK, REGISTER, MATRIX, EVIDENCE, RESUME_MODEL, REPLAY_MODEL):
        if not p.is_file():
            bad(f"missing required file: {p}")
    check_runtime_guard_current_state()

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
    changed = [
        f.strip()
        for f in _git("diff", "--name-only", STAGE_BASELINE, STAGE_HEAD).splitlines()
        if f.strip()
    ]
    for f in changed:
        if f.startswith(("apps/", "shared/", "agents/")):
            bad(f"check7: this stage changed runtime/frontend source: {f}")
        if f.startswith("migrations/"):
            bad(f"check8: this stage changed a migration: {f}")
        if f.startswith("infra/"):
            bad(f"check9: this stage changed deployment/infra configuration: {f}")

    # Step 66D-ALIGN1-RM1: exact-set comparison over the FIXED range. Nothing passes on the
    # strength of a directory or filename prefix; an unregistered path fails here.
    if tuple(sorted(changed)) != EXPECTED_STAGE_PATHS:
        unexpected = sorted(set(changed) - set(EXPECTED_STAGE_PATHS))
        missing = sorted(set(EXPECTED_STAGE_PATHS) - set(changed))
        if unexpected:
            bad(f"check10: unregistered path in this stage's fixed range: {', '.join(unexpected)}")
        if missing:
            bad(
                f"check10: registered path missing from this stage's fixed range: {', '.join(missing)}"
            )

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

    # 13. Step 66SYNC.1-A1 taxonomy: all four categories defined in the register.
    for cat in TAXONOMY_CATEGORIES:
        if cat not in register:
            bad(f"check13: discrepancy register missing taxonomy category: {cat}")

    # 14. UNRESOLVED_CANONICAL_MISMATCHES == 0 and CONTEXT_MATCH still holds.
    m = re.search(r"UNRESOLVED_CANONICAL_MISMATCHES:\s*(\d+)", register)
    if not m:
        bad("check14: register does not declare UNRESOLVED_CANONICAL_MISMATCHES")
    elif int(m.group(1)) != 0:
        bad(f"check14b: UNRESOLVED_CANONICAL_MISMATCHES is {m.group(1)}, expected 0")
    if "RESULT: CONTEXT_MATCH" not in register:
        bad("check14c: register does not record RESULT: CONTEXT_MATCH")
    if not re.search(r"RESULT:\s*CONTEXT_MATCH", ack):
        bad("check14d: acknowledgement does not record RESULT: CONTEXT_MATCH")

    # 15. OPEN_PRODUCT_OWNER_DECISIONS == 3, and D-1/D-2/D-3 are exactly those three.
    m = re.search(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*(\d+)", register)
    if not m:
        bad("check15: register does not declare OPEN_PRODUCT_OWNER_DECISIONS")
    elif int(m.group(1)) != 3:
        bad(f"check15b: OPEN_PRODUCT_OWNER_DECISIONS is {m.group(1)}, expected 3")
    required_marker = len(re.findall(r"Status: PRODUCT_OWNER_DECISION_REQUIRED", register))
    if required_marker != 3:
        bad(f"check15c: {required_marker} PRODUCT_OWNER_DECISION_REQUIRED markers, expected 3")

    # 16. Each of D-1/D-2/D-3 is classified correctly and decided by nobody.
    for did in PO_DECISION_IDS:
        if f"Decision ID:                {did}" not in register:
            bad(f"check16: {did} is not recorded as a Product Owner decision")
            continue
        block = register.split(f"Decision ID:                {did}", 1)[-1].split("### ", 1)[0]
        for field in (
            "Observed technical state:",
            "Decision required:",
            "Impact on Codex inventory:",
            "Impact on POC.0:",
        ):
            if field not in block:
                bad(f"check16b: {did} missing required field: {field}")
        if "Implementation authorized:  NO" not in block:
            bad(f"check16c: {did} does not record 'Implementation authorized: NO'")
        if "Status: PRODUCT_OWNER_DECISION_REQUIRED" not in block:
            bad(f"check16d: {did} is not PRODUCT_OWNER_DECISION_REQUIRED")
    if "None of D-1, D-2 or D-3 was decided" not in register:
        bad("check16e: register does not assert that no partner decided D-1/D-2/D-3")

    # 17. Partner continuation state and the Codex stop rule.
    for probe in (
        "CODEX_INVENTORY_MAY_PROCEED: YES",
        "CLAUDE_DESIGN_INVENTORY_MAY_PROCEED: YES",
        "POC_SCOPE_FINALIZATION: BLOCKED",
        "POC_IMPLEMENTATION: NOT AUTHORIZED",
    ):
        if probe not in register:
            bad(f"check17: register missing partner continuation state: {probe}")
        if probe not in ack:
            bad(f"check17b: acknowledgement missing partner continuation state: {probe}")
    if "MUST NOT STOP solely because" not in register:
        bad("check17c: register does not carry the Codex must-not-stop rule")
    if "DECISION_DEPENDENT" not in register:
        bad("check17d: register does not require DECISION_DEPENDENT marking")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        print(f"{TAXONOMY_MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Canonical main c1db4cc confirmed; RA-2 planning head efa396d confirmed; context")
    print("       snapshot, acknowledgement, discrepancy register and POC readiness matrix all")
    print("       present with explicit classifications; four BE3 feature gates remain default")
    print("       false; no runtime, frontend, agent, migration or infra file changed by this")
    print("       stage and every changed path is inside the allowed set; no secret-shaped or")
    print("       internal-identifier content in any deliverable; production_executed_true_count")
    print("       is 0.")
    print(f"{MARKER}: PASS")
    print("  [OK] Taxonomy: all four categories defined; UNRESOLVED_CANONICAL_MISMATCHES is 0 and")
    print("       RESULT is CONTEXT_MATCH; OPEN_PRODUCT_OWNER_DECISIONS is 3 with D-1/D-2/D-3 each")
    print("       carrying the required fields, 'Implementation authorized: NO' and")
    print("       PRODUCT_OWNER_DECISION_REQUIRED, and none decided by a partner; Codex and Claude")
    print("       Design inventory may proceed; POC scope finalization is BLOCKED and POC")
    print("       implementation is NOT AUTHORIZED.")
    print(f"{TAXONOMY_MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
