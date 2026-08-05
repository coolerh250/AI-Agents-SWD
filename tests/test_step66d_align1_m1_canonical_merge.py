"""Tests for Step 66D-ALIGN1-M1 canonical merge.

Offline by design: no container, no database, no network, no secret access. Claims are re-derived
from Git objects and from parsed source rather than asserted against a document that agrees with
itself.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
SCRIPT = SCRIPTS / "verify_step66d_align1_m1_canonical_merge.py"

PRE_MERGE_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_COMMIT = "f25d12baea7a76e1bc5d29bf884765f16c8536ac"
RM1_COMMIT = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"
MERGE_COMMIT = "ad2d218186c8cb26af0a2fad6d3fa86a43703db5"

HANDOFFS = REPO / "docs" / "handoffs" / "66d-delivery-acceptance"
RECORD = HANDOFFS / "step66d-align1-m1-canonical-merge-record.md"
MANIFEST = HANDOFFS / "step66d-align1-rm1-stage-boundary-manifest.md"
ALIGN1_VERIFIER = SCRIPTS / "verify_step66d_align1_delivery_decision_model.py"

CROSS_STAGE_FILES = (
    "scripts/verify_step66sync1_claude_code_reconciliation.py",
    "tests/test_step66sync1_claude_code_reconciliation.py",
    "scripts/verify_step66sync1_final_partner_reconciliation.py",
    "tests/test_step66sync1_final_partner_reconciliation.py",
    "scripts/verify_step66sync1_m1_canonicalization.py",
    "tests/test_step66sync1_m1_canonicalization.py",
    "scripts/verify_step66sync1_m2_canonical_merge.py",
    "tests/test_step66sync1_m2_canonical_merge.py",
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
    "tests/test_step66c4_be3_ra2m_canonicalization.py",
    "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py",
    "tests/test_step66c4_be3_ra2m2_canonical_merge.py",
)

FROZEN_STAGES = {
    "claude_code": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "828ea900d53edab6f8441f50723e52955a1049e1",
    ),
    "final_partner": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "2396c6c7002387c886463bd38158b9ddc3bfb9e2",
    ),
    "m1": ("c1db4ccbfd88fa775e4761c932835896b9b980ed", "1278b8944e3a8f824a9b35f82382fa8587e7989d"),
    "ra2m": (
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
        "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6",
    ),
    "m2": ("7971ae0c5a5d90a186efd4c52f75988720ce214e", "44ab32ceab60d417ef1e0800be6cd00fc730b12e"),
    "ra2m2": (
        "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798",
        "64467fefc9a9ec303f9ddf4c0ce6d46486504d71",
    ),
}

RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    return result.stdout.decode("utf-8").strip() if result.returncode == 0 else ""


def _ancestor(commit: str, of: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, of], cwd=REPO, check=False
        ).returncode
        == 0
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"m1_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- verifier -----------------------------------------------------------------------------------


def test_verifier_exists() -> None:
    assert SCRIPT.is_file()


def test_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert "STEP66D_ALIGN1_M1_CANONICAL_MERGE_VERIFY: PASS" in result.stdout.decode("utf-8")


# --- merge shape, re-derived from Git ------------------------------------------------------------


def test_merge_commit_has_exactly_two_parents() -> None:
    parents = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert len(parents) == 2, f"a squash or fast-forward would not have two parents: {parents}"


def test_merge_parents_are_pre_merge_main_and_pr_head() -> None:
    parents = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert parents == [PRE_MERGE_MAIN, RM1_COMMIT]


@pytest.mark.parametrize("commit", [ALIGN1_COMMIT, RM1_COMMIT, PRE_MERGE_MAIN, MERGE_COMMIT])
def test_commit_is_preserved_in_main_history(commit: str) -> None:
    assert _ancestor(commit, "HEAD"), f"{commit[:8]} was lost from main history"


def test_branch_carried_exactly_two_commits() -> None:
    assert _git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{RM1_COMMIT}") == "2"


def test_align1_commit_is_the_parent_of_the_rm1_commit() -> None:
    """A rebase or squash would have broken this direct link."""
    assert _git("show", "--no-patch", "--format=%P", RM1_COMMIT).split() == [ALIGN1_COMMIT]


def test_original_align1_commit_message_is_unchanged() -> None:
    message = subprocess.run(
        ["git", "log", "-1", "--format=%B", ALIGN1_COMMIT],
        cwd=REPO,
        stdout=subprocess.PIPE,
        check=False,
    ).stdout.decode("utf-8")
    assert "552" in message, "the historical commit message was rewritten"


# --- frozen scopes survived the merge ------------------------------------------------------------


# The two Step 66SYNC.1 partner reconciliation heads are reachable commits but deliberately NOT
# ancestors of main: Step 66SYNC.1-M1 imported their content by committed-object extraction rather
# than by merging their branches. Their ranges are still frozen and still resolvable.
IN_MAIN_HISTORY = {"m1", "ra2m", "m2", "ra2m2"}


@pytest.mark.parametrize("stage", sorted(FROZEN_STAGES))
def test_historical_stage_range_still_frozen(stage: str) -> None:
    base, head = FROZEN_STAGES[stage]
    assert _git("rev-parse", f"{base}^{{commit}}") == base, f"{stage} baseline does not resolve"
    assert _git("rev-parse", f"{head}^{{commit}}") == head, f"{stage} endpoint does not resolve"
    assert _ancestor(base, head), f"{stage} range is not well-formed"


@pytest.mark.parametrize("stage", sorted(IN_MAIN_HISTORY))
def test_stage_endpoint_reachable_from_main(stage: str) -> None:
    assert _ancestor(FROZEN_STAGES[stage][1], "HEAD")


@pytest.mark.parametrize("stage", sorted(set(FROZEN_STAGES) - IN_MAIN_HISTORY))
def test_partner_heads_were_imported_not_merged(stage: str) -> None:
    """Their content is in main; their commits are not. That is how Step 66SYNC.1-M1 built them."""
    assert not _ancestor(FROZEN_STAGES[stage][1], "HEAD")


def test_align1_positive_scope_is_frozen() -> None:
    body = _read(ALIGN1_VERIFIER)
    assert f'ALIGN1_STAGE_HEAD = "{RM1_COMMIT}"' in body
    assert '"--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD' in body


def test_align1_frozen_range_yields_exactly_the_registered_paths() -> None:
    module = _load("verify_step66d_align1_delivery_decision_model")
    actual = {p for p in _git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines() if p}
    assert len(actual) == 34
    assert actual == set(module.ALIGN1_EXPECTED_PATHS)


@pytest.mark.parametrize(
    "rel", CROSS_STAGE_FILES + ("scripts/verify_step66d_align1_delivery_decision_model.py",)
)
def test_no_positive_scope_resolves_against_head(rel: str) -> None:
    body = _read(REPO / rel)
    offenders = [
        m
        for m in re.findall(r'diff", "--name-only", [^)]*"HEAD"', body)
        if "RUNTIME_GUARD_ANCHOR" not in m
    ]
    assert offenders == [], f"{rel}: {offenders}"


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_runtime_guard_survived_the_merge(rel: str) -> None:
    body = _read(REPO / rel)
    assert "RUNTIME_GUARD_ANCHOR" in body
    guard = body[body.index("RUNTIME_GUARD_ANCHOR") :]
    for prefix in RUNTIME_PREFIXES:
        assert f'"{prefix}"' in guard, f"{rel} runtime guard omits {prefix}"


def test_align1_runtime_denylist_did_not_freeze_with_the_scope() -> None:
    body = _read(ALIGN1_VERIFIER)
    assert 'git("diff", "--name-only", CANONICAL_MAIN).splitlines()' in body


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
@pytest.mark.parametrize(
    "generic", ['"docs/",', '"scripts/verify_step66",', '"tests/test_step66",']
)
def test_no_generic_admission_reintroduced(rel: str, generic: str) -> None:
    verifier = _load("verify_step66d_align1_m1_canonical_merge")
    assert generic not in verifier._acceptance_body(_read(REPO / rel))


# --- merge record ---------------------------------------------------------------------------------


def test_merge_record_exists_in_the_existing_handoff_directory() -> None:
    assert RECORD.is_file()
    assert RECORD.parent == HANDOFFS


@pytest.mark.parametrize("finding", ["R1-F01", "R1-F02", "R1-F03", "R1-F04", "R1-F05"])
def test_merge_record_reports_finding_closed(finding: str) -> None:
    assert re.search(rf"{finding}:\s+CLOSED", _read(RECORD))


@pytest.mark.parametrize("decision", ["66D-D01", "66D-D02", "66D-D03", "66D-D04"])
def test_merge_record_canonicalizes_decision(decision: str) -> None:
    assert re.search(rf"{decision}:\s+RESOLVED / BINDING / CANONICALIZED", _read(RECORD))


def test_merge_record_states_non_squash_and_the_exact_shas() -> None:
    record = _read(RECORD)
    assert "NON-SQUASH MERGE" in record
    for sha in (PRE_MERGE_MAIN, ALIGN1_COMMIT, RM1_COMMIT, MERGE_COMMIT):
        assert sha in record, sha


def test_merge_record_discloses_the_bounded_adaptation() -> None:
    record = _read(RECORD)
    assert "BOUNDED POST-MERGE SCOPE FREEZE" in record
    assert "+10 / -1" in record and "+9 / -4" in record


def test_merge_record_tracks_both_advisories_without_fixing_them() -> None:
    record = _read(RECORD)
    assert "ADV-VERIFIER-01" in record and "ADV-VERIFIER-02" in record
    assert "TRACKED / NOT BLOCKING THIS MERGE" in record


def test_advisory_files_were_not_modified_by_this_stage() -> None:
    changed = _git("diff", "--name-only", MERGE_COMMIT).splitlines()
    for rel in (
        "scripts/verify_step66sync1_claude_design_reconciliation.py",
        "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
    ):
        assert rel not in changed, f"{rel} was modified; advisories are out of scope here"


def test_boundary_manifest_records_the_post_merge_boundary() -> None:
    manifest = _read(MANIFEST)
    for needle in (RM1_COMMIT, MERGE_COMMIT, "64467fe..6a8a7bf"):
        assert needle in manifest, needle
    assert "NOT YET ESTABLISHED" not in manifest


# --- authorization posture -------------------------------------------------------------------------


def test_no_runtime_or_infra_path_was_merged() -> None:
    changed = [p for p in _git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines() if p]
    assert [p for p in changed if p.startswith(RUNTIME_PREFIXES)] == []
    assert [
        p for p in changed if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql"))
    ] == []


def test_legacy_delivery_package_source_untouched() -> None:
    changed = _git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines()
    assert [p for p in changed if "delivery_package" in p.lower()] == []


def test_subsequent_stages_remain_unauthorized() -> None:
    record = re.sub(r"\s+", " ", _read(RECORD))
    for stage in ("Step 66D-DESIGN", "Step 67POC.0", "RA-2I0"):
        assert stage in record
    assert "NOT AUTHORIZED" in record
    assert "STILL NOT DECIDED" in record, "the bounded QA rerun count must remain undecided"


def test_production_count_zero() -> None:
    assert "production_executed_true_count:           0" in _read(RECORD)
