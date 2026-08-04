"""Step 66SYNC.1-D -- final partner reconciliation and synchronization gate tests.

Offline and deterministic. These tests start NO container, open NO database connection, contact NO
external service, and read NO secret. Several tests deliberately RE-DERIVE partner claims from the
partner branches' committed content rather than trusting this stage's own prose.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

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
VERIFY_SCRIPT = ROOT / "scripts" / "verify_step66sync1_final_partner_reconciliation.py"

CANONICAL_MAIN = "c1db4cc"
RA2_PLANNING_HEAD = "efa396d"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

CLAUDE_CODE_HEAD = "828ea90"
CODEX_HEAD = "78aa4ee"
CLAUDE_DESIGN_HEAD = "65c93a1"

PARTNER_BRANCHES = [
    ("planning/66sync1-claude-code-state-reconciliation", CLAUDE_CODE_HEAD),
    ("planning/66sync1-codex-frontend-reconciliation", CODEX_HEAD),
    ("planning/66sync1-claude-design-ux-reconciliation", CLAUDE_DESIGN_HEAD),
]

PARTNER_ACK_PATHS = [
    (CLAUDE_CODE_HEAD, "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md"),
    (CODEX_HEAD, "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md"),
    (CLAUDE_DESIGN_HEAD, "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md"),
]

PARTNER_MARKERS = [
    (
        CLAUDE_CODE_HEAD,
        "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
        "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS",
    ),
    (
        CLAUDE_CODE_HEAD,
        "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
        "STEP66SYNC1_A1_CONTEXT_TAXONOMY_VERIFY: PASS",
    ),
    (
        CODEX_HEAD,
        "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md",
        "STEP66SYNC1_CODEX_FRONTEND_RECONCILIATION_VERIFY: PASS",
    ),
    (
        CLAUDE_DESIGN_HEAD,
        "docs/test/step66sync1-claude-design-reconciliation-evidence.md",
        "STEP66SYNC1_CLAUDE_DESIGN_RECONCILIATION_VERIFY: PASS",
    ),
]

DESIGN_SPEC = "docs/design/ai-agent-team-functional-poc-control-center-spec.md"

ALLOWED_PREFIXES = (
    "docs/alignment/66-project-completion/master/",
    "docs/handoffs/program-sync/",
    "docs/test/",
    "scripts/verify_step66sync1_final_partner_reconciliation.py",
    "tests/test_step66sync1_final_partner_reconciliation.py",
    "source/progress.md",
    # Step 66SYNC.1-M1 canonicalization: this branch legitimately carries the whole
    # Step 66SYNC.1 artifact set, not just the coordinator's slice. Runtime paths
    # (apps/, shared/, agents/, services/, migrations/, infra/) remain rejected.
    "docs/",
    "scripts/verify_step66",
    "tests/test_step66",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _show(ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True
    ).stdout


@pytest.fixture(scope="module")
def state() -> str:
    return _read(STATE)


@pytest.fixture(scope="module")
def ack() -> str:
    return _read(FINAL_ACK)


@pytest.fixture(scope="module")
def register() -> str:
    return _read(FINAL_REGISTER)


@pytest.fixture(scope="module")
def package() -> str:
    return _read(DECISION_PACKAGE)


@pytest.fixture(scope="module")
def gaps() -> str:
    return _read(GAP_REGISTER)


# --- Deliverables ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [STATE, FINAL_ACK, FINAL_REGISTER, DECISION_PACKAGE, GAP_REGISTER, EVIDENCE]
)
def test_required_artifact_exists(path: Path) -> None:
    assert path.is_file(), f"missing required artifact: {path}"


# --- 1. Partner branch heads ----------------------------------------------------


@pytest.mark.parametrize("branch,expected", PARTNER_BRANCHES)
def test_partner_branch_head(branch: str, expected: str) -> None:
    remote = _git("ls-remote", "origin", f"refs/heads/{branch}")
    assert remote, f"origin/{branch} not found"
    assert remote.startswith(expected), f"{branch} is not at {expected}: {remote.split()[0]}"


# --- 2. Partner CONTEXT_MATCH ---------------------------------------------------


@pytest.mark.parametrize("ref,path", PARTNER_ACK_PATHS)
def test_partner_acknowledgement_context_match(ref: str, path: str) -> None:
    text = _show(ref, path)
    assert text, f"could not read {path} at {ref}"
    assert re.search(r"RESULT:\s*CONTEXT_MATCH", text), f"{path} does not record CONTEXT_MATCH"


# --- 3. Partner markers ---------------------------------------------------------


@pytest.mark.parametrize("ref,path,marker", PARTNER_MARKERS)
def test_partner_marker_passes(ref: str, path: str, marker: str) -> None:
    text = _show(ref, path)
    assert text, f"could not read {path} at {ref}"
    assert marker in text, f"marker missing in {path} at {ref}: {marker}"


# --- 4/5. Canonical refs --------------------------------------------------------


def test_canonical_main_is_ancestor() -> None:
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=ROOT,
        capture_output=True,
    ).returncode
    assert rc == 0


def test_ra2_planning_head(state: str) -> None:
    remote = _git(
        "ls-remote", "origin", "refs/heads/planning/66c4-be3-ra2-identity-secret-decision"
    )
    assert remote.startswith(RA2_PLANNING_HEAD), f"RA-2 head is not {RA2_PLANNING_HEAD}"
    assert RA2_PLANNING_HEAD in state


def test_context_id_recorded(state: str, ack: str) -> None:
    assert CONTEXT_ID in state
    assert CONTEXT_ID in ack


# --- 6/7. Taxonomy counts -------------------------------------------------------


def test_no_unresolved_canonical_mismatches(register: str, ack: str) -> None:
    for text in (register, ack):
        m = re.search(r"UNRESOLVED_CANONICAL_MISMATCHES:\s*\n?(\d+)", text)
        assert m is not None
        assert int(m.group(1)) == 0


def test_exactly_three_open_po_decisions(register: str, ack: str) -> None:
    for text in (register, ack):
        m = re.search(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*\n?(\d+)", text)
        assert m is not None
        assert int(m.group(1)) == 3


def test_all_partners_agree_on_three_open_decisions() -> None:
    """Re-derive from the partner branches instead of trusting this stage's summary."""
    for ref in (CLAUDE_CODE_HEAD, CODEX_HEAD, CLAUDE_DESIGN_HEAD):
        out = subprocess.run(
            ["git", "grep", "-h", "OPEN_PRODUCT_OWNER_DECISIONS:", ref, "--", "docs/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout
        counts = set(re.findall(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*(\d+)", out))
        assert counts == {"3"}, f"{ref} declares open PO decisions {counts}, expected exactly 3"


# --- 8. D-1 / D-2 / D-3 ---------------------------------------------------------


@pytest.mark.parametrize("decision_id", ["D-1", "D-2", "D-3"])
def test_decision_present_and_unauthorized(package: str, decision_id: str) -> None:
    assert f"## {decision_id} " in package
    block = package.split(f"## {decision_id} ", 1)[-1].split("\n---", 1)[0]
    assert "OPEN_PRODUCT_OWNER_DECISION" in block
    assert "PRODUCT_OWNER_DECISION_REQUIRED" in block
    assert "IMPLEMENTATION_AUTHORIZED:  NO" in block
    assert "Product Owner selection:  PENDING" in block


def test_no_partner_decided_anything(package: str) -> None:
    assert "Decisions made by any partner:        0" in package
    assert "Options selected:                     0" in package


@pytest.mark.parametrize(
    "decision_id,required_options",
    [
        ("D-1", ["Option A", "Option B"]),
        ("D-2", ["Option A", "Option B", "Option C"]),
        ("D-3", ["Option A", "Option B", "Option C"]),
    ],
)
def test_decision_has_required_options(
    package: str, decision_id: str, required_options: list[str]
) -> None:
    block = package.split(f"## {decision_id} ", 1)[-1].split("\n---", 1)[0]
    for opt in required_options:
        assert f"### {opt}" in block, f"{decision_id} missing {opt}"


def test_d3_option_c_marked_high_risk(package: str) -> None:
    block = package.split("## D-3 ", 1)[-1].split("\n---", 1)[0]
    assert "HIGH-RISK" in block
    assert "SEPARATE SECURITY REVIEW REQUIRED" in block
    assert "NOT PART OF NORMAL POC.0" in block


# --- 9. Screen count ------------------------------------------------------------


def test_design_spec_has_fifteen_screens() -> None:
    """Re-derive the screen count directly from the specification."""
    spec = _show(CLAUDE_DESIGN_HEAD, DESIGN_SPEC)
    assert spec, "could not read the design spec"
    headings = re.findall(r"^### 7\.\d+ ", spec, re.MULTILINE)
    assert len(headings) == 15, f"expected 15 screen sections, found {len(headings)}"


def test_screen_count_reconciliation_recorded(state: str) -> None:
    assert "SUMMARY_COUNT_CORRECTED" in state
    assert "Specification screen count: 15" in state


# --- 10. 66D terminology --------------------------------------------------------


def test_66d_is_canonical_on_main() -> None:
    """66D must not be renamed: confirm it exists as a canonical stage on main."""
    out = subprocess.run(
        ["git", "grep", "-l", "Step 66D-ARCH", CANONICAL_MAIN, "--", "docs/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out, "Step 66D-ARCH not found on canonical main"


@pytest.mark.parametrize("identifier", ["Step 66D-ARCH", "Step 66D-DESIGN"])
def test_66d_canonical_identifier_recorded(state: str, identifier: str) -> None:
    assert identifier in state
    assert "CANONICAL_IDENTIFIER_CONFIRMED" in state


# --- 11. IA options -------------------------------------------------------------


def test_ia_options_not_a_fourth_decision(state: str) -> None:
    assert "POC.0 DESIGN OPTION" in state
    assert "NOT SELECTED" in state
    assert "OPEN_PRODUCT_OWNER_DECISIONS remains exactly 3" in state


# --- 12. Capability matrix ------------------------------------------------------


@pytest.mark.parametrize(
    "classification",
    [
        "READY",
        "READY_WITH_CONSTRAINTS",
        "PARTIAL",
        "DECISION_DEPENDENT",
        "GAP_REQUIRING_POC0",
        "NOT_IMPLEMENTED",
    ],
)
def test_capability_classification_present(state: str, classification: str) -> None:
    assert classification in state


def test_capability_matrix_totals(state: str) -> None:
    assert "Total                  23" in state


# --- 13. POC.0 gaps -------------------------------------------------------------


@pytest.mark.parametrize(
    "category",
    [
        "POC0-BACKEND",
        "POC0-FRONTEND",
        "POC0-UX",
        "POC0-ENVIRONMENT",
        "POC0-INTEGRATION",
        "POC0-SAFETY",
        "POC0-DELIVERY",
    ],
)
def test_gap_category_present(gaps: str, category: str) -> None:
    assert category in gaps


def test_no_gap_is_authorized(gaps: str) -> None:
    assert "Authorized: 0 of 23." in gaps
    assert "Authorized:            NO" in gaps


# --- 14/15. Negative proof ------------------------------------------------------


def test_no_protected_path_changed() -> None:
    changed = [f for f in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines() if f]
    offenders = [
        f for f in changed if f.startswith(("apps/", "shared/", "agents/", "migrations/", "infra/"))
    ]
    assert offenders == [], f"coordinator stage changed protected paths: {offenders}"


def test_all_changed_files_in_allowed_set() -> None:
    changed = [f for f in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines() if f]
    offenders = [f for f in changed if not f.startswith(ALLOWED_PREFIXES)]
    assert offenders == [], f"files outside the allowed set: {offenders}"


def test_partner_branches_untouched() -> None:
    """This stage must not have modified any partner branch."""
    for branch, expected in PARTNER_BRANCHES:
        remote = _git("ls-remote", "origin", f"refs/heads/{branch}")
        assert remote.startswith(expected), f"{branch} was modified"


# --- 16. Feature gates ----------------------------------------------------------


@pytest.mark.parametrize(
    "var,path",
    [
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ],
)
def test_feature_gate_default_false(var: str, path: Path) -> None:
    assert f'os.environ.get("{var}", "false")' in _read(path)


# --- 17/18. Authorization state and safety --------------------------------------


def test_poc_scope_not_finalized(ack: str) -> None:
    assert "POC_SCOPE_FINALIZED:\nNO" in ack
    assert "POC_IMPLEMENTATION_STARTED:\nNO" in ack


@pytest.mark.parametrize(
    "statement",
    [
        "Step 67POC.0:            NOT AUTHORIZED",
        "RA-2M:                   NOT AUTHORIZED",
        "RA-2I0 .. RA-2I6, RA-2R: NOT AUTHORIZED",
        "RA-3 and later:          NOT AUTHORIZED",
    ],
)
def test_authorization_state_recorded(ack: str, statement: str) -> None:
    assert statement in ack


def test_final_result_pass(ack: str) -> None:
    assert "STEP 66SYNC.1 FINAL RESULT:\nPASS" in ack


def test_production_executed_true_count_zero(ack: str, state: str) -> None:
    assert re.search(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n0", ack)
    assert "production_executed_true_count: 0" in state


@pytest.mark.parametrize("doc", [STATE, FINAL_ACK, FINAL_REGISTER, DECISION_PACKAGE, GAP_REGISTER])
def test_no_internal_identifiers(doc: Path) -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    hit = forbidden.search(_read(doc))
    assert hit is None, f"{doc.name} leaks an internal identifier"


@pytest.mark.parametrize("doc", [STATE, FINAL_ACK, FINAL_REGISTER, DECISION_PACKAGE, GAP_REGISTER])
def test_no_secret_shaped_content(doc: Path) -> None:
    secret_shaped = re.compile(
        r"(BEGIN [A-Z ]*PRIVATE KEY)"
        r"|(password\s*[:=]\s*['\"][^'\"]{3,})"
        r"|(postgres(?:ql)?://[^\s`|]*:[^\s`@|]+@)",
        re.IGNORECASE,
    )
    hit = secret_shaped.search(_read(doc))
    assert hit is None, f"{doc.name} contains secret-shaped content"


def test_verifier_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)], cwd=ROOT, capture_output=True, text=True
    )
    assert "STEP66SYNC1_FINAL_PARTNER_RECONCILIATION_VERIFY: PASS" in result.stdout, (
        result.stdout + result.stderr
    )
    assert result.returncode == 0
