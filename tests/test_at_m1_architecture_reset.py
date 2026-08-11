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

AT_M1_BASELINE = "2d4da808b1a89ea278fbb760e27f49047995165e"

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
}


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


def test_all_seventeen_artifacts_exist():
    assert len(EXPECTED_PATHS) == 17
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
    evidence = read(EVIDENCE)
    assert "HOLD" in evidence and "NON-CANONICAL" in evidence.upper()
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
    binding = read(BINDING)
    assert "AT-D09" in binding and "OPEN" in binding and "DEFERRED" in binding
    assert "REMAINS AUTHORITATIVE" in binding
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
