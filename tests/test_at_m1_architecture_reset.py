"""AT-M1 -- architecture reset invariants, scope and negative contract probes.

Three layers:

  1. Scope and artifact tests   re-derive the facts from git and the artifacts themselves
  2. Invariant tests            INV-01 .. INV-10, asserted independently of the verifier
  3. Negative contract probes   mutate a COPY of the architecture package and confirm the verifier
                                rejects each forbidden change, plus an untampered control

The probes exist because a verifier that has never been shown to fail is not evidence. Each probe
applies exactly one forbidden mutation to a scratch copy and asserts the corresponding check stops
holding.

Read-only with respect to the repository. Starts no runtime, container, database or external
provider.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_at_m1_architecture_reset.py"

AT_M1_BASELINE = "fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009"

ARCH = "docs/architecture/autonomous-team"
CONTRACTS = "docs/contracts/autonomous-team"
HANDOFF = "docs/handoffs/autonomous-team"

BINDING = f"{CONTRACTS}/at-binding-decisions.md"
TERMINOLOGY = f"{CONTRACTS}/at-canonical-terminology-registry.md"
REGISTRY = f"{CONTRACTS}/at-capability-state-registry.json"
ADRS = "docs/decisions/at-m1-architecture-decisions.md"
COLLAB = f"{ARCH}/collaboration-and-workroom-model.md"
PLANNING = f"{ARCH}/planning-and-plan-revision-model.md"
ORCHESTRATION = f"{ARCH}/orchestration-debug-replan-model.md"
LINEAGE = f"{ARCH}/source-of-truth-and-lineage-model.md"
EVIDENCE = f"{HANDOFF}/at-m1-evidence.md"

# Authorized at AT-M1-RM1: the two EXISTING canonical registries the AT family is registered in.
MASTER = "docs/alignment/66-project-completion/master"
PRECEDENCE = f"{MASTER}/canonical-source-of-truth-precedence.md"
MANIFEST = f"{MASTER}/canonical-milestone-manifest.md"

EXPECTED_PATHS = {
    f"{ARCH}/at-m1-architecture-reset.md",
    f"{ARCH}/actor-principal-and-team-model.md",
    COLLAB,
    PLANNING,
    ORCHESTRATION,
    LINEAGE,
    f"{ARCH}/human-intervention-and-governance-boundary.md",
    f"{ARCH}/functional-poc-capability-contract.md",
    f"{ARCH}/implementation-milestone-plan.md",
    BINDING,
    TERMINOLOGY,
    REGISTRY,
    ADRS,
    EVIDENCE,
    f"{HANDOFF}/at-m1-implementation-slice-handoff.md",
    "scripts/verify_at_m1_architecture_reset.py",
    "tests/test_at_m1_architecture_reset.py",
    PRECEDENCE,
    MANIFEST,
}

ORIGINAL_AT_M1_PATH_COUNT = 17
RM1_REGISTRATION_PATHS = {PRECEDENCE, MANIFEST}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def changed_paths() -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{AT_M1_BASELINE}...HEAD").splitlines()
        if line.strip()
    }


def read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def verifier_module():
    spec = importlib.util.spec_from_file_location("at_m1_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fenced_blocks(text: str) -> list[str]:
    return re.findall(r"```text\n(.*?)```", text, re.DOTALL)


def team_message_schema(text: str) -> str:
    """The TeamMessage field block, identified by its own real fields.

    A forbidden field NAME legitimately appears in the prohibition lists, so a plain substring
    scan cannot distinguish 'we forbid this' from 'we store this'. The discriminator is whether
    the name appears inside the block that actually declares TeamMessage's fields.
    """
    for block in fenced_blocks(text):
        if "message_id" in block and "thread_id" in block and "sender_principal_id" in block:
            return block
    return ""


# =================================================================================================
# 1. Scope and artifacts
# =================================================================================================


def test_baseline_is_an_ancestor_and_pinned():
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", AT_M1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0
    )
    assert f'AT_M1_BASELINE = "{AT_M1_BASELINE}"' in read(
        "scripts/verify_at_m1_architecture_reset.py"
    )


def test_changed_paths_equal_the_registry_exactly():
    changed = changed_paths()
    assert (
        changed == EXPECTED_PATHS
    ), f"unexpected={sorted(changed - EXPECTED_PATHS)} missing={sorted(EXPECTED_PATHS - changed)}"


def test_scope_is_compared_by_set_equality_not_prefix():
    source = read("scripts/verify_at_m1_architecture_reset.py")
    assert "changed == AT_M1_EXPECTED_PATHS" in source


def test_all_nineteen_artifacts_exist():
    """17 original AT-M1 artifacts plus the two RM1-authorized canonical registries."""
    assert len(EXPECTED_PATHS) == 19
    assert len(EXPECTED_PATHS - RM1_REGISTRATION_PATHS) == ORIGINAL_AT_M1_PATH_COUNT
    for relpath in sorted(EXPECTED_PATHS):
        assert (ROOT / relpath).is_file(), relpath


def test_every_markdown_artifact_carries_the_repo_footer():
    for relpath in sorted(p for p in EXPECTED_PATHS if p.endswith(".md")):
        text = read(relpath)
        assert "staging-safety:" in text, relpath
        assert "Non-production only" in text, relpath


def test_adrs_live_in_the_canonical_decisions_directory():
    """The repo has no adr/ subdirectory convention; ADRs live in docs/decisions/."""
    assert (ROOT / ADRS).is_file()
    assert not (ROOT / ARCH / "adr").exists()
    assert [p for p in changed_paths() if "/adr/" in p] == []


# =================================================================================================
# 2. Invariants
# =================================================================================================


def test_inv01_task_roles_unchanged_and_human_only():
    assert "shared/sdk/tasks/rbac.py" not in changed_paths()
    module = verifier_module()
    roles = module.task_roles_from_source()
    assert roles == {
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    }
    for forbidden in ("runtime_agent", "ai_partner", "system", "agent"):
        assert forbidden not in roles


def test_inv02_single_execution_lineage():
    lineage = read(LINEAGE)
    assert "SOLE autonomous execution source of truth" in lineage
    assert "TWO EXECUTION SYSTEMS" in lineage and "FORBIDDEN" in lineage
    assert "SUBORDINATE HUMAN INTERACTION SURFACE" in lineage


def test_inv03_team_decision_separate_from_po_decision():
    collab = read(COLLAB)
    assert "MUST NOT share enums" in collab
    assert "does NOT authorize a production action" in collab
    assert "does NOT replace Product Owner acceptance" in collab
    # The three decision vocabularies must not be mapped onto one another.
    assert "ACCEPTED_WITH_FOLLOW_UP" not in re.sub(r"`[^`]*`", "", collab).split("## 8.")[
        0
    ].replace("{ACCEPTED, ACCEPTED_WITH_FOLLOW_UP, REJECTED}", "")


def test_inv04_no_chain_of_thought_field_is_contracted():
    module = verifier_module()
    collab = read(COLLAB)
    corpus = collab + read(BINDING) + read(ORCHESTRATION)
    for field in module.FORBIDDEN_STORAGE_FIELDS:
        assert field in corpus, f"{field} should be named as a prohibition"

    schema = team_message_schema(collab)
    assert schema, "the TeamMessage schema block was not found -- the check would be vacuous"
    assert "sender_principal_id" in schema and "artifact_refs" in schema
    for field in module.FORBIDDEN_STORAGE_FIELDS:
        assert field not in schema, f"{field} is declared as a TeamMessage field"


def test_inv05_plan_revision_is_versioned_and_supersedable():
    planning = read(PLANNING)
    for prop in ("VERSIONED", "HISTORICALLY IMMUTABLE", "SUPERSEDABLE", "DIFFABLE", "TRACEABLE"):
        assert prop in planning
    assert "supersedes_revision_id" in planning
    assert "Mutable-history overwrite is FORBIDDEN" in planning


def test_inv06_debug_attempt_is_not_retry():
    orchestration = read(ORCHESTRATION)
    assert "INFRASTRUCTURE RETRY" in orchestration
    assert "DEBUG ATTEMPT" in orchestration
    assert "NOT an autonomous debugging model" in orchestration
    assert "changes      nothing" in orchestration


def test_inv07_template_planner_is_not_canonical():
    planning = read(PLANNING)
    assert "TEST / DEMO FIXTURE ONLY" in planning
    assert "Canonical?        NO" in planning
    assert "task_graph.py" in planning


def test_inv08_pr28_held_and_untouched():
    """AT-M1-RM1: target the authoritative treatment line, not the whole file.

    The previous form searched the entire evidence document for "HOLD" and "NON-CANONICAL", so
    PR #28 could be declared CANONICAL / ACTIVE / MERGE-READY on its own line while incidental
    text elsewhere kept the assertion green.
    """
    module = verifier_module()
    evidence = read(EVIDENCE)
    treatment = module.labelled_line(evidence, "PR #28 treatment:")
    assert treatment, "the evidence has no authoritative 'PR #28 treatment:' line"
    assert "HOLD" in treatment.upper() and "PRESERVE" in treatment.upper()
    assert "NON-CANONICAL" in treatment.upper()
    assert not module.claims_canonical(treatment)
    assert "MERGE-READY" not in treatment.upper()
    row = module.table_row(evidence, "PR #28")
    assert row and "hold" in row.lower() and "AT-M7" in row
    assert not module.claims_canonical(row)
    changed = changed_paths()
    assert not any("delivery_acceptance" in p for p in changed)
    assert not any(p.startswith("migrations/036") for p in changed)


def test_inv09_66d_preserved_set_untouched():
    binding = read(BINDING)
    for preserved in ("Delivery Review", "Review Gate Actions", "ProductOwnerDecision", "66D-D05"):
        assert preserved in binding
    changed = changed_paths()
    assert not any(p.startswith("docs/design/66d-delivery-acceptance/") for p in changed)
    assert not any(p.startswith("docs/architecture/66d-delivery-acceptance/") for p in changed)
    assert not any(p.startswith("docs/contracts/66d-delivery-acceptance/") for p in changed)


def test_inv10_no_runtime_implementation():
    changed = changed_paths()
    forbidden = ("agents/", "apps/", "shared/", "migrations/", "infra/", "runtime/", ".github/")
    assert [p for p in changed if p.startswith(forbidden)] == []
    assert not any(p.endswith((".sql", ".tsx", ".ts", ".jsx")) for p in changed)
    assert sorted(p for p in changed if not p.startswith("docs/")) == [
        "scripts/verify_at_m1_architecture_reset.py",
        "tests/test_at_m1_architecture_reset.py",
    ]


def test_at_d09_remains_open_and_not_an_adr():
    """AT-M1-RM3 (ADV-R3-02): the whole-document form this replaces passed with AT-D09 closed.

    Unrelated OPEN and DEFERRED tokens elsewhere in the contract satisfied it. AT-D09's status is
    now asserted per surface by test_rm3_every_at_d09_status_surface_records_it_open; what remains
    here is the ADR claim, which is a different document.
    """
    assert "REMAINS AUTHORITATIVE" in read(BINDING)
    adrs = read(ADRS)
    closed_section = adrs.split("## Open decisions")[0]
    assert "AT-D09" not in closed_section


def test_capability_registry_totals_are_computed_not_asserted():
    data = json.loads(read(REGISTRY))
    caps = data["capabilities"]
    computed = {
        state: sum(1 for c in caps if c["state"] == state) for state in data["allowed_states"]
    }
    computed["entries"] = len(caps)
    computed["poc_blocking"] = sum(1 for c in caps if c["poc_blocking"])
    assert data["totals"] == computed
    assert all(c["state"] in data["allowed_states"] for c in caps)
    assert all(c["evidence"] for c in caps)


def test_capability_registry_does_not_overclaim():
    """Nothing the audit proved absent may be marked IMPLEMENTED."""
    data = json.loads(read(REGISTRY))
    states = {c["capability"]: c["state"] for c in data["capabilities"]}
    for absent in ("Delegation", "Handoff", "PlanRevision", "Replan", "Proposal"):
        assert states[absent] == "NOT_IMPLEMENTED", absent
    for templated in ("Discussion", "Planning"):
        assert states[templated] == "MOCK_ONLY", templated
    for real in ("Execution", "TestExecution", "Audit"):
        assert states[real] == "IMPLEMENTED", real


# =================================================================================================
# 3. Verifier
# =================================================================================================


def run_verifier(cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", str(VERIFIER)],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_verifier_passes():
    result = run_verifier()
    assert "AT_M1_ARCHITECTURE_RESET_VERIFY: PASS" in result.stdout, result.stdout
    assert result.returncode == 0


def test_verifier_reports_a_measured_check_count():
    result = run_verifier()
    match = re.search(r"checks=(\d+) failures=(\d+)", result.stdout)
    assert match, result.stdout
    assert int(match.group(1)) >= 150
    assert int(match.group(2)) == 0


# =================================================================================================
# 4. Negative contract probes
# =================================================================================================
#
# Each probe applies ONE forbidden mutation to an in-memory copy of an artifact and asserts the
# corresponding contract condition stops holding. The control confirms the unmutated text passes,
# so a probe can never pass vacuously.


def _assert_probe(original: str, mutated: str, condition) -> None:
    """condition(text) -> bool must hold for the original and fail for the mutation."""
    assert mutated != original, "the mutation did not apply -- the probe would be vacuous"
    assert condition(original) is True, "control failed: the unmutated artifact does not hold"
    assert condition(mutated) is False, "the probe was NOT rejected"


def test_probe_untampered_control_passes():
    result = run_verifier()
    assert "AT_M1_ARCHITECTURE_RESET_VERIFY: PASS" in result.stdout
    assert result.returncode == 0


def test_probe_add_runtime_agent_to_task_roles_is_rejected():
    module = verifier_module()
    rbac = read("shared/sdk/tasks/rbac.py")
    mutated = rbac.replace('"requester",', '"requester",\n        "runtime_agent",')

    def human_only(text: str) -> bool:
        match = re.search(
            r"TASK_ROLES:\s*frozenset\[str\]\s*=\s*frozenset\(\s*\{(.*?)\}", text, re.DOTALL
        )
        roles = set(re.findall(r'"([a-z_]+)"', match.group(1))) if match else set()
        return "runtime_agent" not in roles and len(roles) == 6

    _assert_probe(rbac, mutated, human_only)
    # and the live source is genuinely unmutated
    assert module.task_roles_from_source() == {
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    }


def test_probe_second_autonomous_execution_source_is_rejected():
    lineage = read(LINEAGE)
    mutated = lineage.replace(
        "= SUBORDINATE HUMAN INTERACTION SURFACE",
        "= AUTONOMOUS EXECUTION SOURCE",
    )
    _assert_probe(
        lineage,
        mutated,
        lambda t: "SUBORDINATE HUMAN INTERACTION SURFACE" in t,
    )


def test_probe_mapping_team_decision_to_po_decision_is_rejected():
    collab = read(COLLAB)
    mutated = collab.replace(
        "The three MUST NOT share enums.",
        "A TeamDecision maps onto a ProductOwnerDecision value.",
    )
    _assert_probe(collab, mutated, lambda t: "MUST NOT share enums" in t)


def test_probe_storing_chain_of_thought_is_rejected():
    collab = read(COLLAB)
    mutated = collab.replace(
        "audit_ref                     the audit event recording this message",
        "audit_ref                     the audit event recording this message\n"
        "private_chain_of_thought      full internal reasoning",
    )

    def no_cot_in_schema(text: str) -> bool:
        schema = team_message_schema(text)
        return bool(schema) and "private_chain_of_thought" not in schema

    _assert_probe(collab, mutated, no_cot_in_schema)


def test_probe_making_template_planner_authoritative_is_rejected():
    planning = read(PLANNING)
    mutated = planning.replace("Canonical?        NO", "Canonical?        YES")
    _assert_probe(planning, mutated, lambda t: "Canonical?        NO" in t)


def test_probe_removing_plan_revision_versioning_is_rejected():
    planning = read(PLANNING)
    mutated = planning.replace("supersedes_revision_id", "previous_plan").replace(
        "Mutable-history overwrite is FORBIDDEN", "Revisions may be edited in place"
    )
    _assert_probe(
        planning,
        mutated,
        lambda t: "supersedes_revision_id" in t and "Mutable-history overwrite is FORBIDDEN" in t,
    )


def test_probe_treating_retry_as_debug_is_rejected():
    orchestration = read(ORCHESTRATION)
    mutated = orchestration.replace(
        "DLQ is a reliability mechanism. It is NOT an autonomous debugging model.",
        "DLQ is the autonomous debugging model.",
    )
    _assert_probe(
        orchestration,
        mutated,
        lambda t: "NOT an autonomous debugging model" in t,
    )


def test_probe_removing_debug_to_replan_back_edge_is_rejected():
    orchestration = read(ORCHESTRATION)
    mutated = orchestration.replace("DEBUGGING  --plan invalid-->   REPLANNING\n", "")
    _assert_probe(
        orchestration,
        mutated,
        lambda t: "DEBUGGING  --plan invalid-->   REPLANNING" in t,
    )


def test_probe_normalising_manual_assignment_is_rejected():
    human = read(f"{ARCH}/human-intervention-and-governance-boundary.md")
    mutated = human.replace(
        "| Assign an agent to work | **NO** |",
        "| Assign an agent to work | **YES** — expected |",
    )
    _assert_probe(
        human,
        mutated,
        lambda t: "| Assign an agent to work | **NO** |" in t,
    )


def test_probe_marking_pr28_canonical_is_rejected():
    evidence = read(EVIDENCE)
    # Both occurrences must be mutated: leaving one intact would let the probe pass vacuously.
    mutated = evidence.replace("HOLD / PRESERVE / NON-CANONICAL", "CANONICAL / MERGE APPROVED")
    assert evidence.count("HOLD / PRESERVE / NON-CANONICAL") >= 1
    _assert_probe(
        evidence,
        mutated,
        lambda t: "HOLD / PRESERVE / NON-CANONICAL" in t and "NON-CANONICAL" in t.upper(),
    )


def test_probe_modifying_delivery_review_enums_is_rejected():
    binding = read(BINDING)
    mutated = binding.replace(
        "Review Gate Actions (the six)", "Review Gate Actions (the seven, plus TEAM_ACCEPTED)"
    )
    _assert_probe(binding, mutated, lambda t: "Review Gate Actions (the six)" in t)


def test_probe_canonicalizing_permissive_clarification_expiry_is_rejected():
    binding = read(BINDING)
    mutated = binding.replace(
        "Decision:\n    DEFERRED", "Decision:\n    ACCEPTED -- agents proceed"
    )
    _assert_probe(
        binding,
        mutated,
        lambda t: "Decision:\n    DEFERRED" in t and "REMAINS AUTHORITATIVE" in t,
    )


def test_probe_adding_a_runtime_implementation_path_is_rejected():
    """A runtime path in scope must break the exact-set equality."""
    changed = changed_paths()
    mutated = changed | {"shared/sdk/autonomous_team/principal.py"}
    _assert_probe(
        "\n".join(sorted(changed)),
        "\n".join(sorted(mutated)),
        lambda t: set(t.splitlines()) == EXPECTED_PATHS,
    )


@pytest.mark.parametrize(
    "relpath",
    sorted(EXPECTED_PATHS),
)
def test_no_artifact_leaks_an_identifier(relpath):
    module = verifier_module()
    text = read(relpath)
    for pattern, label in module.LEAK_PATTERNS:
        assert re.search(pattern, text) is None, f"{relpath} leaks a {label}"


# =================================================================================================
# AT-M1-RM1 closure
# =================================================================================================


def test_rm1_baseline_is_repinned_to_post_gov1_main():
    """A-01: the AT-M1 baseline must be the post-GOV1 canonical main, exactly."""
    module = verifier_module()
    assert module.AT_M1_BASELINE == "fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009"
    assert module.AT_M1_BASELINE_SHORT == "fa5e5c4"
    assert AT_M1_BASELINE == module.AT_M1_BASELINE, "verifier and test baselines disagree"
    assert f'AT_M1_BASELINE = "{module.AT_M1_BASELINE}"' in read(
        "scripts/verify_at_m1_architecture_reset.py"
    )


def test_rm1_old_baseline_is_gone_from_current_at_m1_semantics():
    """Historical evidence prose may still cite the old baseline; current contracts must not.

    The SHA is assembled at runtime so this module can scan itself without self-matching.
    """
    old = "2d4da808" + "b1a89ea278fbb760e27f49047995165e"
    for relpath in (
        "tests/test_at_m1_architecture_reset.py",
        f"{ARCH}/at-m1-architecture-reset.md",
        BINDING,
        TERMINOLOGY,
        REGISTRY,
        ADRS,
    ):
        assert old not in read(relpath), f"{relpath} still pins the pre-GOV1 baseline"


def test_rm1_gov1_paths_are_absent_from_at_m1_positive_scope():
    """A-01 regression: GOV1's canonical paths must not contaminate AT-M1 scope."""
    changed = changed_paths()
    contamination = sorted(
        p for p in changed if "gov1" in p or p.startswith("scripts/verify_step66")
    )
    assert contamination == [], f"GOV1 paths leaked into AT-M1 scope: {contamination}"


