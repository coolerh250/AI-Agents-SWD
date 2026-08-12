"""AT-M1-GOV1-M1 -- canonical merge: topology, frozen stage scope, and surviving D-01 closure.

Three layers:

  1. Merge topology     the merge is a real two-parent merge and all seven PR commits survive
  2. Canonical state    GOV1 stage scope stays frozen; ALIGN1 historical truth is unchanged;
                        registered-family admission is binding and still bounded
  3. Behavioral probes  the merged check33 is DRIVEN in both directions rather than inspected,
                        and the merge verifier is mutation-probed as a real subprocess

Read-only with respect to the repository. Starts no runtime, container, database or external
provider.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "2d4da808b1a89ea278fbb760e27f49047995165e"
GOV1_STAGE_HEAD = "2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c"
MERGE_COMMIT = "d2d9b7380b3c8e95e276547e46e83b9989ce5955"

ALIGN1_CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_STAGE_HEAD = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"

ALIGN1_VERIFIER_REL = "scripts/verify_step66d_align1_delivery_decision_model.py"
GOV1_VERIFIER_REL = "scripts/verify_at_m1_gov1_stage_family_compatibility.py"
MERGE_VERIFIER_REL = "scripts/verify_at_m1_gov1_m1_canonical_merge.py"
RECORD_REL = "docs/handoffs/autonomous-team/at-m1-gov1-m1-canonical-merge-record.md"

GOV1_EXPECTED_PATHS = {
    ALIGN1_VERIFIER_REL,
    "tests/test_step66d_align1_delivery_decision_model.py",
    GOV1_VERIFIER_REL,
    "tests/test_at_m1_gov1_stage_family_compatibility.py",
    "docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md",
}

PR30_COMMITS = (
    "964ca7afb31ec91859a9c8f0deb104c719b9fccc",
    "aa77b0b",
    "690ed76",
    "5b939b773e49d9e5ffd6d10309e10dada5e43f28",
    "36176e4",
    "800679d",
    GOV1_STAGE_HEAD,
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"unloadable module: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def align1_module():
    return _load(ROOT / ALIGN1_VERIFIER_REL, "gov1_m1_align1_under_test")


def merge_verifier_module():
    return _load(ROOT / MERGE_VERIFIER_REL, "gov1_m1_merge_verifier_under_test")


def read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_ancestor(commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


# =================================================================================================
# 1. Merge topology
# =================================================================================================


def test_merge_commit_has_exactly_two_parents():
    parents = git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    assert len(parents) == 3, f"not a two-parent merge: {parents}"
    assert parents[1] == PRE_MERGE_MAIN
    assert parents[2] == GOV1_STAGE_HEAD


@pytest.mark.parametrize("commit", PR30_COMMITS)
def test_every_pr30_commit_survived_the_merge(commit):
    """A squash or rebase merge would leave these unreachable."""
    assert is_ancestor(commit), f"{commit} is not an ancestor of HEAD"


def test_merge_commit_and_endpoints_are_ancestors():
    assert is_ancestor(MERGE_COMMIT)
    assert is_ancestor(PRE_MERGE_MAIN)
    assert is_ancestor(GOV1_STAGE_HEAD)


def test_merge_introduced_only_the_gov1_registry():
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}").splitlines()
        if line.strip()
    }
    assert changed == GOV1_EXPECTED_PATHS


# =================================================================================================
# 2. Canonical state
# =================================================================================================


def test_gov1_stage_scope_is_frozen_and_exact():
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{PRE_MERGE_MAIN}...{GOV1_STAGE_HEAD}").splitlines()
        if line.strip()
    }
    assert changed == GOV1_EXPECTED_PATHS
    assert len(changed) == 5


def test_gov1_stage_touched_no_runtime_or_architecture_path():
    changed = git("diff", "--name-only", f"{PRE_MERGE_MAIN}...{GOV1_STAGE_HEAD}").splitlines()
    forbidden = (
        "apps/",
        "agents/",
        "shared/",
        "migrations/",
        "infra/",
        "runtime/",
        ".github/",
        "docs/architecture/",
        "docs/contracts/",
        "docs/decisions/",
    )
    assert [p for p in changed if p.strip().startswith(forbidden)] == []
    assert "source/progress.md" not in [p.strip() for p in changed]


def test_align1_historical_boundary_survived_the_merge():
    src = read(ALIGN1_VERIFIER_REL)
    assert f'CANONICAL_MAIN = "{ALIGN1_CANONICAL_MAIN}"' in src
    assert f'ALIGN1_STAGE_HEAD = "{ALIGN1_STAGE_HEAD}"' in src
    assert 'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)' in src


def test_align1_historical_scope_still_matches_its_registry_exactly():
    align1 = align1_module()
    historical = sorted(
        line
        for line in git(
            "diff", "--name-only", align1.CANONICAL_MAIN, align1.ALIGN1_STAGE_HEAD
        ).splitlines()
        if line.strip()
    )
    assert len(align1.ALIGN1_EXPECTED_PATHS) == 34
    assert set(historical) == set(align1.ALIGN1_EXPECTED_PATHS)


def test_registered_families_are_still_exactly_two():
    families = {f[0] for f in align1_module().REGISTERED_GOVERNANCE_FAMILIES}
    assert families == {"step66", "autonomous-team"}


@pytest.mark.parametrize(
    "path",
    [
        "scripts/verify_step66d_align1_delivery_decision_model.py",
        "scripts/verify_at_m1_architecture_reset.py",
        "tests/test_at_m1_architecture_reset.py",
        "scripts/verify_at_m2_team_identity_collaboration.py",
        "tests/test_at_m8_delivery_closure.py",
        MERGE_VERIFIER_REL,
        "tests/test_at_m1_gov1_m1_canonical_merge.py",
        RECORD_REL,
    ],
)
def test_this_stages_own_artifacts_are_admitted(path):
    """The merge record must pass the very admission rule this stage canonicalized."""
    assert align1_module().is_admitted_current_state_path(path), path


@pytest.mark.parametrize(
    "path",
    [
        "scripts/verify_unregistered_family.py",
        "tests/test_unregistered_family.py",
        "scripts/at_runtime_patch.py",
        "tests/random_test_helper.py",
        "shared/sdk/tasks/rbac.py",
        "apps/orchestrator/src/main.py",
        "",
    ],
)
def test_admission_is_still_bounded_after_the_merge(path):
    assert not align1_module().is_admitted_current_state_path(path), path


def test_no_broad_path_allowlist_was_introduced():
    src = read(ALIGN1_VERIFIER_REL)
    assert 'ADMITTED_PATH_PREFIXES = ("docs/",)' in src
    assert 'ADMITTED_PATH_PREFIXES = ("docs/", "scripts/"' not in src
    assert 'ADMITTED_PATH_PREFIXES = ("docs/", "tests/"' not in src


# =================================================================================================
# 3. D-01 closure survived as behavioral
# =================================================================================================


def test_merged_check33_enforces_missing_direction():
    merge_verifier = merge_verifier_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    phantom = "docs/handoffs/at-m1-gov1-m1-phantom-probe.md"
    assert phantom not in registry
    assert merge_verifier.check33_records_failure(align1, registry + (phantom,))


def test_merged_check33_enforces_unexpected_direction():
    merge_verifier = merge_verifier_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    assert merge_verifier.check33_records_failure(align1, registry[:-1])


def test_behavioral_probe_control_and_state_restore():
    merge_verifier = merge_verifier_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    align1.FAILURES.append("sentinel-preexisting")
    assert merge_verifier.check33_records_failure(align1, registry[:-1])
    assert not merge_verifier.check33_records_failure(align1, registry)
    assert tuple(align1.ALIGN1_EXPECTED_PATHS) == registry
    assert align1.FAILURES == ["sentinel-preexisting"]


def test_gov1_verifier_still_carries_its_behavioral_gates():
    src = read(GOV1_VERIFIER_REL)
    for name in ("check11a", "check11b", "check11c"):
        assert f'"{name}"' in src
    assert "check33_records_failure" in src


# =================================================================================================
# 4. Mutation probes against the real merge verifier
# =================================================================================================


@pytest.fixture(scope="module")
def probe_worktree():
    target = Path(tempfile.mkdtemp(prefix="gov1m1-")) / "wt"
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "worktree", "add", "--detach", str(target), "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        yield target
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        shutil.rmtree(target.parent, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True, check=False)


def run_merge_verifier(worktree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(worktree / MERGE_VERIFIER_REL)],
        cwd=worktree,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def restore(worktree: Path) -> None:
    subprocess.run(["git", "checkout", "--", "."], cwd=worktree, capture_output=True, check=False)


def apply_mutation(worktree: Path, relpath: str, old: str, new: str) -> None:
    path = worktree / relpath
    src = path.read_text(encoding="utf-8")
    assert old in src, f"mutation anchor not found in {relpath}: {old[:60]!r}"
    path.write_text(src.replace(old, new), encoding="utf-8")


def assert_rejected(worktree: Path, label: str) -> None:
    result = run_merge_verifier(worktree)
    assert result.returncode != 0, f"{label}: the merge verifier did NOT reject the mutation"
    assert "FAIL" in result.stdout, f"{label}: no FAIL marker\n{result.stdout[-600:]}"


def test_probe_untampered_control_passes(probe_worktree):
    restore(probe_worktree)
    result = run_merge_verifier(probe_worktree)
    assert result.returncode == 0, result.stdout[-800:]
    assert "AT_M1_GOV1_M1_CANONICAL_MERGE_VERIFY: PASS" in result.stdout


def test_probe_p01_historical_endpoint_moved(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)',
        'git("diff", "--name-only", CANONICAL_MAIN, "HEAD")',
    )
    assert_rejected(probe_worktree, "P01")


def test_probe_p02_missing_enforcement_deleted(probe_worktree):
    """The D-01 escape must still be caught by the merge verifier."""
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "    if missing:\n"
        '        bad(f"check33: registered path not changed by this stage: '
        "{', '.join(missing)}\")\n",
        "",
    )
    assert_rejected(probe_worktree, "P02")


def test_probe_p03_unexpected_enforcement_deleted(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "    if unexpected:\n"
        '        bad(f"check33: unregistered path changed by this stage: '
        "{', '.join(unexpected)}\")\n",
        "",
    )
    assert_rejected(probe_worktree, "P03")


def test_probe_p04_broad_scripts_admission(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'ADMITTED_PATH_PREFIXES = ("docs/",)',
        'ADMITTED_PATH_PREFIXES = ("docs/", "scripts/")',
    )
    assert_rejected(probe_worktree, "P04")


def test_probe_p05_at_family_deregistered(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        r'r"^scripts/verify_at_m\d+[a-z0-9_]*\.py$"',
        r'r"^scripts/verify_NOTHING_at_m\d+[a-z0-9_]*\.py$"',
    )
    assert_rejected(probe_worktree, "P05")


def test_probe_p06_merge_record_chain_falsified(probe_worktree):
    restore(probe_worktree)
    apply_mutation(probe_worktree, RECORD_REL, MERGE_COMMIT, "0" * 40)
    assert_rejected(probe_worktree, "P06")


def test_probe_p07_merge_record_claims_squash(probe_worktree):
    restore(probe_worktree)
    apply_mutation(probe_worktree, RECORD_REL, "NON-SQUASH MERGE", "SQUASH MERGE")
    assert_rejected(probe_worktree, "P07")


def test_probe_worktree_is_restored_after_all_probes(probe_worktree):
    restore(probe_worktree)
    result = run_merge_verifier(probe_worktree)
    assert result.returncode == 0, "the worktree was not restored to a passing state"
