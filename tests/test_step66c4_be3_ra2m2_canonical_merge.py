"""Tests for Step 66C.4-BE3-RA-2M2 canonical merge.

Offline by design: no container, no database, no Vault, no OIDC provider, no external identity
provider, no Kubernetes API, no network, no secret access. The merge facts are re-derived from Git
objects rather than read out of the merge record.
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
try:
    from successor_lifecycle import frozen_artifact_is_authorized  # noqa: E402
    from successor_lifecycle import successor_window_end  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def successor_window_end(_baseline: str = "") -> str:
        """Strictest fallback: with no lifecycle module the window stays HEAD-relative."""
        return "HEAD"

    def frozen_artifact_is_authorized(
        _relpath: str, historical: str, current: str
    ) -> tuple[bool, str]:
        """Strictest fallback: with no lifecycle module nothing may diverge at all."""
        return historical == current, "no freeze-amendment authority is available"


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66c4_be3_ra2m2_canonical_merge.py"

SECURITY = REPO / "docs" / "security"
CONTRACTS = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFFS = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
MASTER = REPO / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = REPO / "docs" / "test"

INVENTORY = SECURITY / "be3-ra2-current-state-identity-secret-inventory.md"
THREAT_MODEL = SECURITY / "be3-ra2-identity-secret-threat-and-trust-analysis.md"
DECISION_PACKAGE = CONTRACTS / "be3-ra2-identity-secret-provisioning-decision-package.md"
STAGE_PROPOSAL = HANDOFFS / "be3-ra2-implementation-stage-decomposition.md"
PLANNING_EVIDENCE = TEST_DOCS / "step66c4-be3-ra2-identity-secret-decision-evidence.md"
STAGE_INDEX = MASTER / "next-executable-stage-sequence.md"

BINDING = CONTRACTS / "step66c4-be3-ra2-binding-decisions.md"
ADDENDUM = MASTER / "step66c4-be3-ra2-current-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MERGE_RECORD = HANDOFFS / "step66c4-be3-ra2m2-canonical-merge-record.md"

PRE_MERGE_MAIN = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"
PR_HEAD = "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6"
MERGE_COMMIT = "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798"
PLANNING_HEAD = "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
# This stage's own post-merge record commit. The bounded-adaptation guard below
# measures what THIS stage changed, not what later authorized stages changed.
RECORD_COMMIT = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"

HISTORICAL_EVIDENCE = (
    "docs/security/be3-ra2-current-state-identity-secret-inventory.md",
    "docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md",
    "docs/contracts/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-identity-secret-provisioning-decision-package.md",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-implementation-stage-decomposition.md",
    "docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md",
    "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
    "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
    "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md",
)

DECISIONS = tuple(f"RA2-D{index:02d}" for index in range(1, 13))
CONDITIONS = tuple(f"RA2-C{index:02d}" for index in range(1, 7))
STAGES = (
    "RA2I0",
    "RA2I4P",
    "RA2I4A",
    "RA2I4B",
    "RA2I1",
    "RA2I3",
    "RA2I2",
    "RA2I5",
    "RA2I6",
    "RA2R",
    "RA3",
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
            ["git", "merge-base", "--is-ancestor", commit, descendant], cwd=REPO, check=False
        ).returncode
        == 0
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(decision: str) -> str:
    match = re.search(rf"^## {decision} .*?(?=^## |\Z)", _read(BINDING), re.MULTILINE | re.DOTALL)
    assert match is not None, decision
    return match.group(0)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# --- verifier ---------------------------------------------------------------------------------


def _git_blob_text(commit: str, rel: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{rel}"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.decode("utf-8") if result.returncode == 0 else ""


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
    assert "STEP66C4_BE3_RA2M2_CANONICAL_MERGE_VERIFY: PASS" in result.stdout


# --- merge shape, re-derived from Git -----------------------------------------------------------


def test_merge_commit_exists() -> None:
    assert _git("cat-file", "-t", MERGE_COMMIT) == "commit"


def test_merge_commit_has_exactly_two_parents() -> None:
    assert len(_git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()) == 3


def test_first_parent_is_pre_merge_main() -> None:
    assert _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()[1] == PRE_MERGE_MAIN


def test_second_parent_is_pr_head() -> None:
    assert _git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()[2] == PR_HEAD


def test_merge_commit_in_main_history() -> None:
    assert _is_ancestor(MERGE_COMMIT, "HEAD")


def test_canonicalization_commit_retained() -> None:
    assert _is_ancestor(PR_HEAD, "HEAD")
    assert _git("cat-file", "-t", PR_HEAD) == "commit"


def test_pre_merge_main_retained() -> None:
    assert _is_ancestor(PRE_MERGE_MAIN, "HEAD")


def test_merge_was_not_squashed() -> None:
    """A squash merge would leave a single-parent commit and drop edafc0c from history."""
    assert len(_git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()) == 3
    assert _is_ancestor(PR_HEAD, "HEAD")


def test_merge_commit_references_the_pull_request() -> None:
    assert "#23" in _git("show", "--no-patch", "--format=%s", MERGE_COMMIT)


def test_pr_was_one_commit_above_main() -> None:
    assert _git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{PR_HEAD}") == "1"


def test_planning_branch_remains_unmerged() -> None:
    assert _git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision") == (
        PLANNING_HEAD
    )
    assert not _is_ancestor(PLANNING_HEAD, "HEAD")


# --- historical evidence on main ------------------------------------------------------------------


def test_historical_artifacts_present_on_main() -> None:
    for path in (
        INVENTORY,
        THREAT_MODEL,
        DECISION_PACKAGE,
        STAGE_PROPOSAL,
        PLANNING_EVIDENCE,
        STAGE_INDEX,
    ):
        assert path.is_file(), path.name


def test_historical_artifacts_byte_identical_to_planning_commit() -> None:
    """Byte-identical, or an AT-D12 amendment of the declared shape on a named path."""
    for rel in HISTORICAL_EVIDENCE:
        source = _git("rev-parse", f"{PLANNING_HEAD}:{rel}")
        if _git("rev-parse", f"HEAD:{rel}") == source:
            continue
        allowed, why = frozen_artifact_is_authorized(
            rel, _git_blob_text(PLANNING_HEAD, rel), _git_blob_text("HEAD", rel)
        )
        assert allowed, f"{rel}: {why}"


def test_pending_wording_preserved() -> None:
    package = _read(DECISION_PACKAGE)
    assert "PENDING" in package
    assert "PRODUCT_OWNER_DECISION_REQUIRED" in package
    assert "Decided by Claude Code: 0" in package


def test_no_historical_document_rewritten_with_new_status() -> None:
    for path in (
        INVENTORY,
        THREAT_MODEL,
        DECISION_PACKAGE,
        STAGE_PROPOSAL,
        PLANNING_EVIDENCE,
        STAGE_INDEX,
    ):
        assert "RESOLVED / BINDING" not in _read(path), path.name


def test_historical_test_count_still_seventy_nine() -> None:
    assert "79 tests passed" in _read(STAGE_INDEX)


def test_current_test_count_correction_recorded() -> None:
    addendum = _read(ADDENDUM)
    assert "100 passed / 0 skipped / 0 failed" in addendum
    assert "79 tests passed" in addendum
    assert "79 tests passed" in _read(PRECEDENCE)


def test_verified_test_count_is_one_hundred() -> None:
    """Re-derived by running the merged RA-2 planning suite, not read from any document."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "100 passed" in result.stdout


