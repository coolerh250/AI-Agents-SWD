"""Step 66SYNC.1-A -- Claude Code technical state reconciliation tests.

Offline and deterministic. These tests start NO container, open NO database connection, contact NO
external service, and read NO secret -- doing any of those would be a scope violation of a
read-only reconciliation stage. Several tests deliberately RE-DERIVE the snapshot's central claims
from source rather than trusting the document.
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

SNAPSHOT = ALIGNMENT / "partner-context-snapshot-20260803.md"
ACK = SYNC / "step66sync1-claude-code-acknowledgement.md"
REGISTER = SYNC / "step66sync1-context-discrepancy-register.md"
MATRIX = SYNC / "step66sync1-poc-backend-readiness-matrix.md"
EVIDENCE = ROOT / "docs" / "test" / "step66sync1-claude-code-reconciliation-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
TASK_API = ROOT / "apps" / "orchestrator" / "src" / "task_api.py"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_step66sync1_claude_code_reconciliation.py"

CANONICAL_MAIN = "c1db4cc"
RA2_PLANNING_HEAD = "efa396d"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

ALLOWED_PREFIXES = (
    "docs/alignment/66-project-completion/master/",
    "docs/handoffs/program-sync/",
    "docs/test/",
    "scripts/verify_step66sync1_claude_code_reconciliation.py",
    "tests/test_step66sync1_claude_code_reconciliation.py",
    "source/progress.md",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def snapshot() -> str:
    return _read(SNAPSHOT)


@pytest.fixture(scope="module")
def ack() -> str:
    return _read(ACK)


@pytest.fixture(scope="module")
def register() -> str:
    return _read(REGISTER)


@pytest.fixture(scope="module")
def matrix() -> str:
    return _read(MATRIX)


# --- Deliverables ---------------------------------------------------------------


@pytest.mark.parametrize("path", [SNAPSHOT, ACK, REGISTER, MATRIX, EVIDENCE])
def test_required_deliverable_exists(path: Path) -> None:
    assert path.is_file(), f"missing required deliverable: {path}"


# --- Context verification -------------------------------------------------------


def test_canonical_main_is_ancestor_of_head() -> None:
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=ROOT,
        capture_output=True,
    ).returncode
    assert rc == 0, f"{CANONICAL_MAIN} is not an ancestor of HEAD"


def test_ra2_planning_head_commit_exists() -> None:
    rc = subprocess.run(
        ["git", "cat-file", "-e", f"{RA2_PLANNING_HEAD}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
    ).returncode
    assert rc == 0, f"RA-2 planning head {RA2_PLANNING_HEAD} does not exist"


def test_context_id_recorded(snapshot: str, ack: str) -> None:
    assert CONTEXT_ID in snapshot
    assert f"CONTEXT_ID: {CONTEXT_ID}" in ack


def test_acknowledgement_shape(ack: str) -> None:
    assert "PARTNER: CLAUDE_CODE" in ack
    assert re.search(r"RESULT:\s*CONTEXT_(MATCH|MISMATCH)", ack)
    assert re.search(r"Implementation started:\s*\nNO", ack)


@pytest.mark.parametrize(
    "precedence",
    [
        "Product Owner explicit binding decision",
        "canonical main source and committed evidence",
        "current approved planning branch",
        "independent review evidence",
        "partner acknowledgement",
        "historical conversation summary",
    ],
)
def test_source_of_truth_precedence_recorded(snapshot: str, precedence: str) -> None:
    assert precedence in snapshot


# --- Classification completeness ------------------------------------------------


@pytest.mark.parametrize(
    "classification",
    [
        "IMPLEMENTED_AND_TESTED",
        "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
        "TEST_ONLY",
        "SEEDED_EVIDENCE_ONLY",
        "PLANNED_NOT_IMPLEMENTED",
        "ABSENT",
    ],
)
def test_capability_classification_vocabulary(snapshot: str, classification: str) -> None:
    assert classification in snapshot


@pytest.mark.parametrize(
    "classification", ["READY", "READY_WITH_CONSTRAINTS", "GAP_REQUIRING_POC0", "BLOCKED"]
)
def test_matrix_classification_vocabulary(matrix: str, classification: str) -> None:
    assert classification in matrix


# --- Re-derivation of the snapshot's central claims ------------------------------


def test_task_api_does_not_dispatch_claim_is_true() -> None:
    """Re-derive discrepancy D-1 from source rather than trusting the snapshot."""
    src = _read(TASK_API)
    assert "dispatch_enabled" in src, "task_api no longer reports dispatch_enabled"
    assert '"dispatch_enabled": False' in src or "'dispatch_enabled': False" in src
    assert "stream.tasks" not in src, "task_api now publishes to stream.tasks -- snapshot D-1 stale"


def test_backend_and_frontend_agents_are_empty_claim_is_true() -> None:
    """Re-derive discrepancy D-2 from the filesystem."""
    for name in ("backend-agent", "frontend-agent"):
        d = ROOT / "agents" / name
        assert d.is_dir(), f"agents/{name} directory missing"
        py_files = [p for p in d.rglob("*.py") if "__pycache__" not in p.parts]
        assert py_files == [], f"agents/{name} now has implementation: {py_files}"


def test_zero_production_service_identity_call_sites() -> None:
    """Cross-check the RA-2 identity finding still holds at this baseline."""
    for folder in ("apps", "shared", "agents"):
        out = subprocess.run(
            ["git", "grep", "-n", "is_service_identity=True", "--", folder],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert out == "", f"unexpected production Service Identity construction in {folder}/"


def test_ten_implemented_agents_present() -> None:
    implemented = []
    for d in sorted((ROOT / "agents").iterdir()):
        if not d.is_dir():
            continue
        if [p for p in d.rglob("*.py") if "__pycache__" not in p.parts]:
            implemented.append(d.name)
    assert len(implemented) == 10, f"expected 10 implemented agents, found {implemented}"


# --- Safety / negative proof ----------------------------------------------------


@pytest.mark.parametrize(
    "var,path",
    [
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ],
)
def test_feature_gate_defaults_false(var: str, path: Path) -> None:
    assert f'os.environ.get("{var}", "false")' in _read(path)


def test_no_runtime_frontend_migration_or_infra_changed() -> None:
    changed = [f for f in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines() if f]
    offenders = [
        f for f in changed if f.startswith(("apps/", "shared/", "agents/", "migrations/", "infra/"))
    ]
    assert offenders == [], f"read-only stage changed protected paths: {offenders}"


def test_all_changed_files_are_in_the_allowed_set() -> None:
    changed = [f for f in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines() if f]
    offenders = [f for f in changed if not f.startswith(ALLOWED_PREFIXES)]
    assert offenders == [], f"files outside the allowed set: {offenders}"


@pytest.mark.parametrize("doc", [SNAPSHOT, ACK, REGISTER, MATRIX])
def test_no_secret_shaped_content(doc: Path) -> None:
    secret_shaped = re.compile(
        r"(BEGIN [A-Z ]*PRIVATE KEY)"
        r"|(password\s*[:=]\s*['\"][^'\"]{3,})"
        r"|(postgres(?:ql)?://[^\s`|]*:[^\s`@|]+@)",
        re.IGNORECASE,
    )
    hit = secret_shaped.search(_read(doc))
    assert hit is None, f"{doc.name} contains secret-shaped content"


@pytest.mark.parametrize("doc", [SNAPSHOT, ACK, REGISTER, MATRIX])
def test_no_internal_identifiers(doc: Path) -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    hit = forbidden.search(_read(doc))
    assert hit is None, f"{doc.name} leaks an internal identifier"


def test_production_executed_true_count_zero(ack: str) -> None:
    assert "production_executed_true_count:\n0" in ack
    assert "production_executed_true_count: 0" in _read(ROOT / "source" / "progress.md")


# --- Discrepancy register -------------------------------------------------------


def test_register_declares_open_count(register: str) -> None:
    assert re.search(r"OPEN_DISCREPANCIES:\s*\d+", register)


def test_register_open_count_is_self_consistent(register: str) -> None:
    declared = re.search(r"OPEN_DISCREPANCIES:\s*(\d+)", register)
    assert declared is not None
    n = int(declared.group(1))
    open_items = len(re.findall(r"Status:\s*OPEN", register))
    assert n == open_items, f"declared {n} open discrepancies but {open_items} are marked OPEN"


def test_register_does_not_self_close_po_decisions(register: str) -> None:
    """Discrepancies owned by the Product Owner must not be closed by Claude Code."""
    for did in ("D-1", "D-2", "D-3"):
        block = register.split(f"Discrepancy ID:     {did}", 1)[-1].split("###", 1)[0]
        assert "Status:             OPEN" in block, f"{did} must remain OPEN"
        assert "Product Owner" in block, f"{did} must record Product Owner ownership"


def test_verifier_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)], cwd=ROOT, capture_output=True, text=True
    )
    assert "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS" in result.stdout, (
        result.stdout + result.stderr
    )
    assert result.returncode == 0
