#!/usr/bin/env python3
"""Step 66SYNC.1-D -- final partner reconciliation and synchronization gate self-verifier.

Deterministic and offline. Verifies the three partner branch heads, that all three partners
recorded CONTEXT_MATCH with passing markers, that the synchronization taxonomy holds (0 canonical
mismatches, exactly 3 open Product Owner decisions), that the normalization outcomes were recorded,
and that this coordinator stage changed no runtime, frontend, backend, migration, or deployment
file. Starts no container, opens no database connection, reads no secret.

Marker: STEP66SYNC1_FINAL_PARTNER_RECONCILIATION_VERIFY: PASS | FAIL
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

STATE = ALIGNMENT / "partner-synchronized-program-state-20260803.md"
FINAL_ACK = SYNC / "step66sync1-final-partner-acknowledgement.md"
FINAL_REGISTER = SYNC / "step66sync1-final-context-discrepancy-register.md"
DECISION_PACKAGE = SYNC / "step66sync1-poc-scope-decision-package.md"
GAP_REGISTER = SYNC / "step66sync1-poc0-consolidated-gap-register.md"
EVIDENCE = ROOT / "docs" / "test" / "step66sync1-final-partner-reconciliation-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"

CANONICAL_MAIN = "c1db4cc"
RA2_PLANNING_HEAD = "efa396d"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

PARTNERS = {
    "claude_code": ("planning/66sync1-claude-code-state-reconciliation", "828ea90"),
    "codex": ("planning/66sync1-codex-frontend-reconciliation", "78aa4ee"),
    "claude_design": ("planning/66sync1-claude-design-ux-reconciliation", "65c93a1"),
}

PARTNER_ACKS = {
    "828ea90": "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "78aa4ee": "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "65c93a1": "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
}

PARTNER_MARKERS = {
    ("828ea90", "docs/test/step66sync1-claude-code-reconciliation-evidence.md"): (
        "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS",
        "STEP66SYNC1_A1_CONTEXT_TAXONOMY_VERIFY: PASS",
    ),
    ("78aa4ee", "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"): (
        "STEP66SYNC1_CODEX_FRONTEND_RECONCILIATION_VERIFY: PASS",
    ),
    ("65c93a1", "docs/test/step66sync1-claude-design-reconciliation-evidence.md"): (
        "STEP66SYNC1_CLAUDE_DESIGN_RECONCILIATION_VERIFY: PASS",
    ),
}

DESIGN_SPEC = "docs/design/ai-agent-team-functional-poc-control-center-spec.md"
CAPABILITY_CLASSES = (
    "READY",
    "READY_WITH_CONSTRAINTS",
    "PARTIAL",
    "DECISION_DEPENDENT",
    "GAP_REQUIRING_POC0",
    "NOT_IMPLEMENTED",
)
GAP_CATEGORIES = (
    "POC0-BACKEND",
    "POC0-FRONTEND",
    "POC0-UX",
    "POC0-ENVIRONMENT",
    "POC0-INTEGRATION",
    "POC0-SAFETY",
    "POC0-DELIVERY",
)
# Step 66D-ALIGN1-RM1 fixed stage boundary. This stage's scope is the frozen commit
# range below -- never "baseline -> current HEAD". Later authorized stages advance
# main; they cannot widen, narrow or drift what THIS stage is proven to have changed.
# The expected path set is the immutable manifest of that range. Both values are
# cross-checked against the RM1 stage-boundary manifest.
STAGE_BASELINE = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
STAGE_HEAD = "2396c6c7002387c886463bd38158b9ddc3bfb9e2"
EXPECTED_STAGE_PATHS = (
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md",
    "docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
    "docs/test/step66sync1-final-partner-reconciliation-evidence.md",
    "scripts/verify_step66sync1_final_partner_reconciliation.py",
    "source/progress.md",
    "tests/test_step66sync1_final_partner_reconciliation.py",
)

MARKER = "STEP66SYNC1_FINAL_PARTNER_RECONCILIATION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _show(ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True
    ).stdout


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
    for p in (STATE, FINAL_ACK, FINAL_REGISTER, DECISION_PACKAGE, GAP_REGISTER, EVIDENCE):
        if not p.is_file():
            bad(f"missing required artifact: {p}")
    check_runtime_guard_current_state()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    state = STATE.read_text(encoding="utf-8")
    ack = FINAL_ACK.read_text(encoding="utf-8")
    register = FINAL_REGISTER.read_text(encoding="utf-8")
    package = DECISION_PACKAGE.read_text(encoding="utf-8")
    gaps = GAP_REGISTER.read_text(encoding="utf-8")

    # 1. Three partner branch heads are correct.
    for name, (branch, expected) in PARTNERS.items():
        remote = _git("ls-remote", "origin", f"refs/heads/{branch}")
        if not remote:
            bad(f"check1: origin/{branch} not found")
        elif not remote.startswith(expected):
            bad(f"check1: {name} head mismatch -- expected {expected}, got {remote.split()[0][:7]}")

    # 2. All three partner acknowledgements record CONTEXT_MATCH.
    for ref, path in PARTNER_ACKS.items():
        text = _show(ref, path)
        if not text:
            bad(f"check2: could not read {path} at {ref}")
        elif not re.search(r"RESULT:\s*CONTEXT_MATCH", text):
            bad(f"check2: {path} at {ref} does not record RESULT: CONTEXT_MATCH")

    # 3. All three partner markers PASS in their committed evidence.
    for (ref, path), markers in PARTNER_MARKERS.items():
        text = _show(ref, path)
        if not text:
            bad(f"check3: could not read {path} at {ref}")
            continue
        for marker in markers:
            if marker not in text:
                bad(f"check3: marker missing in {path} at {ref}: {marker}")

    # 4. Canonical main is c1db4cc.
    if (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        != 0
    ):
        bad(f"check4: canonical main {CANONICAL_MAIN} is not an ancestor of HEAD")
    if CANONICAL_MAIN not in state or CANONICAL_MAIN not in ack:
        bad(f"check4b: {CANONICAL_MAIN} not recorded in the state doc and final acknowledgement")

    # 5. RA-2 planning head is efa396d.
    remote = _git(
        "ls-remote", "origin", "refs/heads/planning/66c4-be3-ra2-identity-secret-decision"
    )
    if remote and not remote.startswith(RA2_PLANNING_HEAD):
        bad(f"check5: RA-2 planning head is not {RA2_PLANNING_HEAD}: {remote.split()[0][:7]}")
    if RA2_PLANNING_HEAD not in state:
        bad(f"check5b: state doc does not record RA-2 planning head {RA2_PLANNING_HEAD}")

    # 6. Canonical mismatches are 0.
    for name, text in (("register", register), ("acknowledgement", ack)):
        m = re.search(r"UNRESOLVED_CANONICAL_MISMATCHES:\s*\n?(\d+)", text)
        if not m:
            bad(f"check6: {name} does not declare UNRESOLVED_CANONICAL_MISMATCHES")
        elif int(m.group(1)) != 0:
            bad(f"check6b: {name} declares {m.group(1)} canonical mismatches, expected 0")

    # 7. Open Product Owner decisions are exactly 3.
    for name, text in (("register", register), ("acknowledgement", ack)):
        m = re.search(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*\n?(\d+)", text)
        if not m:
            bad(f"check7: {name} does not declare OPEN_PRODUCT_OWNER_DECISIONS")
        elif int(m.group(1)) != 3:
            bad(f"check7b: {name} declares {m.group(1)} open PO decisions, expected 3")

    # 8. D-1/D-2/D-3 all present, decision-required, and unauthorized.
    for did in ("D-1", "D-2", "D-3"):
        if did not in package:
            bad(f"check8: {did} missing from the decision package")
            continue
        block = package.split(f"## {did} ", 1)[-1].split("\n---", 1)[0]
        if "PRODUCT_OWNER_DECISION_REQUIRED" not in block:
            bad(f"check8b: {did} is not PRODUCT_OWNER_DECISION_REQUIRED")
        if "IMPLEMENTATION_AUTHORIZED:  NO" not in block:
            bad(f"check8c: {did} does not record IMPLEMENTATION_AUTHORIZED: NO")
        if "Product Owner selection:  PENDING" not in block:
            bad(f"check8d: {did} selection is not PENDING")
    if "Decisions made by any partner:        0" not in package:
        bad("check8e: decision package does not assert zero partner decisions")

    # 9. Screen count re-verified.
    if "SUMMARY_COUNT_CORRECTED" not in state:
        bad("check9: screen-count reconciliation result not recorded")
    spec_text = _show("65c93a1", DESIGN_SPEC)
    actual = len(re.findall(r"^### 7\.\d+ ", spec_text, re.MULTILINE))
    if actual != 15:
        bad(f"check9b: design spec has {actual} screen sections, expected 15")
    if "Specification screen count: 15" not in state:
        bad("check9c: state doc does not record the re-derived specification screen count")

    # 10. 66D terminology canonicalized (not invented, not renamed).
    if "CANONICAL_IDENTIFIER_CONFIRMED" not in state:
        bad("check10: 66D terminology result not recorded")
    for ident in ("Step 66D-ARCH", "Step 66D-DESIGN"):
        if ident not in state:
            bad(f"check10b: canonical identifier not recorded: {ident}")

    # 11. IA options not escalated to a fourth PO decision.
    if "NOT SELECTED" not in state or "POC.0 DESIGN OPTION" not in state:
        bad("check11: IA options not classified as a non-binding POC.0 design option")
    if re.search(r"\bD-4\b\s*(POC|IA|Unified)", state):
        bad("check11b: an IA option appears to have been escalated to a fourth PO decision")

    # 12. Capability matrix integrated.
    for cls in CAPABILITY_CLASSES:
        if cls not in state:
            bad(f"check12: capability matrix missing classification: {cls}")
    if "Total                  23" not in state:
        bad("check12b: capability matrix total not recorded")

    # 13. POC.0 gaps consolidated across all seven categories.
    for cat in GAP_CATEGORIES:
        if cat not in gaps:
            bad(f"check13: consolidated gap register missing category: {cat}")
    if "Authorized: 0 of 23." not in gaps:
        bad("check13b: gap register does not record that zero gaps are authorized")

    # 14/15. No runtime/frontend/backend/migration/deployment change by this stage.
    changed = [f for f in _git("diff", "--name-only", STAGE_BASELINE, STAGE_HEAD).splitlines() if f]
    for f in changed:
        if f.startswith(("apps/", "shared/", "agents/", "migrations/", "infra/")):
            bad(f"check14: this stage changed a protected path: {f}")
    # Step 66D-ALIGN1-RM1: exact-set comparison over the FIXED range. Nothing passes on
    # the strength of a directory or filename prefix; an unregistered path fails here.
    _actual = tuple(sorted(changed))
    _unexpected = sorted(set(_actual) - set(EXPECTED_STAGE_PATHS))
    _missing = sorted(set(EXPECTED_STAGE_PATHS) - set(_actual))
    if _unexpected:
        bad(f"check15: unregistered path in this stage's fixed range: {', '.join(_unexpected)}")
    if _missing:
        bad(
            f"check15: registered path missing from this stage's fixed range: {', '.join(_missing)}"
        )

    # 16. Feature gates remain default false.
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check16: {var} default is not 'false' in {gate_file.name}")

    # 17. POC implementation still unauthorized; scope not finalized.
    for probe in ("POC_SCOPE_FINALIZED:\nNO", "POC_IMPLEMENTATION_STARTED:\nNO"):
        if probe not in ack:
            bad(f"check17: final acknowledgement missing: {probe.replace(chr(10), ' ')}")
    for probe in (
        "Step 67POC.0:            NOT AUTHORIZED",
        "RA-2M:                   NOT AUTHORIZED",
    ):
        if probe not in ack:
            bad(f"check17b: final acknowledgement missing authorization statement: {probe}")

    # 18. production_executed_true_count = 0.
    if not re.search(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n0", ack):
        bad("check18: final acknowledgement does not record production_executed_true_count 0")
    if "production_executed_true_count: 0" not in state:
        bad("check18b: state doc does not record production_executed_true_count: 0")

    # Context id + final result present.
    if CONTEXT_ID not in ack or CONTEXT_ID not in state:
        bad(f"check18c: CONTEXT_ID {CONTEXT_ID} missing from the final artifacts")
    if "STEP 66SYNC.1 FINAL RESULT:\nPASS" not in ack:
        bad("check18d: final acknowledgement does not record STEP 66SYNC.1 FINAL RESULT: PASS")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Three partner heads verified (828ea90 / 78aa4ee / 65c93a1); all three partner")
    print("       acknowledgements record CONTEXT_MATCH and all four partner markers PASS in their")
    print("       committed evidence; canonical main c1db4cc and RA-2 head efa396d confirmed;")
    print("       UNRESOLVED_CANONICAL_MISMATCHES 0 and OPEN_PRODUCT_OWNER_DECISIONS exactly 3;")
    print(
        "       D-1/D-2/D-3 all present, PRODUCT_OWNER_DECISION_REQUIRED, IMPLEMENTATION_AUTHORIZED"
    )
    print("       NO, selection PENDING, zero partner decisions; screen count re-derived as 15 and")
    print("       corrected; 66D confirmed as a canonical identifier; IA options remain a")
    print("       non-binding POC.0 design option; capability matrix (23) and POC.0 gap register")
    print("       (23 gaps, 7 categories, 0 authorized) consolidated; no runtime/frontend/backend/")
    print("       migration/deployment file changed; feature gates default false; POC scope not")
    print("       finalized and POC implementation not started; production count 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