# --- binding decisions on main -----------------------------------------------------------------------


def test_all_twelve_decisions_binding_on_main() -> None:
    for decision in DECISIONS:
        assert re.search(r"STATUS:\s+RESOLVED / BINDING", _section(decision)), decision


def test_decision_summary_and_authority() -> None:
    binding = _read(BINDING)
    assert "RA2_D01_D12:\nRESOLVED / BINDING" in binding
    assert "DECISION_AUTHORITY:\nProduct Owner" in binding


def test_all_six_conditions_binding_on_main() -> None:
    binding = _read(BINDING)
    for condition in CONDITIONS:
        assert condition in binding, condition
    assert "RA2_C01_C06:\nRESOLVED / BINDING" in binding


def test_key_selections_survived_the_merge() -> None:
    expectations = {
        "RA2-D01": "Enterprise OIDC",
        "RA2-D02": "Authorization Code Flow with PKCE",
        "RA2-D03": "Platform-owned RBAC is the authorization source of truth",
        "RA2-D04": "projected ServiceAccount OIDC",
        "RA2-D05": "same projected workload OIDC model",
        "RA2-D06": "HashiCorp Vault, non-dev",
        "RA2-D07": "SecretRef abstraction",
        "RA2-D08": "GitOps-controlled provisioning",
        "RA2-D09": "Credential-specific lifecycle controls",
        "RA2-D10": "Dedicated human break-glass identity",
        "RA2-D11": "isolated non-production Kubernetes",
        "RA2-D12": "Activation is not allowed until the complete chain is validated",
    }
    for decision, needle in expectations.items():
        assert needle in _flat(_section(decision)), decision


