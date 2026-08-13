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
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_pcp_v2_control_plane.py"

PM_STATE = ROOT / "docs" / "governance" / "AI_AGENTS_PM_STATE.md"
CONTRACT = ROOT / "docs" / "governance" / "project-control-plane-v2.md"
RECOVERY = ROOT / "docs" / "governance" / "pcp-v2-recovery.md"

CANONICAL_MAIN = "2a2facc898aa3738322d4487cbfce591cfbadc46"
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
    assert CANONICAL_MAIN not in source, "the canonical main SHA is hard-coded into the gate"
    assert AT_M1_MERGE_COMMIT not in source, "the merge commit is hard-coded into the gate"


def test_pcp_snapshot_is_versioned_and_reconcilable():
    fields = module().pm_state_fields()
    assert fields["PM_STATE_VERSION"] == "1"
    assert fields["PM_STATE_SCHEMA"] == "pcp-v2"
    assert fields["RECONCILED_AGAINST_MAIN"] == CANONICAL_MAIN
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
    (
        "C2_at_m2_authorized",
        [
            (
                "AT_M2:                       NOT AUTHORIZED",
                "AT_M2:                       AUTHORIZED",
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
                f"RECONCILED_AGAINST_MAIN:     {CANONICAL_MAIN}",
                f"RECONCILED_AGAINST_MAIN:     {PR28_HEAD}",
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
    loaded = module()
    fields = base_fields()
    fields["CURRENT_MILESTONE"] = "AT_M2"
    assert any(v.startswith("I1:") for v in loaded.invariant_violations(fields))


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


def test_i7_at_m2_requires_the_pcp_gate_to_have_passed():
    loaded = module()
    fields = base_fields()
    fields["AT_M2"] = "AUTHORIZED"
    assert any(v.startswith("I7:") for v in loaded.invariant_violations(fields))
    fields["PCP_V2_1"] = "PASS"
    assert not any(v.startswith("I7:") for v in loaded.invariant_violations(fields))


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
