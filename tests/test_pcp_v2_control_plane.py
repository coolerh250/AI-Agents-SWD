"""PCP-v2 control plane -- drift gate, self-consistency invariants, contradiction fixtures.

The fixtures are the point. A drift gate that has only ever been shown to agree with a correct
snapshot is not evidence; each fixture below states a specific way a snapshot can be wrong and
asserts the gate refuses it.

No fixture mutates canonical project state. Each writes a temporary copy and points the verifier
at it with --pm-state.

Read-only with respect to the repository. Starts no runtime, container, database or provider.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_pcp_v2_control_plane.py"

PM_STATE = ROOT / "docs" / "governance" / "AI_AGENTS_PM_STATE.md"
CONTRACT = ROOT / "docs" / "governance" / "project-control-plane-v2.md"
RECOVERY = ROOT / "docs" / "governance" / "pcp-v2-recovery.md"


def snapshot_main() -> str:
    """Read from the snapshot, never pinned to a constant: the value legitimately moves."""
    return module().pm_state_fields()["RECONCILED_AGAINST_MAIN"]


AT_M1_STAGE_HEAD = "c80350ecc19e28212d9a95cddeb80a24aabe6eae"
AT_M1_MERGE_COMMIT = "db4e7a781dcddf4f5ab4ac413457a88bc7bdefa0"
PR28_HEAD = "c9145cd848a211a9dd2bbff672c532da364eaa55"


def module():
    spec = importlib.util.spec_from_file_location("pcp_v2_verifier", VERIFIER)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def run_verifier(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def fixture_from(tmp_path: Path, name: str, *replacements: tuple[str, str]) -> Path:
    """A temporary PM-state copy with one deliberate contradiction applied."""
    text = PM_STATE.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, f"fixture anchor missing: {old!r}"
        text = text.replace(old, new, 1)
    assert text != PM_STATE.read_text(encoding="utf-8"), f"fixture {name} changed nothing"
    path = tmp_path / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


# =================================================================================================
# 1. Artifacts and the canonical control
# =================================================================================================


def test_pcp_governance_artifacts_exist():
    for path in (PM_STATE, CONTRACT, RECOVERY, VERIFIER):
        assert path.is_file(), path


def test_pcp_canonical_snapshot_passes_the_gate():
    """The control. Every rejection below is worthless without it."""
    result = run_verifier()
    assert result.returncode == 0, result.stdout
    assert "PCP_V2_CONTROL_PLANE_VERIFY: PASS" in result.stdout


def test_pcp_canonical_truth_is_read_from_the_repository_not_hard_coded():
    """A gate carrying its own copy of the truth would agree with itself while both drifted."""
    truth = module().canonical_truth()
    for field in ("AT-D09", "AT-D10", "AT-D10.1", "AT_M2", "AT_M1", "PR29"):
        assert truth[field], f"{field} was not derived from a canonical artifact"
    source = VERIFIER.read_text(encoding="utf-8")
    assert snapshot_main() not in source, "the canonical main SHA is hard-coded into the gate"
    assert AT_M1_MERGE_COMMIT not in source, "the merge commit is hard-coded into the gate"


def test_pcp_snapshot_is_versioned_and_reconcilable():
    fields = module().pm_state_fields()
    assert fields["PM_STATE_VERSION"] == "1"
    assert fields["PM_STATE_SCHEMA"] == "pcp-v2"
    recorded = fields["RECONCILED_AGAINST_MAIN"]
    loaded = module()
    assert loaded.commit_exists(recorded), recorded
    assert loaded.is_ancestor(recorded, loaded.canonical_main()), recorded
    assert fields["AT_M1_STAGE_HEAD"] == AT_M1_STAGE_HEAD
    assert fields["AT_M1_MERGE_COMMIT"] == AT_M1_MERGE_COMMIT


# =================================================================================================
# 2. Staleness is not drift
# =================================================================================================


def test_pcp_staleness_is_tolerated_and_reported():
    """A snapshot records when it was reconciled; falling behind must not be a failure."""
    loaded = module()
    fields = loaded.pm_state_fields()
    behind = loaded.staleness(fields, loaded.canonical_truth())
    assert behind >= 0, "the recorded main is not an ancestor of current main"
    assert loaded.drift_conflicts(fields, loaded.canonical_truth()) == []


def test_pcp_an_ancestor_main_is_stale_while_an_unrelated_commit_is_drift():
    loaded = module()
    truth = loaded.canonical_truth()
    stale = dict(loaded.pm_state_fields(), RECONCILED_AGAINST_MAIN=AT_M1_MERGE_COMMIT)
    assert loaded.drift_conflicts(stale, truth) == [], "an ancestor main must read as stale"
    assert loaded.staleness(stale, truth) >= 0

    drifted = dict(loaded.pm_state_fields(), RECONCILED_AGAINST_MAIN=PR28_HEAD)
    conflicts = loaded.drift_conflicts(drifted, truth)
    assert any("not an ancestor" in c for c in conflicts), conflicts


# =================================================================================================
# 3. Contradiction fixtures C1..C7 -- end to end through the verifier
# =================================================================================================


CONTRADICTIONS = [
    (
        "C1_pr29_open",
        [("PR29:                        MERGED", "PR29:                        OPEN")],
    ),
    # Rewritten at AT-M2-TEAM-CORE. AT-M2 is now genuinely authorized, so "the snapshot says
    # AUTHORIZED" is no longer a contradiction. The contradiction it was protecting against
    # survives in a sharper form: authorization CLAIMED but not backed by the canonical Product
    # Owner decision. A snapshot must never be able to authorize a milestone by itself.
    (
        "C2_at_m2_authorized_without_a_decision_record",
        [
            (
                "AT_M2_AUTHORIZED_BY:         AT-D11 / docs/decisions/at-m2-authorization.md",
                "AT_M2_AUTHORIZED_BY:         (unrecorded)",
            )
        ],
    ),
    (
        "C3_hold_artifact_as_dependency",
        [
            (
                "PR28_HOLD:                   HOLD / PRESERVE / NON-CANONICAL, future AT-M7 input",
                "PR28_HOLD:                   HOLD / CANONICAL DEPENDENCY OF AT-M2",
            )
        ],
    ),
    (
        "C4_at_d09_resolved",
        [
            (
                "AT-D09:                      OPEN / DEFERRED",
                "AT-D09:                      RESOLVED / BINDING",
            )
        ],
    ),
    (
        "C5_wrong_canonical_main",
        [
            (
                "RECONCILED_AGAINST_MAIN:     ",
                f"RECONCILED_AGAINST_MAIN:     {PR28_HEAD}  # was ",
            )
        ],
    ),
    (
        "C6_production_executed",
        [("PRODUCTION_EXECUTED_TRUE_COUNT: 0", "PRODUCTION_EXECUTED_TRUE_COUNT: 3")],
    ),
    (
        "C7_at_m1_not_canonical",
        [
            (
                "AT_M1:                       CLOSED / CANONICAL",
                "AT_M1:                       OPEN / NOT CANONICAL",
            )
        ],
    ),
]


@pytest.mark.parametrize("name,replacements", CONTRADICTIONS, ids=[c[0] for c in CONTRADICTIONS])
def test_pcp_contradiction_fixture_is_rejected(tmp_path, name, replacements):
    fixture = fixture_from(tmp_path, name, *replacements)
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0, f"{name} was accepted:\n{result.stdout}"
    assert "PM_STATE_CONFLICT" in result.stdout or "[INVARIANT]" in result.stdout, result.stdout
    assert "PCP_V2_CONTROL_PLANE_VERIFY: FAIL" in result.stdout


def test_pcp_every_contradiction_class_is_covered():
    assert len(CONTRADICTIONS) == 7
    assert {name.split("_")[0] for name, _ in CONTRADICTIONS} == {f"C{n}" for n in range(1, 8)}


def test_pcp_a_fixture_that_changes_nothing_still_passes(tmp_path):
    """Anti-vacuity: the fixture mechanism itself must not be what causes rejection."""
    path = tmp_path / "untouched.md"
    path.write_text(PM_STATE.read_text(encoding="utf-8"), encoding="utf-8")
    result = run_verifier("--pm-state", str(path))
    assert result.returncode == 0, result.stdout


# =================================================================================================
# 4. Self-consistency invariants I1..I7
# =================================================================================================


def base_fields():
    return dict(module().pm_state_fields())


def test_i1_a_not_authorized_stage_cannot_be_the_current_position():
    """AT-M2-TEAM-CORE: both halves are now stated explicitly.

    The test used to lean on AT_M2 happening to be NOT AUTHORIZED in the live snapshot. It is
    authorized now, so the fixture sets the unauthorized state itself -- which is what the
    invariant is actually about, and makes the test independent of the current position.
    """
    loaded = module()
    fields = base_fields()
    fields["AT_M2"] = "NOT AUTHORIZED"
    fields["CURRENT_MILESTONE"] = "AT_M2"
    assert any(v.startswith("I1:") for v in loaded.invariant_violations(fields))

    fields["AT_M2"] = "AUTHORIZED / IN PROGRESS"
    assert not any(v.startswith("I1:") for v in loaded.invariant_violations(fields))


def test_i2_a_hold_artifact_cannot_be_a_canonical_dependency():
    loaded = module()
    fields = base_fields()
    fields["PR28_HOLD"] = "HOLD / CANONICAL DEPENDENCY OF AT-M2"
    violations = loaded.invariant_violations(fields)
    assert any(v.startswith("I2:") for v in violations), violations


def test_i3_an_open_decision_cannot_also_be_binding():
    loaded = module()
    fields = base_fields()
    fields["AT-D09"] = "OPEN / DEFERRED / BINDING"
    assert any(v.startswith("I3:") for v in loaded.invariant_violations(fields))


def test_i4_production_execution_requires_authorization():
    loaded = module()
    fields = base_fields()
    fields["PRODUCTION_EXECUTED_TRUE_COUNT"] = "1"
    assert any(v.startswith("I4:") for v in loaded.invariant_violations(fields))


def test_i5_a_merged_pr_must_be_ancestry_reconcilable():
    loaded = module()
    fields = base_fields()
    fields["AT_M1_MERGE_COMMIT"] = PR28_HEAD
    assert any(v.startswith("I5:") for v in loaded.invariant_violations(fields))


def test_i6_a_canonical_milestone_needs_ancestry():
    loaded = module()
    fields = base_fields()
    fields["AT_M1_STAGE_HEAD"] = PR28_HEAD
    assert any(v.startswith("I6:") for v in loaded.invariant_violations(fields))


def test_i7_at_m2_requires_the_gate_to_have_passed_or_a_recorded_re_sequencing():
    """AT-D11 moved the PCP-V2.1 gate to production authorization. I7 now has two legal roads.

    The important half is the third case: a snapshot that claims authorization without naming the
    canonical decision is still rejected, so nothing can authorize a milestone by editing one
    field. The rule was re-sequenced; it was not removed.
    """
    loaded = module()
    fields = base_fields()
    fields["AT_M2"] = "AUTHORIZED"

    # Road 1 -- the gate itself passed.
    passed = {**fields, "PCP_V2_1": "PASS", "AT_M2_AUTHORIZED_BY": "", "PCP_V2_1_GATES": ""}
    assert not any(v.startswith("I7:") for v in loaded.invariant_violations(passed))

    # Road 2 -- the gate is still open, but a canonical decision re-sequenced it.
    assert loaded.at_m2_authorization_is_recorded(fields)
    assert not any(v.startswith("I7:") for v in loaded.invariant_violations(fields))

    # Neither -- authorization claimed with nothing behind it. Still a violation.
    for missing in ("AT_M2_AUTHORIZED_BY", "PCP_V2_1_GATES"):
        unbacked = {**fields, missing: ""}
        assert not loaded.at_m2_authorization_is_recorded(unbacked), missing
        assert any(v.startswith("I7:") for v in loaded.invariant_violations(unbacked)), missing


def test_the_canonical_snapshot_violates_no_invariant():
    assert module().invariant_violations(base_fields()) == []


# =================================================================================================
# 5. Contract, recovery packet and acceptance specification
# =================================================================================================


def test_pcp_contract_documents_the_source_of_truth_hierarchy():
    text = CONTRACT.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    assert "engineering source of truth" in flat
    assert "derived project-control truth" in flat
    assert "conversation history" in flat and "never required" in flat
    for concept in ("G1", "G2", "G3", "repair window", "Stage capsule", "Delta prompt"):
        assert concept.lower() in flat.lower(), concept


def test_pcp_contract_defines_the_root_defect_specification_shape():
    flat = re.sub(r"\s+", " ", CONTRACT.read_text(encoding="utf-8"))
    for field in (
        "INVARIANT",
        "DOMAIN",
        "KNOWN INSTANCES",
        "ADVERSARY MODEL",
        "POSITIVE CONTROLS",
        "CLOSURE PROOF",
        "RISK GATE",
    ):
        assert field in flat, field
    assert "NON-EXHAUSTIVE" in flat


def test_pcp_memory_boundary_names_volatile_facts_explicitly():
    flat = re.sub(r"\s+", " ", CONTRACT.read_text(encoding="utf-8")).lower()
    for volatile in ("canonical sha", "count", "pull-request state", "current stage"):
        assert volatile in flat, volatile
    assert "must not** be the sole authority" in flat


def test_pcp_recovery_packet_needs_no_conversation_history():
    flat = re.sub(r"\s+", " ", RECOVERY.read_text(encoding="utf-8"))
    assert "RECOVERY PACKET" in flat
    assert "no prior conversation context" in flat
    assert "No transcript, no prior stage reports, no assistant memory" in flat


def test_pcp_recovery_packet_lists_every_recoverable_field():
    flat = re.sub(r"\s+", " ", RECOVERY.read_text(encoding="utf-8")).lower()
    for field in (
        "canonical main",
        "current milestone",
        "last completed stage",
        "current required gate",
        "binding product owner decisions",
        "hold items",
        "safety state",
        "transition hazard",
        "source-of-truth precedence",
    ):
        assert field in flat, field


def test_pcp_acceptance_spec_requires_a_fresh_session_and_blocks_on_contradiction():
    flat = re.sub(r"\s+", " ", RECOVERY.read_text(encoding="utf-8"))
    assert "genuinely fresh independent session" in flat
    assert "exact semantic agreement" in flat
    assert "silently accepts the stale packet FAILS" in flat
    assert "do NOT proceed to AT-M2" in flat


def test_pcp_stage_makes_no_acceptance_claim():
    flat = re.sub(r"\s+", " ", RECOVERY.read_text(encoding="utf-8"))
    assert "cannot conclude PCP-V2.1 PASS" in flat
    assert "AT-M2 remains NOT AUTHORIZED" in flat


# =================================================================================================
# 6. Forward transition hazard is recorded, not pre-emptively resolved
# =================================================================================================


def test_pcp_at_m1_denylist_hazard_is_recorded_without_being_changed():
    fields = module().pm_state_fields()
    assert "DISPOSITION REQUIRED" in fields["HAZARD_AT_M1_DENYLIST"].upper()
    flat = re.sub(r"\s+", " ", PM_STATE.read_text(encoding="utf-8"))
    assert "not authorization to weaken AT-M1" in flat


def test_pcp_at_m1_head_relative_denylists_are_untouched():
    """This stage must not weaken AT-M1's live rejection logic to make room for itself."""
    at_m1 = (ROOT / "scripts" / "verify_at_m1_architecture_reset.py").read_text(encoding="utf-8")
    assert "offenders = forbidden_scope_offenders(head_changed)" in at_m1
    assert "breached = protected_breaches(head_changed)" in at_m1
    assert '"source/progress.md" not in head_changed' in at_m1