def test_rm1_scope_is_exactly_nineteen_paths():
    assert len(EXPECTED_PATHS) == 19
    assert len(EXPECTED_PATHS - RM1_REGISTRATION_PATHS) == ORIGINAL_AT_M1_PATH_COUNT
    assert changed_paths() == EXPECTED_PATHS


def test_rm1_only_the_two_authorized_registration_paths_were_added():
    module = verifier_module()
    assert set(module.AT_M1_RM1_REGISTRATION_PATHS) == RM1_REGISTRATION_PATHS
    assert module.AT_M1_ORIGINAL_PATH_COUNT == ORIGINAL_AT_M1_PATH_COUNT
    assert set(module.AT_M1_EXPECTED_PATHS) == EXPECTED_PATHS


@pytest.mark.parametrize(
    "field",
    ["private_chain_of_thought", "raw_reasoning", "hidden_reasoning", "system_prompt", "secret"],
)
def test_rm1_inv04_verifier_rejects_a_contracted_hidden_reasoning_field(field):
    """INV-04 behavioral: a CONTRACTED field must be caught, not just prohibition prose."""
    module = verifier_module()
    collab = read(COLLAB)
    real = module.contracted_field_names(collab, "## 4. TeamMessage")
    assert len(real) >= 10, "the TeamMessage contract block was not parsed -- probe is vacuous"
    assert module.leaking_field_names(real) == [], "the live contract already leaks"
    mutated = (*real, field)
    assert module.leaking_field_names(mutated) == [field]


