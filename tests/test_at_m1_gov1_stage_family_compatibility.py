"""AT-M1-GOV1 -- stage-family governance compatibility: registration logic and mutation probes.

Three layers:

  1. Structural tests    inspect the repaired admission rule and the historical frozen boundary
                         directly, independently of the GOV1 verifier's own reporting
  2. Registration tests  prove exactly which artifacts are admitted and which are rejected
  3. Mutation probes     M01..M09 and X2/X3 each apply ONE forbidden change inside a DISPOSABLE
                         GIT WORKTREE and run the REAL GOV1 verifier as a subprocess, asserting
                         it fails

The probes deliberately exercise the real verifier rather than an in-memory copy of its conditions:
a probe that only re-evaluates a predicate cannot prove the shipped verifier would have caught the
change.

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
GOV1_VERIFIER = ROOT / "scripts" / "verify_at_m1_gov1_stage_family_compatibility.py"
ALIGN1_VERIFIER_REL = "scripts/verify_step66d_align1_delivery_decision_model.py"
ALIGN1_TEST_REL = "tests/test_step66d_align1_delivery_decision_model.py"

EXPECTED_PATHS = {
    ALIGN1_VERIFIER_REL,
    ALIGN1_TEST_REL,
    "scripts/verify_at_m1_gov1_stage_family_compatibility.py",
    "tests/test_at_m1_gov1_stage_family_compatibility.py",
    "docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md",
}

GOV1_BASELINE = "2d4da808b1a89ea278fbb760e27f49047995165e"
ALIGN1_STAGE_HEAD = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gov1_module():
    return _load(GOV1_VERIFIER, "gov1_verifier_under_test")


def align1_module():
    return _load(ROOT / ALIGN1_VERIFIER_REL, "align1_verifier_under_test")


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


# =================================================================================================
# 1. Structural
# =================================================================================================


def test_gov1_scope_registry_is_exactly_five_paths():
    module = gov1_module()
    assert set(module.GOV1_EXPECTED_PATHS) == EXPECTED_PATHS
    assert len(module.GOV1_EXPECTED_PATHS) == 5


def test_changed_paths_equal_the_registry_exactly():
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{GOV1_BASELINE}...HEAD").splitlines()
        if line.strip()
    }
    assert (
        changed == EXPECTED_PATHS
    ), f"unexpected={sorted(changed - EXPECTED_PATHS)} missing={sorted(EXPECTED_PATHS - changed)}"


def test_single_source_admission_rule_exists_and_is_consumed_by_the_test():
    align1 = align1_module()
    assert hasattr(align1, "is_admitted_current_state_path")
    assert hasattr(align1, "is_registered_governance_artifact")
    assert hasattr(align1, "REGISTERED_GOVERNANCE_FAMILIES")
    # The mirrored test must consume the rule, not restate it.
    test_src = read(ALIGN1_TEST_REL)
    assert "is_admitted_current_state_path" in test_src
    assert 'allowed = ("docs/", "scripts/verify_step66", "tests/test_step66")' not in test_src


def test_exactly_two_stage_families_are_registered():
    families = {f[0] for f in align1_module().REGISTERED_GOVERNANCE_FAMILIES}
    assert families == {"step66", "autonomous-team"}


def test_historical_frozen_boundary_is_untouched():
    src = read(ALIGN1_VERIFIER_REL)
    assert f'ALIGN1_STAGE_HEAD = "{ALIGN1_STAGE_HEAD}"' in src
    assert 'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)' in src
    check33 = src.split("def check33_positive_exact_scope")[1].split("\ndef ")[0]
    assert "HEAD" not in check33.replace("ALIGN1_STAGE_HEAD", "")
    assert "unexpected" in check33 and "missing" in check33


def test_historical_scope_still_matches_its_registry_exactly():
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


def test_check33_enforces_missing_direction_behaviorally():
    """R1 finding D-01, case A: a registered-but-unchanged path must make the REAL check33 fail.

    Behavioral, not textual: this passes only if the `missing` difference is ENFORCED, so
    deleting the `if missing:` block (escape X2) is caught even though both set-difference
    expressions remain in the source.
    """
    gov1 = gov1_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    phantom = "docs/handoffs/gov1-rm1-behavioral-probe-phantom.md"
    assert phantom not in registry
    assert gov1.check33_records_failure(align1, registry + (phantom,))


def test_check33_enforces_unexpected_direction_behaviorally():
    """R1 finding D-01, case B: a changed-but-unregistered path must make the REAL check33 fail.

    Catches escape X3 (deleting the `if unexpected:` block) for the same reason as case A.
    """
    gov1 = gov1_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    assert gov1.check33_records_failure(align1, registry[:-1])


def test_check33_behavioral_control_and_state_restore():
    """The untampered registry records no failure, and probing restores the module's state."""
    gov1 = gov1_module()
    align1 = align1_module()
    registry = tuple(align1.ALIGN1_EXPECTED_PATHS)
    align1.FAILURES.append("sentinel-preexisting-failure")
    assert gov1.check33_records_failure(align1, registry[:-1])
    assert not gov1.check33_records_failure(align1, registry)
    assert tuple(align1.ALIGN1_EXPECTED_PATHS) == registry
    assert align1.FAILURES == ["sentinel-preexisting-failure"]