def test_pcp_governance_paths_do_not_cross_an_at_m1_denylist():
    """The reason this stage can add paths at all: none of them is on AT-M1's forbidden list."""
    at_m1 = importlib.util.spec_from_file_location(
        "at_m1", ROOT / "scripts" / "verify_at_m1_architecture_reset.py"
    )
    loaded = importlib.util.module_from_spec(at_m1)
    at_m1.loader.exec_module(loaded)
    added = {
        "docs/governance/AI_AGENTS_PM_STATE.md",
        "docs/governance/project-control-plane-v2.md",
        "docs/governance/pcp-v2-recovery.md",
        "scripts/verify_pcp_v2_control_plane.py",
        "tests/test_pcp_v2_control_plane.py",
    }
    assert loaded.forbidden_scope_offenders(added) == []
    assert loaded.protected_breaches(added) == []


# =================================================================================================
# 7. Measured debt reconciliation (Step PCP-V2.1-RM1)
#
# DEF-PCPB-01: two governance verifiers were failing on canonical main while the snapshot said
# BLOCKERS: NONE, and the failures hid behind ADV-R4-01 because they shared its verifier family.
# Debt classified by family cannot tell a known failure from a new one standing next to it.
# =================================================================================================


ADV_R4_01 = (
    "test:tests/test_step66d_align1_rm1_fixed_range_remediation.py"
    "::test_66d_decisions_untouched_by_this_remediation",
    "test:tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_rm1_verifier_passes",
)