def test_rm1_inv04_prohibition_prose_alone_still_passes():
    """M-INV04-C: naming the fields in a prohibition list must NOT be a violation."""
    module = verifier_module()
    collab = read(COLLAB)
    assert "FORBIDDEN FIELDS" in collab
    for forbidden in module.FORBIDDEN_STORAGE_FIELDS:
        assert forbidden in collab, f"{forbidden} is no longer prohibited in prose"
    assert (
        module.leaking_field_names(module.contracted_field_names(collab, "## 4. TeamMessage")) == []
    )


@pytest.mark.parametrize(
    "line",
    [
        "PR #28 treatment: CANONICAL / ACTIVE / MERGE-READY -- adopted as a current dependency",
        "PR #28 treatment: CANONICAL -- current AT-M1 execution dependency",
        "PR #28 treatment: HOLD / PRESERVE / NON-CANONICAL -- MERGE-READY",
    ],
)
def test_rm1_inv08_semantic_canonicalization_is_rejected(line):
    """INV-08 structural: incidental NON-CANONICAL text elsewhere must not rescue these."""
    module = verifier_module()
    held = module.labelled_line(read(EVIDENCE), "PR #28 treatment:")
    assert not module.claims_canonical(held) and "MERGE-READY" not in held.upper()
    canonical_claim = module.claims_canonical(line)
    merge_ready = "MERGE-READY" in line.upper()
    assert canonical_claim or merge_ready, f"the probe line is not actually a violation: {line}"


