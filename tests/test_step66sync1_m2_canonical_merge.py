"""Tests for Step 66SYNC.1-M2 canonical merge.

Offline by design: no container, no database, no network, no secret access. The merge facts are
re-derived from Git objects rather than read out of the merge record.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: the rejection window ends where an authorized successor milestone
# takes over; without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from successor_lifecycle import successor_window_end  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66sync1_m2_canonical_merge.py"

SYNC = REPO / "docs" / "handoffs" / "program-sync"
MASTER = REPO / "docs" / "alignment" / "66-project-completion" / "master"
DESIGN_SPEC = REPO / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"

BINDING = SYNC / "step66sync1-poc-scope-binding-decisions.md"
ADDENDUM = MASTER / "partner-synchronized-program-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MERGE_RECORD = SYNC / "step66sync1-m2-canonical-merge-record.md"

PRE_MERGE_MAIN = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
PR_HEAD = "1278b8944e3a8f824a9b35f82382fa8587e7989d"
MERGE_COMMIT = "7971ae0c5a5d90a186efd4c52f75988720ce214e"
# This stage's own post-merge record commit. The bounded-adaptation guard below
# measures what THIS stage changed, not what later authorized stages changed.
RECORD_COMMIT = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"

HISTORICAL_EVIDENCE = (
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _is_ancestor(commit: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, descendant],
            cwd=REPO,
            check=False,
        ).returncode
        == 0
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- verifier -----------------------------------------------------------------------------


def test_verifier_script_exists() -> None:
    assert SCRIPT.is_file()


def test_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP66SYNC1_M2_CANONICAL_MERGE_VERIFY: PASS" in result.stdout


# --- merge shape, re-derived from Git ------------------------------------------------------


def test_merge_commit_exists() -> None:
    assert _git("cat-file", "-t", MERGE_COMMIT) == "commit"


def test_merge_commit_has_exactly_two_parents() -> None:
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert len(parents) == 3, "expected a two-parent (non-squash) merge commit"


def test_first_parent_is_pre_merge_main() -> None:
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert parents[1] == PRE_MERGE_MAIN


def test_second_parent_is_pr_head() -> None:
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert parents[2] == PR_HEAD


def test_merge_commit_is_in_main_history() -> None:
    assert _is_ancestor(MERGE_COMMIT, "HEAD")


def test_canonicalization_commit_retained_in_history() -> None:
    assert _is_ancestor(PR_HEAD, "HEAD")
    assert _git("cat-file", "-t", PR_HEAD) == "commit"


def test_pre_merge_main_retained_in_history() -> None:
    assert _is_ancestor(PRE_MERGE_MAIN, "HEAD")


def test_merge_was_not_squashed() -> None:
    """A squash merge would leave a single-parent commit and drop 1278b89 from history."""
    parents = _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert len(parents) == 3
    assert _is_ancestor(PR_HEAD, "HEAD")


def test_merge_commit_references_the_pull_request() -> None:
    subject = _git("show", "--no-patch", "--format=%s", MERGE_COMMIT)
    assert "#22" in subject


def test_canonicalization_commit_is_a_single_commit_above_pre_merge_main() -> None:
    assert _git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{PR_HEAD}") == "1"


# --- artifacts on main ---------------------------------------------------------------------


def test_all_step66sync1_artifacts_present_on_main() -> None:
    for rel in (
        "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
        "docs/alignment/66-project-completion/master/"
        "partner-synchronized-program-state-20260803.md",
        "docs/alignment/66-project-completion/master/"
        "partner-synchronized-program-state-20260804.md",
        "docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md",
        "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
        "docs/handoffs/program-sync/step66sync1-canonicalization-manifest.md",
        "docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md",
        "docs/test/step66sync1-m1-canonicalization-evidence.md",
    ):
        assert _git("cat-file", "-t", f"HEAD:{rel}") == "blob", rel


def test_all_five_partner_verifiers_present_on_main() -> None:
    for name in (
        "claude_code_reconciliation",
        "codex_frontend_reconciliation",
        "claude_design_reconciliation",
        "final_partner_reconciliation",
        "m1_canonicalization",
    ):
        assert _git("cat-file", "-t", f"HEAD:scripts/verify_step66sync1_{name}.py") == "blob", name
        assert _git("cat-file", "-t", f"HEAD:tests/test_step66sync1_{name}.py") == "blob", name


# --- binding decisions on main ---------------------------------------------------------------


def test_d1_resolved_binding_on_main() -> None:
    binding = _read(BINDING)
    assert re.search(r"^D-1:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE)
    assert "Selected:     Dedicated POC Development Goal" in binding


def test_d2_resolved_binding_on_main() -> None:
    binding = _read(BINDING)
    assert re.search(r"^D-2:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE)
    assert "Selected:     Hybrid execution model" in binding


def test_d3_resolved_binding_on_main() -> None:
    binding = _read(BINDING)
    assert re.search(r"^D-3:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE)
    assert "Selected:     Runtime LLM remains plan-only" in binding


def test_decision_authority_is_product_owner() -> None:
    assert "DECISION_AUTHORITY:\nProduct Owner" in _read(BINDING)


def test_all_twelve_binding_conditions_on_main() -> None:
    binding = _read(BINDING)
    for index in range(1, 13):
        assert f"B-{index:02d}" in binding


def test_open_step66sync1_decisions_are_zero() -> None:
    assert "OPEN_PRODUCT_OWNER_DECISIONS_FROM_STEP66SYNC1:\n0" in _read(BINDING)


# --- preservation and normalization ----------------------------------------------------------


def test_historical_evidence_still_present_and_unrewritten() -> None:
    for rel in HISTORICAL_EVIDENCE:
        text = _read(REPO / rel)
        assert text.strip(), rel
        assert "RESOLVED / BINDING" not in text, rel


def test_historical_open_decision_count_still_three() -> None:
    ack = _read(SYNC / "step66sync1-final-partner-acknowledgement.md")
    assert re.search(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*\n?\s*3", ack)


def test_screen_count_is_still_fifteen() -> None:
    """Re-derived by counting spec headings, not read from a summary."""
    headings = re.findall(r"^### 7\.\d+ ", _read(DESIGN_SPEC), re.MULTILINE)
    assert len(headings) == 15


def test_step66d_canonical_identifier_retained() -> None:
    for term in ("Step 66D-ARCH", "66D-DESIGN"):
        assert _git("grep", "-l", term, "HEAD", "--", "docs").strip(), term


def test_ia_options_still_non_binding_and_unselected() -> None:
    binding = _read(BINDING)
    assert re.search(r"remain\s+POC\.0\s+non-binding\s+design\s+options;\s+neither\s+is", binding)
    assert "non-binding until a Product Owner selects it" in _read(PRECEDENCE)


# --- authorization state ----------------------------------------------------------------------


def test_poc_implementation_still_unauthorized() -> None:
    assert "POC_IMPLEMENTATION_AUTHORIZED:\nNO" in _read(BINDING)
    assert re.search(
        r"^POC_IMPLEMENTATION:\s+NOT STARTED / NOT AUTHORIZED$", _read(ADDENDUM), re.MULTILINE
    )


def test_ra2m_still_unauthorized() -> None:
    assert re.search(r"^RA2M:\s+NOT STARTED / NOT AUTHORIZED$", _read(ADDENDUM), re.MULTILINE)


def test_step66d_arch_still_unauthorized() -> None:
    assert re.search(
        r"^STEP66D_ARCH:\s+NOT STARTED / NOT AUTHORIZED$", _read(ADDENDUM), re.MULTILINE
    )


def test_step67poc0_still_unauthorized() -> None:
    assert re.search(r"^STEP67POC0:\s+NOT STARTED / NOT AUTHORIZED$", _read(ADDENDUM), re.MULTILINE)


def test_be3_gates_still_default_false() -> None:
    resume = _read(REPO / "shared" / "sdk" / "tasks" / "resume_request_model.py")
    replay = _read(REPO / "shared" / "sdk" / "tasks" / "replay_request_model.py")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in replay
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in replay


# --- no implementation was merged --------------------------------------------------------------


def _merged_paths() -> list[str]:
    return [
        line
        for line in _git("diff", "--name-only", PRE_MERGE_MAIN, MERGE_COMMIT).splitlines()
        if line
    ]


def test_merge_introduced_no_runtime_or_backend_source() -> None:
    forbidden = ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/")
    assert [p for p in _merged_paths() if p.startswith(forbidden)] == []


def test_merge_introduced_no_frontend_source() -> None:
    suffixes = (".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss")
    assert [p for p in _merged_paths() if p.endswith(suffixes)] == []


def test_merge_introduced_no_infra_or_deployment_config() -> None:
    assert [
        p
        for p in _merged_paths()
        if "docker-compose" in p or p.startswith(("helm/", "k8s/", "charts/"))
    ] == []


def test_merge_changed_thirty_four_paths() -> None:
    assert len(_merged_paths()) == 34


def test_merge_record_commit_adds_only_its_own_files() -> None:
    changed = [
        line
        for line in _git("diff", "--name-only", MERGE_COMMIT, RECORD_COMMIT).splitlines()
        if line
    ]
    allowed = {
        "docs/handoffs/program-sync/step66sync1-m2-canonical-merge-record.md",
        "scripts/verify_step66sync1_m2_canonical_merge.py",
        "tests/test_step66sync1_m2_canonical_merge.py",
        "source/progress.md",
        "scripts/verify_step66sync1_m1_canonicalization.py",
        "tests/test_step66sync1_m1_canonicalization.py",
    }
    assert [p for p in changed if p not in allowed] == []


def test_m1_baseline_correction_is_minimal() -> None:
    """The M1 gate pinned origin/main == c1db4cc; the merge falsified it. Only that was narrowed."""
    for rel in (
        "scripts/verify_step66sync1_m1_canonicalization.py",
        "tests/test_step66sync1_m1_canonicalization.py",
    ):
        numstat = _git("diff", "--numstat", MERGE_COMMIT, RECORD_COMMIT, "--", rel)
        if not numstat:
            continue
        added, deleted, _ = numstat.split("\t", 2)
        assert int(added) <= 15, f"{rel} added {added} lines"
        assert int(deleted) <= 5, f"{rel} deleted {deleted} lines"
        body = _read(REPO / rel)
        assert "merge-base" in body
        assert PRE_MERGE_MAIN in body


def test_m1_gate_still_passes_after_the_merge() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "verify_step66sync1_m1_canonicalization.py")],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS" in result.stdout


def test_progress_record_is_append_only_since_the_merge() -> None:
    """No content line may be removed.

    The M1 commit left progress.md without a trailing newline, so appending after it makes Git
    report the old last line as deleted and immediately re-added. That is the only tolerated
    'deletion': the assertion is that every removed line comes straight back.
    """
    diff = _git("diff", "--unified=0", MERGE_COMMIT, "HEAD", "--", "source/progress.md")
    if not diff:
        return
    removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and line[1:2] != "-"]
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and line[1:2] != "+"]
    assert added, "no lines were appended"
    for line in removed:
        assert line in added, f"content line removed from progress.md: {line!r}"


# --- merge record ------------------------------------------------------------------------------


def test_merge_record_states_every_required_fact() -> None:
    record = _read(MERGE_RECORD)
    for needle in (
        "Step 66SYNC.1-M2",
        "#22",
        PR_HEAD,
        PRE_MERGE_MAIN,
        MERGE_COMMIT,
        "NON-SQUASH MERGE",
        "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS",
        "Canonicalization commit preserved:\nYES",
    ):
        assert needle in record, needle


def test_merge_record_claims_no_unauthorized_stage() -> None:
    record = _read(MERGE_RECORD).lower()
    for phrase in ("poc.0 authorized", "ra-2m authorized", "step 66d-arch authorized"):
        assert phrase not in record


def test_merge_record_records_no_squash_rebase_or_force_push() -> None:
    record = _read(MERGE_RECORD)
    for line in ("Squash:                                           NO", "Force push:", "Rebase:"):
        assert line in record


def test_production_executed_true_count_is_zero_everywhere() -> None:
    for path in (BINDING, ADDENDUM, PRECEDENCE, MERGE_RECORD):
        text = _read(path)
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            assert value == "0", path.name


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "7971ae0c5a5d90a186efd4c52f75988720ce214e"


def test_runtime_guard_scans_current_state_not_only_the_frozen_range() -> None:
    """A runtime path added by any later commit must still be caught."""
    changed = [
        line
        for line in _git("diff", "--name-only", RUNTIME_GUARD_ANCHOR, successor_window_end(RUNTIME_GUARD_ANCHOR)).splitlines()
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
    assert offenders == [], f"protected paths present after this stage: {offenders}"