def test_hmac_still_local_test_only() -> None:
    flat = _flat(_section("RA2-D05"))
    assert "LOCAL / TEST ONLY" in flat
    assert "DISABLED IN SHARED RUNTIME" in flat


def test_vault_agent_versus_csi_still_unselected() -> None:
    flat = _flat(_section("RA2-D07"))
    assert "Vault Agent versus CSI is NOT selected" in flat
    assert "RA-2I4P" in flat
    assert "DEFERRED TO RA-2I4P" in _read(MERGE_RECORD)


# --- sequence and authorization ------------------------------------------------------------------------


def test_sequence_present_and_ordered() -> None:
    chain = re.search(r"RA-2M\n(?:\s*->\s*RA-[\w]+\n)+", _read(BINDING))
    assert chain is not None
    assert re.findall(r"RA-[\w]+", chain.group(0)) == [
        "RA-2M",
        "RA-2I0",
        "RA-2I4P",
        "RA-2I4A",
        "RA-2I4B",
        "RA-2I1",
        "RA-2I3",
        "RA-2I2",
        "RA-2I5",
        "RA-2I6",
        "RA-2R",
        "RA-3",
    ]


def test_sequence_is_not_an_authorization() -> None:
    binding = _read(BINDING)
    assert "APPROVED EXECUTION SEQUENCE" in binding
    assert "NOT IMPLEMENTATION AUTHORIZATION" in binding
    assert "RA2_IMPLEMENTATION:\nNOT STARTED / NOT AUTHORIZED" in binding


def test_every_stage_unauthorized_in_binding_record() -> None:
    binding = _read(BINDING)
    for stage in STAGES:
        assert re.search(rf"^{stage}:\s+NOT AUTHORIZED$", binding, re.MULTILINE), stage


def test_every_stage_unauthorized_in_merge_record() -> None:
    record = _read(MERGE_RECORD)
    for stage in (
        "RA-2I0",
        "RA-2I4P",
        "RA-2I4A",
        "RA-2I4B",
        "RA-2I1",
        "RA-2I3",
        "RA-2I2",
        "RA-2I5",
        "RA-2I6",
        "RA-2R",
        "RA-3",
    ):
        assert re.search(rf"^{re.escape(stage)}:\s+NOT AUTHORIZED$", record, re.MULTILINE), stage


# --- runtime state re-derived from source ----------------------------------------------------------------


def test_be3_gates_still_default_false() -> None:
    resume = _read(REPO / "shared" / "sdk" / "tasks" / "resume_request_model.py")
    replay = _read(REPO / "shared" / "sdk" / "tasks" / "replay_request_model.py")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in replay
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in replay


def test_task_api_still_trusts_request_headers() -> None:
    source = _read(REPO / "apps" / "orchestrator" / "src" / "task_api.py")
    assert "X-Task-Actor" in source
    assert "X-Task-Role" in source


def test_oidc_still_disabled() -> None:
    assert _git("grep", "-l", "OidcDisabledError", "--", "shared", "apps").strip()


def test_vault_directory_still_has_no_configuration() -> None:
    vault_dir = REPO / "infra" / "vault"
    if not vault_dir.is_dir():
        return
    assert [p for p in vault_dir.rglob("*") if p.is_file() and p.name != ".gitkeep"] == []