def test_rm1_precedence_registration_is_scoped_and_preserves_66d():
    precedence = read(PRECEDENCE)
    assert "Autonomous Team architecture precedence" in precedence
    for decision in ("AT-D01", "AT-D02", "AT-D03", "AT-D04", "AT-D05"):
        assert decision in precedence
    for preserved in (
        "Review Gate Actions",
        "ProductOwnerDecision",
        "TASK_ROLES",
        "Delivery / Acceptance boundaries",
    ):
        assert preserved in precedence, f"{preserved} is not preserved against the AT family"
    assert "scoped precedence, not a global supersession" in re.sub(r"\s+", " ", precedence)


def test_rm1_milestone_registration_records_real_status():
    manifest = read(MANIFEST)
    assert "Autonomous Team milestones" in manifest
    for milestone in (
        "AT-M0",
        "AT-M1",
        "AT-M2",
        "AT-M3",
        "AT-M4",
        "AT-M5",
        "AT-M6",
        "AT-M7",
        "AT-M8",
    ):
        assert milestone in manifest
    flat = re.sub(r"\s+", " ", manifest)
    for milestone in ("AT-M2", "AT-M3", "AT-M4", "AT-M5", "AT-M6"):
        assert "NOT AUTHORIZED" in flat.split(milestone, 1)[1][:200], f"{milestone} not gated"
    assert "PENDING CANONICAL MERGE" in flat.upper(), "AT-M1 is claimed canonical before merge"
    assert "M0 — Source of Truth" in manifest, "the original M0..M7 track was disturbed"


def test_rm1_at_d09_remains_open_in_the_registration():
    """Target the AT-D09 statement: an unrelated line already contains the word OPEN."""
    module = verifier_module()
    precedence = read(PRECEDENCE)
    statement = module.line_with(precedence, "AT-D09")
    assert statement, "the precedence record does not mention AT-D09"
    assert "OPEN" in statement.upper() and "DEFERRED" in statement.upper()
    for closure in ("RESOLVED", "CLOSED", "BINDING", "ACCEPTED"):
        assert closure not in statement.upper(), f"AT-D09 claims {closure}: {statement!r}"
    # The document-wide form this replaces would pass even with AT-D09 closed.
    assert "OPEN" in precedence.replace(statement, ""), (
        "precondition for this test: an unrelated OPEN token must exist, proving the "
        "document-wide check was insufficient"
    )


def test_rm1_pr28_recorded_as_at_m7_input_not_a_dependency():
    for relpath in (PRECEDENCE, MANIFEST):
        text = read(relpath)
        assert "PR #28" in text and "AT-M7" in text
        assert "HOLD" in text.upper()


# =================================================================================================
# AT-M1-RM2 — R2 blocking defect closure (DEF-R2-01, DEF-R2-02)
# =================================================================================================

REGISTRY_PATH = REGISTRY
BINDING_PATH = BINDING


def _capability(name: str) -> dict:
    data = json.loads(read(REGISTRY_PATH))
    for entry in data.get("capabilities", []):
        if entry.get("capability") == name:
            return entry
    raise AssertionError(f"capability {name!r} is not in the registry")