def test_rm1_applicable_governance_set_is_derived_not_nominated():
    """PCP-V2.1-A hand-picked four sentinels and missed the guard that failed."""
    loaded = module()
    applicable = loaded.applicable_governance_verifiers()
    assert len(applicable) > 20, "the applicable set looks hand-picked"
    for required in (
        "scripts/verify_step66d_align1_delivery_decision_model.py",
        "scripts/verify_at_m1_gov1_stage_family_compatibility.py",
        "scripts/verify_at_m1_gov1_m1_canonical_merge.py",
        "scripts/verify_at_m1_architecture_reset.py",
    ):
        assert required in applicable, f"{required} escaped the applicable set"
    assert "scripts/verify_pcp_v2_control_plane.py" not in applicable, "self-measurement"
    source = VERIFIER.read_text(encoding="utf-8")
    assert "repository_state_dependent" in source and "glob" in source, "not derived structurally"


def test_rm1_registered_debt_is_read_from_the_pm_state():
    registered = module().registered_debt_ids(PM_STATE.read_text(encoding="utf-8"))
    assert len(registered) >= 10
    for known in ADV_R4_01:
        assert known in registered


def test_rm1_a_new_failure_cannot_hide_behind_debt_in_the_same_family():
    """THE camouflage probe. Two registered failures plus one new one in the SAME module."""
    loaded = module()
    registered = loaded.registered_debt_ids(PM_STATE.read_text(encoding="utf-8"))
    intruder = (
        "test:tests/test_step66d_align1_rm1_fixed_range_remediation.py"
        "::test_a_brand_new_failure_in_the_same_module"
    )
    measured = [*ADV_R4_01, intruder]
    new = loaded.new_unregistered_failures(measured, registered)
    assert new == [intruder], f"the intruder was camouflaged by its family: {new}"


def test_rm1_the_exact_registered_pair_alone_raises_nothing():
    """The control. Without it the probe above would pass on a blanket-reject rule."""
    loaded = module()
    registered = loaded.registered_debt_ids(PM_STATE.read_text(encoding="utf-8"))
    assert loaded.new_unregistered_failures(list(ADV_R4_01), registered) == []


def test_rm1_a_new_verifier_failure_in_a_registered_family_is_new():
    loaded = module()
    registered = loaded.registered_debt_ids(PM_STATE.read_text(encoding="utf-8"))
    sibling = "verifier:verify_step66c4_be3_z_something_else.py"
    assert loaded.new_unregistered_failures([sibling], registered) == [sibling]


def test_rm1_debt_identity_is_exact_not_family_shaped():
    """A family prefix must never be accepted as a debt identity."""
    loaded = module()
    registered = loaded.registered_debt_ids(PM_STATE.read_text(encoding="utf-8"))
    assert not any(entry.endswith(("*", "/", "::")) for entry in registered)
    assert all(":" in entry for entry in registered)


def test_rm1_blockers_none_is_a_measured_claim_not_an_assertion():
    flat = re.sub(r"\s+", " ", PM_STATE.read_text(encoding="utf-8"))
    assert "is a **measured** claim" in flat
    assert "not an assertion that nobody noticed one" in flat
    assert "GOVERNANCE_REGRESSION" in flat


def test_rm1_stale_measurement_invalidates_the_blockers_claim(tmp_path):
    """A measurement that no longer describes current authority inputs must not stand."""
    recorded = module().pm_state_fields()["GOVERNANCE_INPUT_DIGEST"]
    fixture = fixture_from(
        tmp_path,
        "stale_measurement",
        (f"GOVERNANCE_INPUT_DIGEST:     {recorded}", "GOVERNANCE_INPUT_DIGEST:     " + "0" * 64),
    )
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0, result.stdout
    assert "stale" in result.stdout


def test_rm1_governance_admission_is_by_domain_not_family():
    """The PCP paths must be admitted by the same rule an unseen family would use."""
    spec = importlib.util.spec_from_file_location(
        "align1", ROOT / "scripts" / "verify_step66d_align1_delivery_decision_model.py"
    )
    align1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(align1)
    assert not hasattr(align1, "REGISTERED_GOVERNANCE_FAMILIES")
    for path in (
        "scripts/verify_pcp_v2_control_plane.py",
        "tests/test_pcp_v2_control_plane.py",
        "scripts/verify_zzz_family_nobody_has_invented_yet.py",
        "tests/test_zzz_family_nobody_has_invented_yet.py",
    ):
        assert align1.is_admitted_current_state_path(path), path
    for path in ("scripts/at_runtime_patch.py", "agents/x/src/a.py", "migrations/9.sql"):
        assert not align1.is_admitted_current_state_path(path), path


# =================================================================================================
# 8. Semantic applicability and bidirectional debt (Step PCP-V2.1-RM2)
#
# B-1: applicability was a regex for the literal token HEAD, so a verifier spelling the same live
# reference "origin/main" was invisible. The rule must not care which word is used.
# =================================================================================================


LIVE_REF_SHAPES = {
    "head": '["git", "diff", "--name-only", "abc123...HEAD"]',
    "origin_main": '["git", "diff", "--name-only", "origin/main"]',
    "indirect_variable": 'REF = compute_ref()\nsubprocess.run(["git", "diff", REF])',
    "default_branch_helper": 'b = default_branch()\nsubprocess.run(["git", "log", b])',
    "fstring_range": 'BASE = "x"\nsubprocess.run(["git", "diff", f"{BASE}...{tip()}"])',
    "unseen_expression": 'subprocess.run(["git", "rev-list", resolve_upstream(cfg)[0]])',
    "wrapper_indirection": (
        "def git(*args):\n    return subprocess.run(['git', *args])\n\n"
        "def check():\n    return git('diff', '--name-only', upstream_ref())"
    ),
}


@pytest.mark.parametrize("shape", sorted(LIVE_REF_SHAPES), ids=sorted(LIVE_REF_SHAPES))
def test_rm2_every_live_reference_spelling_is_applicable(shape):
    """No ref spelling is consulted, so an unseen one cannot escape."""
    loaded = module()
    applicable, reason = loaded.repository_state_dependent(LIVE_REF_SHAPES[shape])
    assert applicable, f"{shape} escaped the applicable set: {reason}"