# --- no implementation merged ------------------------------------------------------------------------------


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


def test_merge_introduced_no_manifest_or_chart() -> None:
    assert [
        p
        for p in _merged_paths()
        if "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
        or p.endswith((".yaml", ".yml"))
    ] == []


def test_merge_changed_sixteen_paths() -> None:
    assert len(_merged_paths()) == 16


# --- post-merge record scope, including the bounded adaptation ---------------------------------------------------


def _post_merge_paths() -> list[str]:
    out = _git("diff", "--name-only", MERGE_COMMIT, RECORD_COMMIT).splitlines()
    return [line.strip() for line in out if line.strip()]


def test_post_merge_commit_adds_only_its_own_artifacts() -> None:
    allowed = {
        "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
        "step66c4-be3-ra2m2-canonical-merge-record.md",
        "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py",
        "tests/test_step66c4_be3_ra2m2_canonical_merge.py",
        "source/progress.md",
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
    }
    assert [p for p in _post_merge_paths() if p not in allowed] == []


def test_no_historical_evidence_touched_after_the_merge() -> None:
    for rel in HISTORICAL_EVIDENCE:
        assert rel not in _post_merge_paths(), rel


def test_bounded_adaptation_is_minimal() -> None:
    """The RA-2M1 scope allowlist may gain only the two RA-2M2 filenames."""
    for rel in (
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
    ):
        numstat = _git("diff", "--numstat", MERGE_COMMIT, RECORD_COMMIT, "--", rel)
        if not numstat:
            continue
        added, deleted, _ = numstat.split("\t", 2)
        assert int(added) <= 4, f"{rel} added {added} lines"
        assert int(deleted) == 0, f"{rel} deleted {deleted} lines"


def test_bounded_adaptation_admits_no_runtime_path() -> None:
    for rel in (
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
    ):
        tail = _read(REPO / rel).split("allowed_exact")[-1][:900]
        for prefix in ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/"):
            assert f'"{prefix}"' not in tail, f"{rel} admitted {prefix}"


def test_ra2m1_verifier_still_passes_after_the_merge() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "verify_step66c4_be3_ra2m_canonicalization.py")],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS" in result.stdout


def test_progress_record_is_append_only_since_the_merge() -> None:
    diff = _git("diff", "--unified=0", MERGE_COMMIT, "HEAD", "--", "source/progress.md")
    if not diff:
        return
    removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and line[1:2] != "-"]
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and line[1:2] != "+"]
    assert added, "no lines were appended"
    for line in removed:
        assert line in added, f"content line removed from progress.md: {line!r}"


# --- merge record -----------------------------------------------------------------------------------------------


def test_merge_record_states_every_required_fact() -> None:
    record = _read(MERGE_RECORD)
    for needle in (
        "Step 66C.4-BE3-RA-2M2",
        "#23",
        PR_HEAD,
        PRE_MERGE_MAIN,
        MERGE_COMMIT,
        PLANNING_HEAD,
        "NON-SQUASH MERGE",
        "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS",
        "Canonicalization commit preserved:\nYES",
        "Historical evidence:\nPRESERVED",
        "168 passed",
    ):
        assert needle in record, needle


def test_merge_record_records_discipline() -> None:
    record = _read(MERGE_RECORD)
    for line in ("Squash:", "Rebase:", "Force push:", "Admin bypass:", "Amend:"):
        assert line in record, line
    assert "--match-head-commit:          YES" in record


def test_production_executed_true_count_is_zero_everywhere() -> None:
    for path in (BINDING, ADDENDUM, MERGE_RECORD, PRECEDENCE):
        text = _read(path)
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            assert value == "0", path.name


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798"


def test_runtime_guard_scans_current_state_not_only_the_frozen_range() -> None:
    """A runtime path added by any later commit must still be caught."""
    changed = [
        line
        for line in _git(
            "diff", "--name-only", RUNTIME_GUARD_ANCHOR, successor_window_end(RUNTIME_GUARD_ANCHOR)
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
    assert offenders == [], f"protected paths present after this stage: {offenders}"