def test_no_governance_bypass_was_introduced():
    for relpath in (ALIGN1_VERIFIER_REL, ALIGN1_TEST_REL):
        src = read(relpath)
        for bypass in ("pytest.mark.skip", "pytest.skip", "xfail"):
            assert bypass not in src, f"{relpath} introduced {bypass}"


# =================================================================================================
# 2. Registration logic (§21)
# =================================================================================================


@pytest.mark.parametrize(
    "path",
    [
        "scripts/verify_step66d_align1_delivery_decision_model.py",
        "tests/test_step66d_align1_delivery_decision_model.py",
        "scripts/verify_at_m1_architecture_reset.py",
        "tests/test_at_m1_architecture_reset.py",
        "scripts/verify_at_m2_team_identity_collaboration.py",
        "tests/test_at_m2_team_identity_collaboration.py",
    ],
)
def test_registered_governance_artifacts_are_accepted(path):
    assert align1_module().is_admitted_current_state_path(path), path


@pytest.mark.parametrize(
    "path",
    [
        "scripts/verify_unregistered_family.py",
        "tests/test_unregistered_family.py",
        "scripts/at_runtime_patch.py",
        "scripts/random_helper.py",
        "tests/at_random_helper.py",
        "tests/random_test_helper.py",
        "shared/sdk/tasks/rbac.py",
        "apps/orchestrator/src/main.py",
        "agents/qa-agent/src/agent.py",
        "migrations/037_example.sql",
        "infra/docker-compose/docker-compose.yml",
        "",
    ],
)
def test_unregistered_and_runtime_paths_are_rejected(path):
    assert not align1_module().is_admitted_current_state_path(path), path


def test_being_under_scripts_or_tests_is_not_sufficient():
    """The whole point of the repair: location does not confer admission."""
    admit = align1_module().is_admitted_current_state_path
    assert not admit("scripts/anything.py")
    assert not admit("tests/anything.py")
    assert admit("scripts/verify_at_m1_architecture_reset.py")
    assert admit("tests/test_at_m1_architecture_reset.py")


# =================================================================================================
# 3. Mutation probes (§22) -- real verifier, real worktree
# =================================================================================================


@pytest.fixture(scope="module")
def probe_worktree():
    """A disposable detached worktree at HEAD, so probes run the REAL verifier on real files."""
    target = Path(tempfile.mkdtemp(prefix="gov1-probe-")) / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(target), "HEAD"],
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
            text=True,
            check=False,
        )
        shutil.rmtree(target.parent, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True, check=False)


def run_gov1(worktree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(worktree / "scripts" / "verify_at_m1_gov1_stage_family_compatibility.py"),
        ],
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
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


def assert_rejected(worktree: Path, label: str) -> None:
    result = run_gov1(worktree)
    assert result.returncode != 0, f"{label}: the GOV1 verifier did NOT reject the mutation"
    assert "FAIL" in result.stdout, f"{label}: no FAIL marker\n{result.stdout[-600:]}"