def test_rm2_agent_principal_evidence_is_machine_true():
    """DEF-R2-01: the canonical registry must not claim principal_id has 0 occurrences."""
    entry = _capability("AgentPrincipal")
    evidence = entry["evidence"]
    assert entry["state"] == "CONTRACT_ONLY"
    assert "principal_id: 0 occurrences" not in evidence
    assert "ActorPrincipal: 0" in evidence
    assert "Actor.principal_id" in evidence and "authorization" in evidence.lower()


def test_rm2_handoff_evidence_is_machine_true():
    """DEF-R2-01: the canonical registry must not claim only 2 handoff matches."""
    entry = _capability("Handoff")
    evidence = entry["evidence"]
    assert entry["state"] == "NOT_IMPLEMENTED"
    assert "Only 2 matches" not in evidence
    assert "HandoffSummary" in evidence and "delivery_package" in evidence
    assert "work-transfer" in evidence and "absent" in evidence.lower()


def test_rm2_registry_evidence_matches_measured_repository_truth():
    """The corrected counts must be the ones actually measurable, not new invented numbers."""
    scope = ["apps", "shared", "agents", "services", "migrations"]
    principal = len(
        [ln for ln in git("grep", "-o", "principal_id", AT_M1_BASELINE, "--", *scope).splitlines()]
    )
    handoff = len(
        [ln for ln in git("grep", "-oi", "handoff", AT_M1_BASELINE, "--", *scope).splitlines()]
    )
    assert principal > 0 and handoff > 0, "measurement harness returned nothing"
    assert str(principal) in _capability("AgentPrincipal")["evidence"]
    assert str(handoff) in _capability("Handoff")["evidence"]


def test_rm2_capability_states_and_totals_unchanged_by_rm2():
    data = json.loads(read(REGISTRY_PATH))
    caps = data["capabilities"]
    counts: dict[str, int] = {}
    for entry in caps:
        counts[entry["state"]] = counts.get(entry["state"], 0) + 1
    assert len(caps) == 30
    assert counts == {
        "IMPLEMENTED": 7,
        "PARTIAL": 10,
        "MOCK_ONLY": 2,
        "CONTRACT_ONLY": 5,
        "NOT_IMPLEMENTED": 5,
        "DEFERRED": 1,
    }
    assert data["production_executed_true_count"] == 0


@pytest.mark.parametrize(
    "surface,mutated",
    [
        ("summary", "AT-D09:  RESOLVED / BINDING -- decided by AT-M1 (section 6)"),
        ("status", "STATUS:  RESOLVED / CLOSED -- decided by AT-M1"),
    ],
)
def test_rm2_at_d09_authoritative_surface_closure_is_detected(surface, mutated):
    """DEF-R2-02: closing an authoritative AT-D09 surface must be caught on that surface alone."""
    module = verifier_module()
    binding = read(BINDING_PATH)
    section = module.section_text(binding, "## 6. AT-D09")
    live = (
        module.labelled_line(binding, "AT-D09:")
        if surface == "summary"
        else module.labelled_line(section, "STATUS:")
    )
    assert live, f"the authoritative {surface} surface was not found"
    assert not module.claims_at_d09_closed(live), f"the live {surface} already claims closure"
    assert module.claims_at_d09_closed(mutated), f"the probe {surface} is not a closure claim"


def test_rm2_at_d09_decision_value_is_deferred():
    module = verifier_module()
    section = module.section_text(read(BINDING_PATH), "## 6. AT-D09")
    assert module.indented_value(section, "Decision:").upper() == "DEFERRED"


def test_rm2_at_d09_gate_is_not_satisfiable_by_unrelated_tokens():
    """The whole-document form this replaces would pass with every AT-D09 surface closed."""
    binding = read(BINDING_PATH)
    module = verifier_module()
    section = module.section_text(binding, "## 6. AT-D09")
    authoritative = "\n".join(
        [
            module.labelled_line(binding, "AT-D09:"),
            module.labelled_line(section, "STATUS:"),
            module.indented_value(section, "Decision:"),
        ]
    )
    residual = binding.replace(authoritative, "")
    # Unrelated OPEN / DEFERRED tokens exist, which is exactly why the old check was insufficient.
    assert "OPEN" in residual and "DEFERRED" in residual


def test_rm2_step_66c4_authority_is_preserved_in_the_at_d09_section():
    module = verifier_module()
    section = module.section_text(read(BINDING_PATH), "## 6. AT-D09")
    flat_section = re.sub(r"\s+", " ", section)
    assert "Step 66C.4 clarification expiry contract REMAINS AUTHORITATIVE" in flat_section
    assert "must not canonicalize permissive continuation" in flat_section
    assert "SUPERSEDED" not in section.upper() and "SUPERSEDES" not in section.upper()


def test_rm2_at_d09_remains_open_and_undecided():
    """RM2 must not decide AT-D09."""
    module = verifier_module()
    binding = read(BINDING_PATH)
    section = module.section_text(binding, "## 6. AT-D09")
    assert "OPEN" in module.labelled_line(binding, "AT-D09:").upper()
    assert "OPEN" in module.labelled_line(section, "STATUS:").upper()
    assert module.indented_value(section, "Decision:").upper() == "DEFERRED"
    assert "AT-D09" in read(PRECEDENCE)


def at_d09_status_surfaces(module, binding: str) -> dict[str, str]:
    """Every surface of the binding contract that states AT-D09's status.

    AT-M1-RM3 (DEF-R3-01): RM2 covered the first four. The section-8 authorization register and
    the section-6 heading marker also state the status, and a closure claim on either passed the
    verifier and the whole test module.
    """
    section = module.section_text(binding, "## 6. AT-D09")
    return {
        "summary": module.labelled_line(binding, "AT-D09:"),
        "status": module.labelled_line(section, "STATUS:"),
        "decision": module.indented_value(section, "Decision:"),
        "heading": module.line_with(binding, "## 6. AT-D09"),
        "register": module.labelled_line(
            module.section_text(binding, "## 8. Authorization status"), "AT_D09:"
        ),
    }


def test_rm3_section_8_authorization_register_records_at_d09_open():
    """DEF-R3-01: mutating this line to RESOLVED / BINDING left both gates green."""
    module = verifier_module()
    register = at_d09_status_surfaces(module, read(BINDING_PATH))["register"]
    assert register, "the section-8 authorization register has no AT_D09 line"
    assert "OPEN" in register.upper(), f"the register does not record AT-D09 as OPEN: {register!r}"
    assert not module.claims_at_d09_closed(register)
    assert module.claims_at_d09_closed("AT_D09:  RESOLVED / BINDING")


@pytest.mark.parametrize("surface", ["summary", "status", "decision", "heading", "register"])
def test_rm3_every_at_d09_status_surface_records_it_open(surface):
    module = verifier_module()
    live = at_d09_status_surfaces(module, read(BINDING_PATH))[surface]
    assert live, f"the authoritative {surface} surface was not found"
    assert not module.claims_at_d09_closed(live), f"the {surface} surface claims closure: {live!r}"
    expected = "DEFERRED" if surface == "decision" else "OPEN"
    assert expected in live.upper(), f"the {surface} surface is not {expected}: {live!r}"