def test_rm2_the_classifier_reads_no_reference_token_list():
    """The B-1 recurrence guard: a ref spelling inside the classifier means it is a list again."""
    source = VERIFIER.read_text(encoding="utf-8")
    classifier = source.split("def repository_state_dependent")[1].split("\ndef ")[0]
    for spelling in ("HEAD", "origin/main", "master", "default_branch", "upstream", '"git"'):
        assert spelling not in classifier, f"the classifier consults the spelling {spelling!r}"


def test_rm3_vocabulary_decides_membership_in_neither_direction():
    """RM3 inverted the default: applicable unless external dependency is PROVEN.

    The RM2 form of this test asserted the module below was EXCLUDED. Under RM3 it is included,
    for a structural reason rather than a lexical one -- it reads repository files, and those
    advance. Vocabulary still decides nothing, and now it cannot cause an omission either.
    """
    loaded = module()
    vocabulary_only = (
        '"""Compares docs. HEAD, origin/main and default_branch appear only here."""\n'
        'AT_M1_STAGE_HEAD = "c80350e"\n'
        "def check():\n    return open('docs/x.md').read()\n"
    )
    applicable, reason = loaded.repository_state_dependent(vocabulary_only)
    assert applicable, reason
    assert "reading repository state" in reason
    assert loaded.environment_dependent(vocabulary_only) == (False, "")


def test_rm3_uncertainty_fails_closed_into_the_set():
    loaded = module()
    applicable, _ = loaded.repository_state_dependent("def broken(:\n")
    assert applicable, "an unparseable module must be measured, not omitted"


def test_rm3_a_path_string_naming_a_tool_is_not_an_invocation():
    """The false-exclusion guard: reading 'helm' as an invocation dropped a registered identity."""
    loaded = module()
    assert loaded.environment_dependent('FORBIDDEN = ("helm/", "k8s/")') == (False, "")
    assert loaded.environment_dependent('subprocess.run(["helm", "template", "."])')[0]
    assert loaded.environment_dependent("import requests")[0]


def test_rm2_applicability_is_not_a_hand_maintained_list():
    loaded = module()
    verifiers = loaded.applicable_governance_verifiers()
    assert len(verifiers) > 40, "the applicable set looks nominated"
    for required in (
        "scripts/verify_step66c4_be1_data_model_deadline_outbox.py",
        "scripts/verify_step66d_align1_delivery_decision_model.py",
        "scripts/verify_at_m1_gov1_stage_family_compatibility.py",
        "scripts/verify_at_m1_architecture_reset.py",
    ):
        assert required in verifiers, f"{required} escaped the applicable set"
    assert "scripts/verify_pcp_v2_control_plane.py" not in verifiers
    assert loaded.GOVERNANCE_ARTIFACT.match("agents/verify_thing.py") is None
    assert loaded.GOVERNANCE_ARTIFACT.match("scripts/nested/verify_thing.py") is None


# --- the governance TEST domain (A-3) -----------------------------------------------------------


def test_rm2_the_governance_test_domain_is_derived_and_non_empty():
    loaded = module()
    tests = loaded.applicable_governance_tests()
    assert len(tests) > 20, "the governance test domain looks hand-picked"
    assert "tests/test_step66d_align1_rm1_fixed_range_remediation.py" in tests
    assert all(t.startswith("tests/test_") for t in tests)
    assert "tests/test_alert_receiver_auth.py" not in tests


def test_rm2_a_test_identity_can_actually_be_measured():
    """A registered test: identity that could never be measured was the A-3 hole."""
    source = VERIFIER.read_text(encoding="utf-8")
    measured = source.split("def _measure_tree")[1].split("\ndef ")[0]
    assert "domains_at(tree)" in measured
    assert "test:" in measured
    active, _ = module().debt_sections(PM_STATE.read_text(encoding="utf-8"))
    assert any(entry.startswith("test:") for entry in active)


# --- bidirectional reconciliation (A-4) ---------------------------------------------------------


def active_debt():
    return module().debt_sections(PM_STATE.read_text(encoding="utf-8"))[0]


def test_rm2_under_registration_is_a_regression():
    loaded = module()
    registered = active_debt()
    known = sorted(e for e in registered if "align1_rm1_fixed_range" in e)
    assert len(known) >= 2, known
    intruder = (
        "test:tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_brand_new_failure"
    )
    assert loaded.new_unregistered_failures([*known, intruder], registered) == [intruder]
    assert loaded.new_unregistered_failures(known, registered) == []


def test_rm2_over_registration_is_detected():
    """A-4: an ACTIVE identity that no longer fails must be retired, not retained."""
    loaded = module()
    registered = active_debt()
    measured = sorted(registered)[1:]
    stale = loaded.overregistered_active_debt(measured, registered)
    assert stale == [sorted(registered)[0]], stale
    assert loaded.overregistered_active_debt(sorted(registered), registered) == []


def test_rm2_historical_debt_exempts_nothing():
    """An identity parked as historical must not pre-absolve its own re-failure."""
    loaded = module()
    identity = "verifier:verify_step66c4_be3_planning.py"
    doc = PM_STATE.read_text(encoding="utf-8").replace(f"- {identity}\n", "", 1)
    doc = doc.replace(
        loaded.HISTORICAL_DEBT_HEADING,
        f"{loaded.HISTORICAL_DEBT_HEADING}\n\n- {identity}",
        1,
    )
    active, historical = loaded.debt_sections(doc)
    assert identity in historical and identity not in active
    assert loaded.new_unregistered_failures([identity], active) == [identity]


def test_rm2_active_and_historical_are_separate_authorities():
    loaded = module()
    source = VERIFIER.read_text(encoding="utf-8")
    assert "def debt_sections" in source
    assert "Only ACTIVE debt participates" in source
    active, historical = loaded.debt_sections(PM_STATE.read_text(encoding="utf-8"))
    assert active and not (active & historical)


def test_rm2_every_active_identity_is_baseline_backed_and_open():
    flat = re.sub(r"\s+", " ", PM_STATE.read_text(encoding="utf-8"))
    assert "measured failing at `GOVERNANCE_DEBT_BASELINE`" in flat
    assert "None of them is fixed by being listed" in flat
    assert "an entry here exempts nothing" in flat


def test_rm2_the_reconciliation_note_is_conditional():
    """A-7: the note previously said 'all registered' even on runs reporting regressions."""
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'if reconciled else "NOT reconciled"' in source


def test_rm2_no_applicable_count_is_encoded_as_correctness():
    """The count legitimately moves when governance files change."""
    source = VERIFIER.read_text(encoding="utf-8")
    for count in ("== 47", "== 63", "== 25"):
        assert count not in source, f"an expected count {count} is encoded as correctness"


# =================================================================================================
# 9. Fail-closed applicability, freshness provenance, recovery and PM provenance (PCP-V2.1-RM3)
#
# A1: RM2 classified by COMMAND FORM, so a shell string, a constructed binary name, os.system and
#     a wrapper all escaped. RM3 stops asking: applicable is the default, exclusion needs proof.
# =================================================================================================


COMMAND_FORMS = {
    "subprocess_list": 'subprocess.run(["git", "diff", "--name-only", "HEAD"])',
    "shell_string": 'subprocess.run("git diff --name-only origin/main", shell=True)',
    "split_binary": 'B = "g" + "it"\nsubprocess.run([B, "status"])',
    "constructed_argv": 'CMD = ["gi" + "t", "rev-parse"]\nsubprocess.run(CMD)',
    "os_system": 'import os\nos.system("git rev-parse HEAD")',
    "wrapper_helper": (
        "def run(*a):\n    return subprocess.run(list(a))\n\ndef check():\n"
        "    return run('git', 'log', upstream())"
    ),
    "unseen_form": 'runner.exec_(["git", "for-each-ref", "--sort=-committerdate"])',
    "worktree_read_only": 'open("docs/governance/AI_AGENTS_PM_STATE.md").read()',
    "pathlib_read_only": 'pathlib.Path("docs/x.md").read_text()',
    "no_io_at_all": "VALUE = 1\n\ndef add(a, b):\n    return a + b\n",
}


