"""Step 66D-ALIGN1-RM1 — fixed-range verifier integrity remediation.

Closes Step 66D-ALIGN1-R1 findings R1-F01..R1-F05. These tests exercise the actual path-set,
range and manifest decision logic -- not the verifier's output string.

Offline and read-only. No container, database, Redis, Vault, OIDC provider, Kubernetes API,
agent workflow or external provider is started, and no secret is read.
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

CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_COMMIT = "f25d12baea7a76e1bc5d29bf884765f16c8536ac"

MANIFEST = (
    REPO
    / "docs"
    / "handoffs"
    / "66d-delivery-acceptance"
    / "step66d-align1-rm1-stage-boundary-manifest.md"
)
RM1_EVIDENCE = REPO / "docs" / "test" / "step66d-align1-rm1-verifier-remediation-evidence.md"
ALIGN1_EVIDENCE = REPO / "docs" / "test" / "step66d-align1-canonical-alignment-evidence.md"

STAGE_FILES = {
    "verify_step66sync1_claude_code_reconciliation": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "828ea900d53edab6f8441f50723e52955a1049e1",
    ),
    "verify_step66sync1_final_partner_reconciliation": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "2396c6c7002387c886463bd38158b9ddc3bfb9e2",
    ),
    "verify_step66sync1_m1_canonicalization": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "1278b8944e3a8f824a9b35f82382fa8587e7989d",
    ),
    "verify_step66c4_be3_ra2m_canonicalization": (
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
        "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6",
    ),
}

RECORD_RANGES = {
    "verify_step66sync1_m2_canonical_merge": (
        "7971ae0c5a5d90a186efd4c52f75988720ce214e",
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
    ),
    "verify_step66c4_be3_ra2m2_canonical_merge": (
        "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798",
        "64467fefc9a9ec303f9ddf4c0ce6d46486504d71",
    ),
}

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

PROBE_DOCS = "docs/review-probes/unrelated-governance-probe.md"
PROBE_VERIFIER = "scripts/verify_step66_unrelated_probe.py"
PROBE_TEST = "tests/test_step66_unrelated_probe.py"
PROBE_RUNTIME = "apps/review_probe/unauthorized_runtime_change.txt"
ALL_PROBES = (PROBE_DOCS, PROBE_VERIFIER, PROBE_TEST, PROBE_RUNTIME)

RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    return result.stdout.decode("utf-8").strip() if result.returncode == 0 else ""


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"rm1_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- R1-F01/F02/F03: fixed ranges replace drifting ones -----------------------------------------


@pytest.mark.parametrize("name", sorted(STAGE_FILES))
def test_stage_verifier_pins_its_boundary(name: str) -> None:
    module = _load(name)
    base, head = STAGE_FILES[name]
    assert module.STAGE_BASELINE == base, f"{name} baseline drifted"
    assert module.STAGE_HEAD == head, f"{name} stage head drifted"


@pytest.mark.parametrize("name", sorted(STAGE_FILES))
def test_registered_paths_equal_the_frozen_range(name: str) -> None:
    """The registry is the range: re-derived from Git, not asserted against itself."""
    module = _load(name)
    base, head = STAGE_FILES[name]
    actual = tuple(sorted(p for p in _git("diff", "--name-only", base, head).splitlines() if p))
    assert tuple(sorted(module.EXPECTED_STAGE_PATHS)) == actual


@pytest.mark.parametrize("name", sorted(STAGE_FILES))
@pytest.mark.parametrize("probe", ALL_PROBES)
def test_unregistered_probe_is_not_accepted_by_the_stage_scope(name: str, probe: str) -> None:
    """Exact-set logic: adding any probe makes the actual set differ from the registry."""
    registered = set(_load(name).EXPECTED_STAGE_PATHS)
    assert probe not in registered
    mutated = registered | {probe}
    assert mutated != registered, "an unregistered path must change the comparison outcome"
    assert sorted(mutated - registered) == [probe]


@pytest.mark.parametrize("name", sorted(RECORD_RANGES))
def test_record_range_is_frozen_at_both_ends(name: str) -> None:
    module = _load(name)
    base, head = RECORD_RANGES[name]
    assert module.MERGE_COMMIT == base
    assert module.RECORD_COMMIT == head


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_no_stage_scope_compares_against_head(rel: str) -> None:
    body = _read(REPO / rel)
    offenders = [
        m
        for m in re.findall(r'diff", "--name-only", [^)]*"HEAD"', body)
        if "RUNTIME_GUARD_ANCHOR" not in m
    ]
    assert offenders == [], f"{rel} still resolves a stage range against HEAD: {offenders}"


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_runtime_guard_still_scans_current_state(rel: str) -> None:
    """Freezing the scope must not freeze the denylist: a later runtime path must still fail."""
    body = _read(REPO / rel)
    assert "RUNTIME_GUARD_ANCHOR" in body, f"{rel} has no current-state runtime guard"
    assert re.search(r'"--name-only", RUNTIME_GUARD_ANCHOR, "HEAD"', body), rel


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_runtime_guard_covers_every_protected_prefix(rel: str) -> None:
    body = _read(REPO / rel)
    guard = body[body.index("RUNTIME_GUARD_ANCHOR") :]
    for prefix in RUNTIME_PREFIXES:
        assert f'"{prefix}"' in guard, f"{rel} runtime guard omits {prefix}"


def _acceptance_body(body: str) -> str:
    """Source with rejection contexts stripped, mirroring the RM1 verifier."""
    verifier = _load("verify_step66d_align1_rm1_fixed_range_remediation")
    return str(verifier.acceptance_body(body))


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
@pytest.mark.parametrize(
    "generic", ['"docs/",', '"scripts/verify_step66",', '"tests/test_step66",']
)
def test_generic_prefix_allowlists_are_gone(rel: str, generic: str) -> None:
    assert generic not in _acceptance_body(_read(REPO / rel)), f"{rel} still carries {generic}"


def test_the_stripping_helper_does_not_hide_a_real_allowlist() -> None:
    """Guard the guard: an actual acceptance tuple must still be visible after stripping."""
    real = 'allowed_prefixes = (\n    "docs/",\n)\nif path.startswith(allowed_prefixes):\n'
    assert '"docs/",' in _acceptance_body(real)
    rejection = 'FORBIDDEN = (\n    "docs/",\n)\n'
    assert '"docs/",' not in _acceptance_body(rejection)


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_no_equivalent_broad_glob_was_substituted(rel: str) -> None:
    body = _read(REPO / rel)
    for glob in ('"docs/**"', '"scripts/verify_step66*"', '"tests/test_step66*"', '"docs/*"'):
        assert glob not in body, f"{rel} substituted an equivalent broad glob {glob}"


# --- runtime denylist must survive --------------------------------------------------------------


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_runtime_denylist_still_present(rel: str) -> None:
    body = _read(REPO / rel)
    assert any(f'"{p}"' in body for p in RUNTIME_PREFIXES), f"{rel} lost its runtime denylist"


@pytest.mark.parametrize("name", sorted(STAGE_FILES))
def test_no_runtime_path_is_registered(name: str) -> None:
    registered = _load(name).EXPECTED_STAGE_PATHS
    assert [p for p in registered if p.startswith(RUNTIME_PREFIXES)] == []


# --- R1-F04: boundary-reset protection ----------------------------------------------------------


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_boundaries_are_literal_full_shas(rel: str) -> None:
    body = _read(REPO / rel)
    for const in ("STAGE_BASELINE", "STAGE_HEAD", "MERGE_COMMIT", "RECORD_COMMIT"):
        for value in re.findall(rf"^{const}\s*=\s*(.+)$", body, re.M):
            literal = value.strip().rstrip(",").strip()
            assert re.fullmatch(r'"[0-9a-f]{40}"', literal), f"{rel} {const} = {literal}"


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_boundaries_cannot_be_overridden_from_the_environment(rel: str) -> None:
    body = _read(REPO / rel)
    assert not re.search(r"os\.environ.*(STAGE_|MERGE_COMMIT|RECORD_COMMIT)", body)


@pytest.mark.parametrize("rel", CROSS_STAGE_FILES)
def test_boundary_is_never_a_branch_tip_or_symbolic_ref(rel: str) -> None:
    body = _read(REPO / rel)
    for const in ("STAGE_BASELINE", "STAGE_HEAD", "MERGE_COMMIT", "RECORD_COMMIT"):
        for value in re.findall(rf"^{const}\s*=\s*(.+)$", body, re.M):
            for forbidden in ("HEAD", "origin/", "rev-parse", "refs/", "ORIG_HEAD"):
                assert forbidden not in value, f"{rel} {const} resolves via {forbidden}"


def test_boundary_manifest_records_every_constant() -> None:
    """Changing a verifier constant alone must not be enough: the manifest has to agree."""
    manifest = _read(MANIFEST)
    for base, head in {**STAGE_FILES, **RECORD_RANGES}.values():
        assert base in manifest, f"baseline {base[:7]} missing from the boundary manifest"
        assert head in manifest, f"stage head {head[:7]} missing from the boundary manifest"


def test_manifest_names_a_boundary_authority_and_update_rule() -> None:
    manifest = _read(MANIFEST)
    for needle in ("boundary_authority:", "update_rule:", "forbidden_endpoints:", "sha_source:"):
        assert needle in manifest


def test_manifest_forbids_moving_endpoints() -> None:
    flat = re.sub(r"\s+", " ", _read(MANIFEST))
    assert "HEAD" in flat and "forbidden_endpoints" in flat
    assert "working tree" in flat


@pytest.mark.parametrize(
    "stage_id",
    [
        "step66sync1-claude-code-reconciliation",
        "step66sync1-final-partner-reconciliation",
        "step66sync1-m1-canonicalization",
        "step66sync1-m2-canonical-merge",
        "step66c4-be3-ra2m-canonicalization",
        "step66c4-be3-ra2m2-canonical-merge",
    ],
)
def test_every_stage_has_a_manifest_entry(stage_id: str) -> None:
    assert f"stage_id:                   {stage_id}" in _read(MANIFEST)


# --- ALIGN1 positive exact scope (R1-F01 for the newest stage) ----------------------------------


def test_align1_verifier_has_a_positive_scope_registry() -> None:
    module = _load("verify_step66d_align1_delivery_decision_model")
    assert len(module.ALIGN1_EXPECTED_PATHS) == 34
    assert hasattr(module, "check33_positive_exact_scope")


def test_align1_scope_equals_what_the_branch_actually_changed() -> None:
    module = _load("verify_step66d_align1_delivery_decision_model")
    changed = {p for p in _git("diff", "--name-only", CANONICAL_MAIN).splitlines() if p}
    assert changed == set(module.ALIGN1_EXPECTED_PATHS)


@pytest.mark.parametrize("probe", ALL_PROBES)
def test_align1_check33_rejects_an_unregistered_path(probe: str) -> None:
    """Real decision logic: feed check33 a mutated path set and require a recorded failure."""
    module = _load("verify_step66d_align1_delivery_decision_model")
    mutated = list(module.ALIGN1_EXPECTED_PATHS) + [probe]
    module.git = lambda *args: "\n".join(mutated)  # type: ignore[attr-defined]
    module.FAILURES.clear()
    module.check33_positive_exact_scope()
    assert module.FAILURES, f"check33 accepted the unregistered path {probe}"
    assert probe in " ".join(module.FAILURES)


def test_align1_check33_rejects_a_disappearing_registered_path() -> None:
    module = _load("verify_step66d_align1_delivery_decision_model")
    mutated = list(module.ALIGN1_EXPECTED_PATHS)[:-1]
    module.git = lambda *args: "\n".join(mutated)  # type: ignore[attr-defined]
    module.FAILURES.clear()
    module.check33_positive_exact_scope()
    assert module.FAILURES, "check33 accepted a registry entry vanishing"


def test_align1_check33_accepts_the_registered_set() -> None:
    module = _load("verify_step66d_align1_delivery_decision_model")
    module.git = lambda *a: "\n".join(module.ALIGN1_EXPECTED_PATHS)  # type: ignore[attr-defined]
    module.FAILURES.clear()
    module.check33_positive_exact_scope()
    assert module.FAILURES == []


# --- R1-F05: accuracy corrections ---------------------------------------------------------------


def test_cross_stage_file_count_is_twelve() -> None:
    assert len(CROSS_STAGE_FILES) == 12
    assert len([p for p in CROSS_STAGE_FILES if p.startswith("scripts/")]) == 6
    assert len([p for p in CROSS_STAGE_FILES if p.startswith("tests/")]) == 6


def test_every_cross_stage_file_actually_differs_from_canonical_main() -> None:
    changed = {p for p in _git("diff", "--name-only", CANONICAL_MAIN).splitlines() if p}
    for rel in CROSS_STAGE_FILES:
        assert rel in changed, f"{rel} is claimed as modified but is not"


def test_previously_omitted_file_is_disclosed() -> None:
    evidence = _read(RM1_EVIDENCE)
    assert "tests/test_step66c4_be3_ra2m2_canonical_merge.py" in evidence
    assert "11" in evidence and "12" in evidence


def test_align1_evidence_corrects_the_counts_without_hiding_them() -> None:
    evidence = _read(ALIGN1_EVIDENCE)
    assert "552" in evidence, "the original erroneous figure must stay visible"
    assert "553" in evidence, "the correction must be present"
    assert "CORRECTION" in evidence


def test_original_commit_message_is_not_rewritten() -> None:
    """History stands; corrections live in current records only."""
    message = subprocess.run(
        ["git", "log", "-1", "--format=%B", ALIGN1_COMMIT],
        cwd=REPO,
        stdout=subprocess.PIPE,
        check=False,
    ).stdout.decode("utf-8")
    assert "552" in message, "the historical commit message must not be rewritten"


def test_align1_commit_is_still_an_ancestor() -> None:
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ALIGN1_COMMIT, "HEAD"], cwd=REPO, check=False
    )
    assert rc.returncode == 0, "the original ALIGN1 commit was rebased, amended or squashed away"


def test_at_most_one_remediation_commit() -> None:
    count = _git("rev-list", "--count", f"{ALIGN1_COMMIT}..HEAD")
    assert count.isdigit() and int(count) <= 1, f"expected at most one RM1 commit, found {count}"


# --- historical provenance guard must not have been weakened ------------------------------------


def test_m1_append_only_provenance_guard_intact() -> None:
    m1 = _read(SCRIPTS / "verify_step66sync1_m1_canonicalization.py")
    for needle in (
        "ANNOTATED",
        "ANNOTATION_MARKER",
        "git_blob_text",
        "content above the annotation marker was modified",
        "must be additive",
        "OPEN_PRODUCT_OWNER_DECISIONS",
    ):
        assert needle in m1, f"the M1 provenance guard lost {needle!r}"


def test_annotated_files_still_preserve_their_source_prefix() -> None:
    module = _load("verify_step66sync1_m1_canonicalization")
    for commit, paths in module.ANNOTATED.items():
        for rel in paths:
            original = module.git_blob_text(commit, rel)
            current = (REPO / rel).read_text(encoding="utf-8")
            assert original, rel
            assert module.ANNOTATION_MARKER in current, rel
            head = current.partition(module.ANNOTATION_MARKER)[0]
            assert module._norm(head) == module._norm(original), f"{rel} preserved prefix changed"


def test_66d_decisions_untouched_by_this_remediation() -> None:
    for rel in (
        "docs/contracts/66d-delivery-acceptance/"
        "step66d-delivery-decision-model-binding-decisions.md",
        "docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md",
        "docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md",
    ):
        assert _git("diff", "--name-only", ALIGN1_COMMIT, "--", rel) == "", rel


# --- authorization posture ----------------------------------------------------------------------


def test_rm1_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_step66d_align1_rm1_fixed_range_remediation.py")],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert "STEP66D_ALIGN1_RM1_FIXED_RANGE_REMEDIATION_VERIFY: PASS" in result.stdout.decode()


def test_no_runtime_or_infra_path_changed() -> None:
    changed = [p for p in _git("diff", "--name-only", CANONICAL_MAIN).splitlines() if p]
    assert [p for p in changed if p.startswith(RUNTIME_PREFIXES)] == []
    assert [p for p in changed if p.endswith((".yaml", ".yml", ".tsx", ".ts", ".sql"))] == []


def test_merge_and_arch1_remain_unauthorized() -> None:
    evidence = re.sub(r"\s+", " ", _read(RM1_EVIDENCE))
    assert "MERGE AUTHORIZATION: NOT GRANTED" in evidence
    assert "NOT AUTHORIZED" in evidence
    assert "production_executed_true_count: 0" in evidence
    for claim in ("ready to merge", "R2 passed", "independent review passed"):
        assert claim.lower() not in evidence.lower()