CANONICAL_DOC = "docs/contracts/autonomous-team/at-binding-decisions.md"


def carriers_in(module, body, subject="at-d09", artifact=CANONICAL_DOC):
    """Drive the carrier protocol over a constructed canonical document."""
    return module.canonical_carriers(artifact, body, subject)


def verdicts_in(module, body, subject="at-d09", artifact=CANONICAL_DOC):
    return [
        module.carrier_verdict(kind, value)
        for _, _, _, kind, value in carriers_in(module, body, subject, artifact)
    ]


def rejects(module, body, subject="at-d09", artifact=CANONICAL_DOC):
    return any(verdicts_in(module, body, subject, artifact))


# =================================================================================================
# AT-D10 carrier protocol. Tests exercise protocol PROPERTIES on constructed documents rather than
# asserting the verifier's own output over the live corpus.
# =================================================================================================


def test_rm6_at_d10_is_canonicalized_as_a_binding_decision():
    binding = read(BINDING)
    assert "AT-D10:  RESOLVED / BINDING" in binding
    section = binding.split("## 9. AT-D10")[1]
    flat_section = re.sub(r"\s+", " ", section)
    assert "Free-form prose is NON-AUTHORITATIVE" in flat_section
    assert "structured carrier wins" in flat_section
    assert "FAILS CLOSED" in flat_section
    assert "never changes canonical state" in flat_section


def test_rm6_live_canonical_carriers_are_all_in_an_allowed_state():
    module = verifier_module()
    assert module.unauthorized_carriers("at-d09") == []
    assert module.unauthorized_carriers("at-m2") == []
    assert module.missing_required_carriers() == []
    assert module.contradicting_carriers("at-d09") == []
    assert module.contradicting_carriers("at-m2") == []


def test_rm6_every_required_carrier_kind_is_present_live():
    module = verifier_module()
    for artifact, subject, kind, form in module.REQUIRED_CARRIERS:
        found = {(k, f) for a, _, f, k, _ in module.domain_carriers(subject) if a == artifact}
        assert (kind, form) in found, f"{artifact} lost its {subject}/{kind}/{form} carrier"


# --- R6-B1: discovery must not be gated on vocabulary -------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["AT_D09_DISPOSITION", "AT_D09_OUTCOME", "AT_D09_STANDING", "AT_D09_VERDICT", "AT_D09_XYZZY"],
)
def test_rm6_qualified_key_is_a_carrier_whatever_its_noun(key):
    """The key's trailing noun must not decide whether the field is discovered."""
    module = verifier_module()
    body = f"# Doc\n\n```text\n{key}:  ENACTED\n```\n"
    found = carriers_in(module, body)
    assert found, f"{key} was not discovered as a carrier"
    assert rejects(module, body), f"{key}: ENACTED was discovered but not rejected"


@pytest.mark.parametrize("value", ["ENACTED", "DISCHARGED", "SEALED", "PROMULGATED", "ZZTOP"])
def test_rm6_unknown_value_on_a_carrier_fails_closed(value):
    """No unseen word appears in the verifier; rejection comes from failing to affirm OPEN."""
    module = verifier_module()
    body = f"# Doc\n\n```text\nAT_D09:  {value}\n```\n"
    assert rejects(module, body), f"unknown value {value!r} escaped"


def test_rm6_no_unseen_probe_word_is_present_in_the_verifier_source():
    source = read("scripts/verify_at_m1_architecture_reset.py").upper()
    probes = (
        "DISPOSITION",
        "ENACTED",
        "DISCHARGED",
        "SEALED",
        "PROMULGATED",
        "ZZTOP",
        # R7's independent probe words, and RM7's own.
        "ADJUDICATED",
        "QUIESCED",
        "CONSUMMATED",
        "INTERDICTED",
        "ABEYANCE",
        "POSTURE",
        "ABROGATED",
        "PERFECTED",
        "EXTINGUISHED",
    )
    for word in probes:
        assert word not in source, f"{word} leaked into the verifier as vocabulary"


# --- carrier shapes -----------------------------------------------------------------------------


def test_rm6_multiline_and_blank_line_values_are_read_completely():
    module = verifier_module()
    assert rejects(module, "# Doc\n\n```text\nAT_D09_STATE:\n    ENACTED\n```\n")
    assert rejects(module, "# Doc\n\n```text\nAT_D09_STATE:\n\n    ENACTED\n```\n")


def test_rm6_section_field_takes_its_subject_from_the_section():
    module = verifier_module()
    body = "## 6. AT-D09 - clarification expiry (OPEN)\n\n```text\nDECISION:  ENACTED\n```\n"
    assert rejects(module, body)


def test_rm6_undeclared_section_field_label_fails_closed():
    """An unknown labelled field inside a subject section is a carrier, not narrative."""
    module = verifier_module()
    body = "## 6. AT-D09 - clarification expiry (OPEN)\n\n```text\nDISPOSITION:  ENACTED\n```\n"
    assert rejects(module, body)


def test_rm6_declared_narrative_label_is_not_a_carrier():
    module = verifier_module()
    body = (
        "## 6. AT-D09 - clarification expiry (OPEN)\n\n```text\n"
        "UX suggestion under consideration:\n    an agent MAY proceed under a stated assumption\n"
        "```\n"
    )
    labels = [form for _, _, form, _, _ in carriers_in(module, body)]
    assert "section-field" not in labels
    assert not rejects(module, body)


def test_rm6_table_row_state_is_read_from_the_row_not_the_subject_cell():
    """ADV-R6-01: the state sits in a sibling cell, not the cell naming the subject."""
    module = verifier_module()
    body = "# Doc\n\n| Subject | State |\n| --- | --- |\n| AT-D09 | ENACTED |\n"
    found = carriers_in(module, body)
    assert found, "table row was not discovered"
    assert rejects(module, body)


# --- R6-B4: heading authority is deterministic --------------------------------------------------


def test_rm6_parenthesised_heading_marker_is_a_canonical_carrier():
    module = verifier_module()
    assert rejects(module, "## 6b. AT-D09 clarification expiry (RESOLVED)\n\nbody\n")


def test_rm6_dash_delimited_heading_is_not_a_canonical_carrier():
    """Declared outcome B: only the parenthesised marker binds. A title cannot change state."""
    module = verifier_module()
    body = "## 6b. AT-D09 clarification expiry - RESOLVED\n\nbody\n"
    assert [f for _, _, f, _, _ in carriers_in(module, body) if f == "heading-status"] == []
    assert not rejects(module, body)