@pytest.mark.parametrize("form", sorted(COMMAND_FORMS), ids=sorted(COMMAND_FORMS))
def test_rm3_no_command_form_can_escape_applicability(form):
    """A1: every one of these is applicable, including the three that escaped RM2 and the two
    that never touch a process at all."""
    loaded = module()
    applicable, reason = loaded.repository_state_dependent(COMMAND_FORMS[form])
    assert applicable, f"{form} escaped: {reason}"


def test_rm3_only_a_proven_external_dependency_excludes():
    loaded = module()
    for external in ("import requests", "from urllib import request", "import socket"):
        assert loaded.repository_state_dependent(external)[0] is False, external
    for tool in (
        'subprocess.run(["docker", "ps"])',
        'subprocess.run("kubectl get pods", shell=True)',
    ):
        assert loaded.repository_state_dependent(tool)[0] is False, tool


def test_rm3_exclusions_are_reported_not_silent():
    """An exclusion nobody can see is indistinguishable from a gap."""
    loaded = module()
    excluded = loaded.excluded_environment_verifiers()
    assert excluded, "no exclusions reported at all"
    assert all(isinstance(reason, str) and reason for _, reason in excluded)
    applicable = set(loaded.applicable_governance_verifiers())
    assert not applicable & {relpath for relpath, _ in excluded}


# --- A2: freshness over the authority-input domain ----------------------------------------------


def test_rm3_the_authority_input_domain_includes_the_debt_register():
    """A2: the register decides exemption, so editing it must invalidate a measurement."""
    loaded = module()
    baseline = loaded.authority_input_digest()
    source = VERIFIER.read_text(encoding="utf-8")
    digest_fn = source.split("def authority_input_digest")[1].split("\ndef ")[0]
    assert "debt_sections" in digest_fn, "the debt register is not part of the provenance digest"
    assert "applicable_governance_verifiers" in source
    assert baseline == loaded.authority_input_digest(), "the digest is not deterministic"


def test_rm3_a_debt_register_change_invalidates_the_measurement(tmp_path):
    loaded = module()
    recorded = loaded.pm_state_fields()["GOVERNANCE_INPUT_DIGEST"]
    assert loaded.governance_measurement_stale(loaded.pm_state_fields()) == []
    fixture = fixture_from(
        tmp_path,
        "register_changed",
        (f"GOVERNANCE_INPUT_DIGEST:     {recorded}", "GOVERNANCE_INPUT_DIGEST:     " + "1" * 64),
    )
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0
    assert "authority inputs changed" in result.stdout or "retaken" in result.stdout


def test_rm3_freshness_is_not_path_based():
    """Path lists can only see files someone remembered to list; a digest cannot miss content."""
    source = VERIFIER.read_text(encoding="utf-8")
    stale_fn = source.split("def governance_measurement_stale")[1].split("\ndef ")[0]
    assert "authority_input_digest" in stale_fn
    assert "GOVERNANCE_ARTIFACT" not in stale_fn


# --- A3: the recovery procedure must require remeasurement ---------------------------------------


def test_rm3_recovery_packet_requires_current_governance_measurement():
    packet = RECOVERY.read_text(encoding="utf-8")
    assert "--governance" in packet, "the measurement mode is undiscoverable from the packet"
    flat = re.sub(r"\s+", " ", packet)
    assert "MANDATORY before accepting" in flat
    assert "it does not measure" in flat
    assert "INHERITED claim from a MEASURED one" in flat


def test_rm3_a_mistyped_required_option_cannot_downgrade_to_a_weaker_pass():
    result = run_verifier("--governnace")
    assert result.returncode != 0, result.stdout
    assert "unknown option" in result.stdout
    assert "PASS" not in result.stdout.split("unknown option")[-1]


# --- A4: snapshot provenance self-consistency ----------------------------------------------------


def test_rm3_snapshot_provenance_is_coherent():
    loaded = module()
    assert loaded.provenance_conflicts(loaded.pm_state_fields()) == []


def test_rm3_a_stage_attribution_mismatch_is_rejected(tmp_path):
    loaded = module()
    fields = loaded.pm_state_fields()
    fixture = fixture_from(
        tmp_path,
        "stage_mismatch",
        (
            f"RECONCILED_BY_STAGE:         {fields['RECONCILED_BY_STAGE']}",
            "RECONCILED_BY_STAGE:         PCP-V2.1-A",
        ),
    )
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0
    assert "RECONCILED_BY_STAGE" in result.stdout


# --- A5: two classes of fact, two authority models -----------------------------------------------


def test_rm3_the_contract_separates_engineering_facts_from_pm_facts():
    flat = re.sub(r"\s+", " ", CONTRACT.read_text(encoding="utf-8"))
    assert "ENGINEERING VOLATILE FACT" in flat
    assert "PM CONTROL-PLANE FACT" in flat
    assert "The snapshot is a cache and is never sufficient" in flat
    assert "recorded only as prose is not authoritative at all" in flat
    assert "structured and versioned" in flat


# =================================================================================================
# 10. Canonical measurement determinism and ambient-state isolation (Step PCP-V2.1-RM4)
#
# DEF-PCPE-01: the measurement ran in the operator's own working tree. Three verifiers reading a
# gitignored .runtime/ passed here and failed in a clean checkout of the same commit, with a
# byte-identical authority digest. "BLOCKERS: NONE" described the workstation, not canonical main.
# =================================================================================================


PROBE_PREFIX = "verify_rm4probe_"

PROBE_VERIFIERS = {
    # A -- tracked repository input only.
    "tracked": (
        "import pathlib\n"
        "ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "print((ROOT / 'docs' / 'governance' / 'AI_AGENTS_PM_STATE.md').is_file())\n"
    ),
    # B -- an input the harness itself generates, deterministically, from tracked content.
    "generated": (
        "import os, pathlib\n"
        "ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "derived = pathlib.Path(os.environ['TEMP']) / 'rm4-generated.txt'\n"
        "derived.write_text((ROOT / 'README.md').read_text(encoding='utf-8')[:16])\n"
        "print(derived.read_text())\n"
    ),
    # C -- a gitignored local file. The DEF-PCPE-01 shape.
    "ignored": (
        "import pathlib\n"
        "ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "print((ROOT / '.runtime' / 'rm4-probe.json').is_file())\n"
    ),
    # D -- a variable whose value measurement policy passes through from the machine.
    "envvar": "import os\nprint(len(os.environ['PATH']))\n",
    # E -- a home or cache location.
    "homefile": "import pathlib\nprint((pathlib.Path.home() / '.pcp-rm4-probe').is_file())\n",
    # F -- inputs that cannot be observed at all: this one erases the record of what it read.
    "unobserved": (
        "import io, os\n"
        "io.open(os.environ['PCP_MEASUREMENT_TRACE'], 'w').close()\n"
        "print('inputs unobservable')\n"
    ),
    # An external tool named only as forbidden path text must not be excluded for the word alone.
    "toolword": (
        "import pathlib\n"
        "FORBIDDEN = 'infra/helm/'\n"
        "ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "print(FORBIDDEN, (ROOT / 'README.md').is_file())\n"
    ),
    # A previously unseen way of reaching repository state must stay measured, never excluded.
    "unseenform": (
        "import os, pathlib\n"
        "ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "print(len(os.listdir(ROOT / 'docs')))\n"
    ),
}