def test_probe_untampered_control_passes(probe_worktree):
    restore(probe_worktree)
    result = run_gov1(probe_worktree)
    assert result.returncode == 0, result.stdout[-800:]
    assert "AT_M1_GOV1_STAGE_FAMILY_COMPATIBILITY_VERIFY: PASS" in result.stdout


def test_probe_m01_remove_at_verifier_registration(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        r'r"^scripts/verify_at_m\d+[a-z0-9_]*\.py$"',
        r'r"^scripts/verify_NOTHING_at_m\d+[a-z0-9_]*\.py$"',
    )
    assert_rejected(probe_worktree, "M01")


def test_probe_m02_remove_at_test_registration(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        r'r"^tests/test_at_m\d+[a-z0-9_]*\.py$"',
        r'r"^tests/test_NOTHING_at_m\d+[a-z0-9_]*\.py$"',
    )
    assert_rejected(probe_worktree, "M02")


def test_probe_m03_broad_scripts_admission(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'ADMITTED_PATH_PREFIXES = ("docs/",)',
        'ADMITTED_PATH_PREFIXES = ("docs/", "scripts/")',
    )
    assert_rejected(probe_worktree, "M03")


def test_probe_m04_broad_tests_admission(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'ADMITTED_PATH_PREFIXES = ("docs/",)',
        'ADMITTED_PATH_PREFIXES = ("docs/", "tests/")',
    )
    assert_rejected(probe_worktree, "M04")


def test_probe_m05_catch_all_verify_prefix(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        r'("step66", r"^scripts/verify_step66[a-z0-9_]*\.py$", r"^tests/test_step66[a-z0-9_]*\.py$"),',
        r'("step66", r"^scripts/verify_.*\.py$", r"^tests/test_.*\.py$"),',
    )
    assert_rejected(probe_worktree, "M05")


def test_probe_m06_accept_unregistered_stage_family(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "REGISTERED_GOVERNANCE_FAMILIES: tuple[tuple[str, str, str], ...] = (",
        "REGISTERED_GOVERNANCE_FAMILIES: tuple[tuple[str, str, str], ...] = (\n"
        '    ("unregistered-family", r"^scripts/verify_unregistered_family\\.py$",'
        ' r"^tests/test_unregistered_family\\.py$"),',
    )
    assert_rejected(probe_worktree, "M06")


def test_probe_m07_historical_endpoint_becomes_head(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)',
        'git("diff", "--name-only", CANONICAL_MAIN, "HEAD")',
    )
    assert_rejected(probe_worktree, "M07")


def test_probe_m08_historical_equality_weakened_to_subset(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "    missing = sorted(set(ALIGN1_EXPECTED_PATHS) - set(changed))",
        "    missing = []",
    )
    assert_rejected(probe_worktree, "M08")


def test_probe_x2_missing_enforcement_deleted(probe_worktree):
    """R1 escape X2: keep both set-difference computations, delete only `if missing: bad(...)`."""
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "    if missing:\n"
        '        bad(f"check33: registered path not changed by this stage: '
        "{', '.join(missing)}\")\n",
        "",
    )
    assert_rejected(probe_worktree, "X2")


def test_probe_x3_unexpected_enforcement_deleted(probe_worktree):
    """R1 escape X3: keep both set-difference computations, delete only `if unexpected: bad(...)`."""
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        "    if unexpected:\n"
        '        bad(f"check33: unregistered path changed by this stage: '
        "{', '.join(unexpected)}\")\n",
        "",
    )
    assert_rejected(probe_worktree, "X3")


def test_probe_m09_shared_runtime_path_admitted(probe_worktree):
    restore(probe_worktree)
    apply_mutation(
        probe_worktree,
        ALIGN1_VERIFIER_REL,
        'ADMITTED_PATH_PREFIXES = ("docs/",)',
        'ADMITTED_PATH_PREFIXES = ("docs/", "shared/", "runtime/")',
    )
    assert_rejected(probe_worktree, "M09")


def test_probe_worktree_is_restored_after_all_probes(probe_worktree):
    restore(probe_worktree)
    result = run_gov1(probe_worktree)
    assert result.returncode == 0, "the worktree was not restored to a passing state"