def test_rm6_removing_a_required_heading_carrier_is_rejected_live():
    """The dash form cannot bind, so losing the parenthesised marker must fail as a MISSING carrier."""
    module = verifier_module()
    mutated = read(BINDING).replace(
        "## 6. AT-D09 — clarification expiry execution semantics (OPEN)",
        "## 6. AT-D09 — clarification expiry execution semantics - RESOLVED",
    )
    kinds = {k for _, _, f, k, _ in carriers_in(module, mutated) if f == "heading-status"}
    assert kinds == set(), "the dash heading must not be a carrier"


# --- free prose is not a canonical channel ------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "AT-D09 should now be treated as RESOLVED and BINDING by all downstream stages.",
        "AT-D09 henceforth stands ENACTED and governs expiry behaviour.",
        "It would be wrong to say AT-D09 is RESOLVED.",
        "No stage has recorded AT-D09 as RESOLVED.",
        "A prior draft claimed AT-D09 was RESOLVED; that claim was withdrawn.",
        "Whether AT-D09 is RESOLVED remains the open question.",
        "AT-D09 could be resolved in a future Product Owner decision.",
        "AT-D09 is recorded in section 6 of this contract.",
    ],
)
def test_rm6_prose_is_never_a_canonical_carrier(sentence):
    """Neither closure-looking nor criticism prose may bind or break canonical state."""
    module = verifier_module()
    body = f"# Doc\n\n{sentence}\n"
    assert carriers_in(module, body) == [], f"prose became a carrier: {sentence!r}"


def test_rm6_evidence_records_are_not_canonical_state_artifacts():
    module = verifier_module()
    body = "# Doc\n\n```text\nAT_D09:  RESOLVED / BINDING\n```\n"
    assert carriers_in(module, body, artifact=EVIDENCE) == []
    assert carriers_in(module, body) != [], "the same line must bind in a canonical artifact"


def test_rm6_prose_contradiction_advisory_is_non_blocking():
    module = verifier_module()
    notes = module.prose_contradiction_advisories("at-d09")
    assert isinstance(notes, list)
    # Advisories never participate in the verdict.
    assert module.unauthorized_carriers("at-d09") == []


# --- AT-M2 under the same protocol --------------------------------------------------------------


@pytest.mark.parametrize(
    "line,should_reject",
    [
        ("AT_M2:  AUTHORIZED", True),
        ("AT_M2:  AUTHORIZED (previously NOT AUTHORIZED)", True),
        ("AT_M2_IMPLEMENTATION:  AUTHORIZED", True),
        ("AT_M2:  NOT AUTHORIZED", False),
        # AT-D10.1 (RM7): the historical parenthetical is commentary inside the value. It used to
        # be tolerated as a qualifier; it is now non-atomic, and the explanation belongs outside.
        ("AT_M2:  NOT AUTHORIZED (previously AUTHORIZED)", True),
        ("AT-M2..AT-M8:  NOT AUTHORIZED", False),
    ],
)
def test_rm6_at_m2_authorization_carriers(line, should_reject):
    module = verifier_module()
    body = f"# Doc\n\n```text\n{line}\n```\n"
    assert rejects(module, body, subject="at-m2") is should_reject


def test_rm6_at_m2_prose_cannot_authorize():
    module = verifier_module()
    body = "# Doc\n\nAT-M2 is AUTHORIZED to begin implementation.\n"
    assert carriers_in(module, body, subject="at-m2") == []


# --- conflict and anti-vacuity ------------------------------------------------------------------


def test_rm6_contradictory_structured_carriers_are_detected():
    module = verifier_module()
    body = "# Doc\n\n```text\nAT_D09:  OPEN\nAT_D09_STATE:  NOT OPEN\n```\n"
    found = module.canonical_carriers(CANONICAL_DOC, body, "at-d09")
    polarity = {}
    for _, _, _, kind, value in found:
        for affirmed, term in module.propositions(value):
            polarity.setdefault((kind, term), set()).add(affirmed)
    assert any(len(seen) > 1 for seen in polarity.values()), "contradiction not observable"


def test_rm6_anti_vacuity_is_coverage_based_not_count_based():
    module = verifier_module()
    source = read("scripts/verify_at_m1_architecture_reset.py")
    assert "missing_required_carriers" in source
    assert module.REQUIRED_CARRIERS, "no required carriers declared"
    # Every declared requirement names an artifact inside the authorized scope.
    for artifact, _, _, _ in module.REQUIRED_CARRIERS:
        assert artifact in module.AT_M1_EXPECTED_PATHS


# =================================================================================================
# AT-D10.1 atomic canonical carrier value rule, and the structural key grammar that replaced the
# character whitelist. Tests exercise protocol PROPERTIES on constructed documents.
# =================================================================================================


def test_rm7_at_d10_1_is_canonicalized_as_a_binding_decision():
    binding = read(BINDING)
    assert "AT-D10.1:  RESOLVED / BINDING" in binding
    section = re.sub(r"\s+", " ", binding.split("## 10. AT-D10.1")[1])
    assert "expresses exactly ONE canonical proposition" in section
    assert "MUST NOT appear inside a canonical value" in section
    assert "FAILS CLOSED" in section
    assert "Explanation belongs OUTSIDE the carrier" in section
    assert "AT-D09 remains OPEN / DEFERRED" in section
    assert "AT-M2 remains NOT AUTHORIZED" in section


# --- DEF-R7-01: discovery must not depend on how the key is written -----------------------------


@pytest.mark.parametrize(
    "key",
    [
        "AT-D09 [tracking ref 4]",
        "AT_D09~~superseded marker~~",
        "AT-D09 status @ record 12",
        "at-d09 standing of record",
        'AT-D09 "field of record"',
        "AT-D09, entry of record",
        "AT-D09 — entry of record",
        "AT-D09 / expiry semantics",
        "AT-D09 entry. of record",
        "AT-D09 " + "an elaborated qualifier phrase " * 8,
    ],
)
def test_rm7_key_punctuation_and_length_never_hide_a_carrier(key):
    """DEF-R7-01: the key is whatever precedes the first colon. Nothing about how it is spelled,
    punctuated or how long it is may decide whether the line is discovered."""
    module = verifier_module()
    body = f"# Doc\n\n```text\n{key}:  ESTOPPED\n```\n"
    assert carriers_in(module, body), f"{key!r} was not discovered as a carrier"
    assert rejects(module, body), f"{key!r} was discovered but its value was not rejected"


@pytest.mark.parametrize("decorated", ["- {k}: ESTOPPED", "> {k}: ESTOPPED", "**{k}:** ESTOPPED"])
def test_rm7_markdown_decoration_is_formatting_not_grammar(decorated):
    module = verifier_module()
    body = "# Doc\n\n```text\n" + decorated.format(k="AT_D09_STANDING") + "\n```\n"
    assert carriers_in(module, body), f"{decorated!r} was not discovered"
    assert rejects(module, body)