OUT_OF_DOMAIN = "agents/verify_rm4probe_runtime.py"


def seed_probe_tree() -> Path:
    seed = Path(tempfile.mkdtemp(prefix="pcp-rm4-probe-"))
    (seed / "scripts").mkdir(parents=True, exist_ok=True)
    for name, body in PROBE_VERIFIERS.items():
        (seed / "scripts" / f"{PROBE_PREFIX}{name}.py").write_text(body, encoding="utf-8")
    planted = seed / OUT_OF_DOMAIN
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("print('runtime module, not governance')\n", encoding="utf-8")
    return seed


def measure_probes(loaded) -> dict:
    """One canonical measurement over a deliberately tiny seeded domain."""
    original = loaded.domains_at

    def restricted(root):
        verifiers, _ = original(root)
        return [p for p in verifiers if Path(p).name.startswith(PROBE_PREFIX)], []

    loaded.domains_at = restricted
    seed = seed_probe_tree()
    try:
        return loaded.canonical_measurement(ambient=seed)
    finally:
        loaded.domains_at = original
        shutil.rmtree(seed, ignore_errors=True)


@pytest.fixture(scope="module")
def probes() -> dict:
    measurement = measure_probes(module())
    assert "error" not in measurement, measurement.get("error")
    return measurement


def state_of(measurement: dict, name: str) -> tuple[str, str]:
    identity = f"verifier:{PROBE_PREFIX}{name}.py"
    for reported, reason in measurement.get("environment_dependent", []):
        if reported == identity:
            return module().ENVIRONMENT_DEPENDENT, reason
    for reported, reason in measurement.get("unknown", []):
        if reported == identity:
            return module().UNKNOWN, reason
    return module().REPO_DETERMINISTIC, ""


# --- the harness: canonical measurement never runs in the developer's tree ------------------------


def test_rm4_canonical_measurement_runs_in_a_disposable_pristine_checkout():
    source = VERIFIER.read_text(encoding="utf-8")
    harness = source.split("def canonical_measurement")[1].split("\ndef ")[0]
    assert "materialize_canonical_repository" in harness
    assert "worktree" not in harness, "a linked worktree inherits the operator namespace"
    assert "tempfile.TemporaryDirectory" in harness
    body = source.split("def _measure_tree")[1].split("\ndef ")[0]
    assert "cwd=tree" in body, "the measurement still executes in the developer's working tree"
    assert "cwd=ROOT" not in body
    assert "_sanitized_environment" in body


def test_rm4_the_measurement_checkout_must_be_pristine():
    """A checkout carrying inherited untracked state is not a canonical measurement environment."""
    body = VERIFIER.read_text(encoding="utf-8").split("def _measure_tree")[1].split("\ndef ")[0]
    assert "--ignored" in body
    assert "is not pristine" in body


def test_rm4_the_environment_is_an_allowlist_not_the_operators():
    loaded = module()
    granted = (
        VERIFIER.read_text(encoding="utf-8")
        .split("def _sanitized_environment")[1]
        .split("\ndef ")[0]
    )
    assert "os.environ.copy()" not in granted, "the ambient environment is inherited wholesale"
    for controlled in ("HOME", "USERPROFILE", "TEMP", "PYTHONHASHSEED", "PYTHONPYCACHEPREFIX"):
        assert controlled in granted
    assert loaded.AMBIENT_ENVIRONMENT <= loaded.ENVIRONMENT_ALLOWLIST


def test_rm4_developer_tree_leftovers_cannot_reach_the_measurement():
    """DEF-PCPE-01 directly: the same non-canonical artifact, present then absent, in the tree the
    operator happens to have open. The canonical answer must not move."""
    loaded = module()
    relpath = ".runtime/rm4-devtree-independence-probe.json"
    assert loaded.non_canonical_paths(ROOT, {relpath}), "the probe path is not gitignored"
    leftover = ROOT / relpath
    leftover.parent.mkdir(parents=True, exist_ok=True)
    try:
        leftover.write_text('{"probe": true}\n', encoding="utf-8")
        with_leftover = measure_probes(loaded)
        leftover.unlink()
        without_leftover = measure_probes(loaded)
    finally:
        if leftover.exists():
            leftover.unlink()
    for field in ("failures", "environment_dependent", "unknown", "verifiers"):
        assert with_leftover[field] == without_leftover[field], field


# --- admissibility: three states, and UNKNOWN is mapped to neither neighbour ----------------------


def test_rm4_admissibility_has_three_explicit_states():
    loaded = module()
    assert {loaded.REPO_DETERMINISTIC, loaded.ENVIRONMENT_DEPENDENT, loaded.UNKNOWN} == {
        "REPO_DETERMINISTIC",
        "ENVIRONMENT_DEPENDENT",
        "UNKNOWN",
    }


def test_rm4_probe_a_tracked_input_is_repo_deterministic(probes):
    assert state_of(probes, "tracked")[0] == module().REPO_DETERMINISTIC


def test_rm4_probe_b_a_generated_input_is_repo_deterministic(probes):
    """Provisioned deterministically from canonical content, so its authority is canonical."""
    assert state_of(probes, "generated")[0] == module().REPO_DETERMINISTIC


def test_rm4_probe_c_a_gitignored_dependency_is_environment_dependent(probes):
    state, reason = state_of(probes, "ignored")
    assert state == module().ENVIRONMENT_DEPENDENT
    assert ".runtime/rm4-probe.json" in reason


def test_rm4_probe_d_the_environment_is_controlled_rather_than_classified(probes):
    """Deliberate deviation, recorded rather than hidden.

    Sanitising the environment eliminates environment dependence instead of classifying it: every
    variable is granted a policy-derived value, passed through, or deterministically absent. An
    axis that flagged reads of the six pass-through names classified three ALREADY-REGISTERED debt
    identities as environment-dependent, because Python's own machinery reads COMSPEC and PATH on
    every subprocess call. That is under-sampling, so the axis was dropped and the guarantee is
    made by the policy instead.
    """
    loaded = module()
    assert state_of(probes, "envvar")[0] == loaded.REPO_DETERMINISTIC
    assert "controlled rather than classified" in loaded.ENVIRONMENT_NOTE
    rule = VERIFIER.read_text(encoding="utf-8").split("def admissibility")[1].split("\ndef ")[0]
    assert "AMBIENT_ENVIRONMENT" not in rule
    granted = (
        VERIFIER.read_text(encoding="utf-8")
        .split("def _sanitized_environment")[1]
        .split("\ndef ")[0]
    )
    assert "os.environ.copy()" not in granted, "an unsanitized environment would restore the risk"


def test_rm4_probe_e_a_home_or_cache_dependency_is_environment_dependent(probes):
    state, reason = state_of(probes, "homefile")
    assert state == module().ENVIRONMENT_DEPENDENT
    assert "home" in reason or "cache" in reason


def test_rm4_probe_f_unobservable_inputs_fail_closed_as_unknown(probes):
    """Not excluded, and not admitted using the workstation's answer. It blocks."""
    state, reason = state_of(probes, "unobserved")
    assert state == module().UNKNOWN
    assert "not observed" in reason


def test_rm4_a_tool_word_in_path_text_does_not_exclude(probes):
    """The RM3 false exclusion must not come back on the admissibility axis."""
    assert state_of(probes, "toolword")[0] == module().REPO_DETERMINISTIC


def test_rm4_an_unseen_repository_access_form_stays_measured(probes):
    assert state_of(probes, "unseenform")[0] == module().REPO_DETERMINISTIC


def test_rm4_unknown_blocks_the_blockers_none_claim():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "check19b" in source
    guard = source.split('"check19b"')[0].rsplit("expect(", 1)[1]
    assert 'measurement.get("unknown", []) == []' in guard


def test_rm4_out_of_domain_runtime_modules_are_not_pulled_in(probes):
    for identity in probes.get("failures", []):
        assert "agents/" not in identity
    assert module().GOVERNANCE_ARTIFACT.match(OUT_OF_DOMAIN) is None


def test_rm4_environment_dependent_identities_are_not_registered_as_debt(probes):
    """RM4 section 12: 'this machine had no runtime evidence' is not a governance failure."""
    loaded = module()
    active, historical = loaded.debt_sections(PM_STATE.read_text(encoding="utf-8"))
    for identity, _ in probes.get("environment_dependent", []):
        assert identity not in active
        assert identity not in historical
    for name in ("verify_production_readiness_runtime.py", "verify_backup_restore_dr_runtime.py"):
        assert f"verifier:{name}" not in active


# --- reproducibility: two independent pristine checkouts, run one after the other -----------------


def test_rm4_two_clean_checkouts_produce_identical_exact_results():
    """Count-only equality is not accepted: the exact identity sets must match."""
    loaded = module()
    first = measure_probes(loaded)
    second = measure_probes(loaded)
    assert first["commit"] == second["commit"]
    assert len(first["commit"]) == 40, "the recorded commit is not a resolved full SHA"
    assert first["verifiers"] == second["verifiers"]
    assert first["failures"] == second["failures"]
    assert first["environment_dependent"] == second["environment_dependent"]
    assert first["unknown"] == second["unknown"]
    assert first["policy_digest"] == second["policy_digest"]


# --- provenance: a result must state the policy it was taken under -------------------------------


def test_rm4_measurement_provenance_is_recorded_and_current():
    loaded = module()
    assert loaded.measurement_provenance_conflicts(loaded.pm_state_fields()) == []
    fields = loaded.pm_state_fields()
    assert fields["MEASUREMENT_POLICY_ID"] == loaded.MEASUREMENT_POLICY_ID
    assert fields["MEASUREMENT_POLICY_DIGEST"] == loaded.measurement_policy_digest()


def test_rm4_a_policy_change_invalidates_the_recorded_measurement(tmp_path):
    loaded = module()
    fixture = fixture_from(
        tmp_path,
        "policy_changed",
        (
            f"MEASUREMENT_POLICY_DIGEST:   {loaded.measurement_policy_digest()}",
            "MEASUREMENT_POLICY_DIGEST:   " + "9" * 64,
        ),
    )
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0
    assert "measurement policy changed" in result.stdout


def test_rm4_a_measurement_without_a_policy_is_rejected(tmp_path):
    loaded = module()
    fixture = fixture_from(
        tmp_path,
        "policy_absent",
        (f"MEASUREMENT_POLICY_ID:       {loaded.MEASUREMENT_POLICY_ID}", "REMOVED_POLICY_ID: x"),
    )
    result = run_verifier("--pm-state", str(fixture))
    assert result.returncode != 0
    assert "MEASUREMENT_POLICY_ID is absent" in result.stdout


def test_rm4_the_policy_is_part_of_the_authority_digest():
    """Changing how measurement decides anything must make the recorded result stale."""
    source = VERIFIER.read_text(encoding="utf-8")
    digest_fn = source.split("def authority_input_digest")[1].split("\ndef ")[0]
    assert "measurement_policy_digest()" in digest_fn
    policy_fn = source.split("def measurement_policy_digest")[1].split("\ndef ")[0]
    assert "TRACER_SOURCE" in policy_fn, "the tracer implementing admissibility is not covered"
    assert "ENVIRONMENT_ALLOWLIST" in policy_fn


def test_rm4_the_admissibility_rule_is_not_a_verifier_name_list():
    """Exclusion is the under-sampling boundary now, so it must not be an enumeration of names."""
    source = VERIFIER.read_text(encoding="utf-8")
    rule = source.split("def admissibility")[1].split("\ndef ")[0]
    for token in ("verify_", "runtime.py", ".runtime", "readiness", "backup-dr"):
        assert token not in rule, f"the admissibility rule consults {token!r}"
    lookup = source.split("def non_canonical_paths")[1].split("\ndef ")[0]
    assert "check-ignore" in lookup, "non-canonical status is not decided by the repository itself"


def test_rm4_recovery_packet_names_the_canonical_measurement():
    flat = re.sub(r"\s+", " ", RECOVERY.read_text(encoding="utf-8"))
    assert "--governance" in flat
    assert "STANDALONE repository it builds itself" in flat
    assert "NOT the working tree you happen to have open" in flat
    assert "branches, remotes, config or credentials" in flat


# =================================================================================================
# 11. Git namespace isolation and harness-artifact attribution (Step PCP-V2.1-RM5)
#
# BLK-PCPF-01: the measurement ran in a linked worktree, whose git common-dir IS the operator's
# repository. It inherited 48 local branches, the operator's origin URL, their git identity and
# live network -- and six verifiers returned different results at the same canonical commit when
# that namespace differed.
#
# BLK-PCPF-02: pytest's session-end cache write landed in a gitignored .pytest_cache and was
# attributed to whichever node ran last, so an identical new failing test blocked at first and
# middle position and was silently exempted at last position.
# =================================================================================================


PROBE_TEST_MODULE = "tests/test_step66d_align1_rm1_fixed_range_remediation.py"
PROBE_VERIFIER = "verify_step66d_align1_rm1_fixed_range_remediation.py"
PROBE_BODY = 'def test_rm5_probe_new_failure():\n    assert False, "deliberate probe failure"\n\n\n'


def canonical_repo(loaded, tmp_path):
    """Materialise the measurement repository the way a canonical run does."""
    scaffold = tmp_path / "scaffold"
    scaffold.mkdir()
    home = scaffold / "home"
    home.mkdir()
    commit = loaded.git("rev-parse", "HEAD")
    repo, remote, error = loaded.materialize_canonical_repository(commit, scaffold, home)
    assert not error, error
    return repo, remote, scaffold, home, commit