def test_rm7_key_grammar_holds_no_character_class():
    """The regression that made DEF-R7-01 possible was a whitelist on the qualifier's characters.

    keyed_field splits at the first colon, so a key made only of characters no author would
    anticipate is still a key.
    """
    module = verifier_module()
    assert module.keyed_field("AT-D09 <#%^&*>{}[]|+=~: ESTOPPED") == (
        "AT-D09 <#%^&*>{}[]|+=~",
        " ESTOPPED",
    )
    assert module.keyed_field("no colon here at all") is None


def test_rm7_a_line_that_does_not_begin_with_the_subject_is_not_a_carrier():
    """Subject membership is decided by the key, not by mentioning the subject somewhere."""
    module = verifier_module()
    body = "# Doc\n\n```text\nNOTE about AT-D09:  RESOLVED / BINDING\n```\n"
    assert carriers_in(module, body) == []


# --- DEF-R7-02 / AT-D10.1: one carrier, one proposition -----------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "OPEN / DEFERRED; RESOLVED / BINDING",
        "OPEN -- amended, now CLOSED",
        "OPEN — now RESOLVED",
        "OPEN – now RESOLVED",
        "OPEN (previously RESOLVED)",
        "OPEN [see section 6]",
        "OPEN -- see section 6 for context",
        "OPEN. This remains undecided",
        "DEVOLVED -- as recorded above",
    ],
)
def test_rm7_multi_clause_canonical_values_fail_closed(value):
    """The rule is atomicity. An allowed head no longer shields whatever follows it, and no
    clause is discarded to reach a readable value."""
    module = verifier_module()
    assert module.atomicity_verdict(value), f"{value!r} was accepted as atomic"
    assert rejects(module, f"# Doc\n\n```text\nAT_D09:  {value}\n```\n")


@pytest.mark.parametrize("value", ["OPEN", "OPEN / DEFERRED", "DEFERRED", "NOT AUTHORIZED"])
def test_rm7_clean_atomic_values_remain_valid(value):
    """A slash-separated compound is ONE proposition; atomicity must not reject valid truth."""
    module = verifier_module()
    assert module.atomicity_verdict(value) == ""


def test_rm7_the_complete_value_reaches_validation():
    """DEF-R7-02: nothing is truncated before validation, so a second line is a second clause."""
    module = verifier_module()
    single = "# Doc\n\n```text\nAT_D09_STANDING:\n    OPEN\n```\n"
    doubled = "# Doc\n\n```text\nAT_D09_STANDING:\n    OPEN\n    RESOLVED / BINDING\n```\n"
    assert not rejects(module, single)
    assert rejects(module, doubled), "a continuation line was dropped before validation"


def test_rm7_an_empty_carrier_value_fails_closed():
    module = verifier_module()
    assert module.atomicity_verdict("   ")
    assert module.carrier_verdict("status", "")


def test_rm7_two_heading_markers_are_two_propositions():
    module = verifier_module()
    assert not rejects(module, "## 6b. AT-D09 clarification expiry (OPEN)\n\nbody\n")
    assert rejects(module, "## 6b. AT-D09 clarification expiry (OPEN) (now RESOLVED)\n\nbody\n")


def test_rm7_live_canonical_carriers_are_all_atomic():
    module = verifier_module()
    for subject in ("at-d09", "at-m2"):
        for artifact, line, form, _, value in module.domain_carriers(subject):
            assert (
                module.atomicity_verdict(value) == ""
            ), f"{artifact}:{line} [{form}] carries a non-atomic value {value!r}"


# --- the RM6 guarantees must survive the RM7 grammar change -------------------------------------


@pytest.mark.parametrize("value", ["ESTOPPED", "DEVOLVED", "MOOTED"])
def test_rm7_unknown_atomic_values_still_fail_closed(value):
    """Atomicity did not replace allowed-state validation: an atomic unknown is still rejected."""
    module = verifier_module()
    assert module.atomicity_verdict(value) == "", "the probe value must itself be atomic"
    assert rejects(module, f"# Doc\n\n```text\nAT_D09:  {value}\n```\n")


@pytest.mark.parametrize(
    "line,should_reject",
    [
        ("AT_M2:  NOT AUTHORIZED", False),
        ("AT_M2:  AUTHORIZED", True),
        ("AT_M2:  NOT AUTHORIZED; AUTHORIZED", True),
        ("AT_M2:  MOOTED", True),
        ("AT-M2, entry of record:  AUTHORIZED", True),
        ("AT-M2..AT-M8:  NOT AUTHORIZED", False),
    ],
)
def test_rm7_at_m2_under_the_atomic_protocol(line, should_reject):
    module = verifier_module()
    body = f"# Doc\n\n```text\n{line}\n```\n"
    assert rejects(module, body, subject="at-m2") is should_reject


@pytest.mark.parametrize(
    "sentence",
    [
        "The Product Owner has now CLOSED the expiry question.",
        "Downstream stages MUST treat the expiry question as CLOSED.",
        "An earlier draft of this record marked the question RESOLVED.",
        "A later decision COULD mark the question RESOLVED and BINDING.",
        "Calling the expiry question SETTLED misreads this record.",
        'Someone wrote "the question is RESOLVED"; that was wrong.',
    ],
)
def test_rm7_prose_is_still_never_a_canonical_carrier(sentence):
    module = verifier_module()
    assert carriers_in(module, f"# Doc\n\n{sentence}\n") == []


def test_rm7_a_sentence_inside_a_subject_section_is_not_a_section_field():
    """A label binds only inside a fenced block: without the subject in the key, the fence is the
    structure that separates a canonical field from a sentence containing a colon."""
    module = verifier_module()
    body = (
        "## 6. AT-D09 - clarification expiry (OPEN)\n\n"
        "Note: this paragraph asserts no governance state.\n"
    )
    assert [f for _, _, f, _, _ in carriers_in(module, body) if f == "section-field"] == []
    body_fenced = "## 6. AT-D09 - clarification expiry (OPEN)\n\n```text\nSTATUS:  MOOTED\n```\n"
    assert rejects(module, body_fenced)


def test_rm7_structured_conflict_detection_survives():
    module = verifier_module()
    body = "# Doc\n\n```text\nAT_D09:  OPEN\nAT_D09_STANDING:  NOT OPEN\n```\n"
    polarity: dict[tuple[str, str], set[bool]] = {}
    for _, _, _, kind, value in carriers_in(module, body):
        for affirmed, term in module.propositions(value):
            polarity.setdefault((kind, term), set()).add(affirmed)
    assert any(len(seen) > 1 for seen in polarity.values())


def test_rm7_anti_vacuity_stays_form_granular_and_tolerates_redundancy():
    """Coverage is (artifact, subject, kind, FORM). A redundant restatement is not itself
    required; losing the whole category is."""
    module = verifier_module()
    assert all(len(required) == 4 for required in module.REQUIRED_CARRIERS)
    assert module.missing_required_carriers() == []
    registers = [
        (a, line)
        for a, line, form, kind, _ in module.domain_carriers("at-d09")
        if (a, kind, form) == (BINDING, "status", "register")
    ]
    assert len(registers) > 1, "the redundancy this test describes no longer exists"