def insert_probe(body: str, new: str, position: str) -> str:
    """Insert at a syntactically safe boundary: before an UNDECORATED top-level test."""
    import ast

    tree = ast.parse(body)
    tests = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
        and not node.decorator_list
    ]
    assert tests, "no undecorated top-level test to anchor on"
    if position == "last":
        return body.rstrip("\n") + "\n" + new
    anchor = tests[0] if position == "first" else tests[len(tests) // 2]
    lines = body.splitlines(keepends=True)
    return "".join(lines[: anchor.lineno - 1]) + new + "".join(lines[anchor.lineno - 1 :])


def measure_new_test(loaded, position: str, body: str = PROBE_BODY) -> dict:
    """Append a real failing governance test and take a real canonical measurement."""
    seed = Path(tempfile.mkdtemp(prefix="pcp-rm5-"))
    (seed / "tests").mkdir(parents=True)
    original_source = (ROOT / PROBE_TEST_MODULE).read_text(encoding="utf-8")
    (seed / PROBE_TEST_MODULE).write_text(
        insert_probe(original_source, body, position), encoding="utf-8"
    )
    original = loaded.domains_at

    def restricted(root):
        verifiers, tests = original(root)
        return (
            [p for p in verifiers if Path(p).name == PROBE_VERIFIER],
            [p for p in tests if p == PROBE_TEST_MODULE],
        )

    loaded.domains_at = restricted
    try:
        return loaded.canonical_measurement(ambient=seed)
    finally:
        loaded.domains_at = original
        shutil.rmtree(seed, ignore_errors=True)


# --- git namespace isolation ----------------------------------------------------------------------


def test_rm5_measurement_repository_has_its_own_git_namespace(tmp_path):
    loaded = module()
    repo, _, scaffold, home, commit = canonical_repo(loaded, tmp_path)
    common = loaded._isolated_git(scaffold, home, repo, "rev-parse", "--git-common-dir").stdout
    stated = Path(common.strip())
    resolved = stated if stated.is_absolute() else (repo / stated)
    assert (
        resolved.resolve() != (ROOT / ".git").resolve()
    ), "the measurement repository shares the operator's git common-dir"
    assert loaded._isolated_git(scaffold, home, repo, "rev-parse", "HEAD").stdout.strip() == commit


def test_rm5_only_declared_refs_exist_in_the_measurement_repository(tmp_path):
    loaded = module()
    repo, _, scaffold, home, commit = canonical_repo(loaded, tmp_path)
    refs = loaded.ref_manifest(repo, scaffold, home)
    assert refs, "the measurement repository has no refs at all"
    assert all(entry.endswith(commit) for entry in refs), refs
    names = {entry.split()[0] for entry in refs}
    assert names <= {"refs/heads/main", "refs/remotes/origin/main", "refs/remotes/origin/HEAD"}
    operator_branches = len(loaded.git("branch", "--format=%(refname)").splitlines())
    assert operator_branches > len(names), "the operator repo has too few branches to prove this"


def test_rm5_the_operator_origin_is_not_reachable_from_the_measurement_repository(tmp_path):
    loaded = module()
    repo, remote, scaffold, home, _ = canonical_repo(loaded, tmp_path)
    origin = loaded._isolated_git(scaffold, home, repo, "config", "--get", "remote.origin.url")
    assert Path(origin.stdout.strip()).resolve() == remote.resolve(), origin.stdout
    operator_origin = loaded.git("config", "--get", "remote.origin.url")
    assert operator_origin and operator_origin not in origin.stdout


def test_rm5_git_runs_without_operator_or_system_configuration(tmp_path):
    loaded = module()
    repo, _, scaffold, home, _ = canonical_repo(loaded, tmp_path)
    granted = loaded._isolated_git_environment(scaffold, home)
    assert granted["GIT_CONFIG_NOSYSTEM"] == "1"
    assert Path(granted["GIT_CONFIG_GLOBAL"]) == scaffold / "gitconfig"
    assert granted["GIT_TERMINAL_PROMPT"] == "0"
    identity = loaded._isolated_git(scaffold, home, repo, "config", "--get", "user.email")
    assert identity.stdout.strip() == "", "the operator's git identity reached the measurement"
    measured = loaded._sanitized_environment(scaffold, home, scaffold / "t.trace", repo)
    for key in ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT", "GIT_TRACE"):
        assert key in measured, f"measured processes run git without {key}"


def test_rm5_an_operator_local_branch_cannot_move_canonical_truth():
    """The BLK-PCPF-01 property, exercised rather than asserted."""
    loaded = module()
    branch = "rm5/namespace-independence-probe"
    subprocess.run(
        ["git", "branch", "-f", branch, "HEAD"], cwd=ROOT, check=False, capture_output=True
    )
    try:
        with_branch = measure_probes(loaded)
    finally:
        subprocess.run(["git", "branch", "-D", branch], cwd=ROOT, check=False, capture_output=True)
    without_branch = measure_probes(loaded)
    for field in ("failures", "environment_dependent", "unknown", "verifiers", "ref_manifest"):
        assert with_branch[field] == without_branch[field], field


def test_rm5_a_revision_outside_the_declared_namespace_is_classified_not_registered():
    """A verifier pinning an operator-local commit is not canonical debt, and it says why."""
    loaded = module()
    source = VERIFIER.read_text(encoding="utf-8")
    assert "def unresolvable_revisions" in source
    rule = source.split("def unresolvable_revisions")[1].split("\ndef ")[0]
    assert "rev-parse" in rule and "--verify" in rule
    for token in ("verify_", "step66", "sync1"):
        assert token not in rule, f"the ref-authority rule consults {token!r}"
    assert loaded.requested_revisions(
        "trace: built-in: git rev-parse 828ea90\ntrace: built-in: git log origin/some-branch\n"
    ) == {"828ea90", "origin/some-branch"}


def test_rm5_git_child_processes_are_observed_natively():
    """GIT_TRACE is git's own argv log, so a shell shim and its quoting hazards are unnecessary."""
    source = VERIFIER.read_text(encoding="utf-8")
    assert '"GIT_TRACE"' in source
    assert "GIT_TRACE_INVOCATION" in source


# --- harness-owned artifacts ----------------------------------------------------------------------


def test_rm5_the_pytest_cache_cannot_become_a_measured_dependency():
    body = VERIFIER.read_text(encoding="utf-8").split("def _measure_tree")[1].split("\ndef ")[0]
    assert "no:cacheprovider" in body
    assert "cache_dir=" in body
    assert ".pytest_cache" not in body, "the fix is a filename filter rather than isolation"


def test_rm5_harness_state_lives_outside_the_measured_repository():
    """Ownership, not a filename list: nothing the harness writes lands in the measured repo."""
    source = VERIFIER.read_text(encoding="utf-8")
    granted = source.split("def _sanitized_environment")[1].split("\ndef ")[0]
    for harness_owned in ("PYTHONPYCACHEPREFIX", "TEMP", "PCP_MEASUREMENT_TRACE", "GIT_TRACE"):
        assert harness_owned in granted
    assert "scaffold" in granted
    admissible = source.split("def admissibility")[1].split("\ndef ")[0]
    assert "pytest_cache" not in admissible
    assert "__pycache__" not in admissible


@pytest.mark.parametrize("position", ["first", "middle", "last"])
def test_rm5_a_new_failing_test_blocks_from_any_position(position):
    """BLK-PCPF-02 directly. Execution order must not decide whether a failure is canonical."""
    loaded = module()
    measurement = measure_new_test(loaded, position)
    node = f"test:{PROBE_TEST_MODULE}::test_rm5_probe_new_failure"
    escaped = [
        reason for identity, reason in measurement["environment_dependent"] if identity == node
    ]
    assert node in measurement["failures"], f"the probe escaped at {position}: {escaped}"
    active, _ = loaded.debt_sections(PM_STATE.read_text(encoding="utf-8"))
    assert loaded.new_unregistered_failures(measurement["failures"], active) != []


def test_rm5_a_test_reading_a_noncanonical_file_is_still_classified():
    """The control: the harness-artifact fix must not become blanket suppression."""
    loaded = module()
    measurement = measure_new_test(
        loaded,
        "last",
        body=(
            "def test_rm5_probe_new_failure():\n"
            "    import pathlib\n"
            "    root = pathlib.Path(__file__).resolve().parents[1]\n"
            "    assert (root / '.runtime' / 'rm5-probe.json').is_file()\n\n\n"
        ),
    )
    node = f"test:{PROBE_TEST_MODULE}::test_rm5_probe_new_failure"
    reasons = {identity: reason for identity, reason in measurement["environment_dependent"]}
    assert node in reasons, "a test's own non-canonical dependency was suppressed"
    assert ".runtime" in reasons[node]


def test_rm5_the_measurement_policy_was_versioned_for_these_semantics():
    """RM4 evidence must not survive a change in how measurement works."""
    loaded = module()
    assert loaded.MEASUREMENT_POLICY_VERSION == "2"
    assert loaded.ADMISSIBILITY_CONTRACT_VERSION == "2"
    assert "standalone-clone" in loaded.MEASUREMENT_ISOLATION_MODE
    policy = loaded.measurement_policy()
    for field in ("GIT_ISOLATION_POLICY", "REMOTE_AUTHORITY_POLICY", "HARNESS_ARTIFACT_POLICY"):
        assert policy[field]
    digest_fn = (
        VERIFIER.read_text(encoding="utf-8")
        .split("def measurement_policy_digest")[1]
        .split("\ndef ")[0]
    )
    assert "measurement_policy()" in digest_fn
