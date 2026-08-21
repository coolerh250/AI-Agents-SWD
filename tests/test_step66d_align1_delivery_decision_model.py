"""Tests for Step 66D-ALIGN1 delivery decision model alignment.

Offline by design: no container, no database, no network, no secret access. Several tests re-derive
their claims from Git objects or repository source rather than asserting that a document agrees
with itself.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: the rejection window ends where an authorized successor milestone
# takes over; without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import live_guard_changed_paths  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def live_guard_changed_paths(baseline: str) -> list[str]:
        """Strictest fallback: with no lifecycle module nothing is exempt."""
        current = "HEAD"
        return [
            line.strip().replace("\\", "/")
            for line in _git("diff", "--name-only", baseline, current).splitlines()
            if line.strip()
        ]

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66d_align1_delivery_decision_model.py"

CONTRACTS = REPO / "docs" / "contracts" / "66d-delivery-acceptance"
HANDOFFS = REPO / "docs" / "handoffs" / "66d-delivery-acceptance"
MASTER = REPO / "docs" / "alignment" / "66-project-completion" / "master"
SYNC = REPO / "docs" / "handoffs" / "program-sync"

BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"
TERMS = CONTRACTS / "step66d-canonical-terminology-registry.md"
MATRIX = HANDOFFS / "step66d-canonical-conflict-supersession-matrix.md"
GAPS = HANDOFFS / "step66d-align1-gap-register.md"
RETRY = HANDOFFS / "step66d-arch1-retry-readiness.md"
EVIDENCE = REPO / "docs" / "test" / "step66d-align1-canonical-alignment-evidence.md"

GATES = MASTER / "product-and-technical-gates.md"
DOD = MASTER / "project-definition-of-done.md"
MILESTONES = MASTER / "canonical-milestone-manifest.md"
PLAN = MASTER / "project-completion-master-plan.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"

DESIGN_SPEC = REPO / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"
UX_GAPS = SYNC / "step66sync1-claude-design-ux-gap-register.md"
POC0_GAPS = SYNC / "step66sync1-poc0-consolidated-gap-register.md"

CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ANNOTATION_MARKER = "<!-- SUPERSESSION-NOTE-BEGIN: Step 66D-ALIGN1 -->"

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
DECISIONS = ("66D-D01", "66D-D02", "66D-D03", "66D-D04")
CONFLICTS = ("66D-CONFLICT-01", "66D-CONFLICT-02", "66D-CONFLICT-03", "66D-CONFLICT-04")
ANNOTATED = (DESIGN_SPEC, UX_GAPS, POC0_GAPS)
ENTITIES = (
    "DeliverySubmission",
    "DeliveryReviewTask",
    "DeliveryReviewAction",
    "ProductOwnerDecision",
    "AcceptanceFollowUpItem",
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _enum(kind: str) -> tuple[str, ...]:
    pattern = rf"### {kind}\n\n```text\n(.*?)```"
    match = re.search(pattern, _read(BINDING), re.DOTALL)
    assert match is not None, kind
    return tuple(line.strip() for line in match.group(1).splitlines() if line.strip())


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
    assert "STEP66D_ALIGN1_DELIVERY_DECISION_MODEL_VERIFY: PASS" in result.stdout


def test_canonical_baseline_is_ancestor() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"], cwd=REPO, check=False
    )
    assert result.returncode == 0


# --- binding decisions ----------------------------------------------------------------------


def test_all_four_decisions_present() -> None:
    binding = _read(BINDING)
    for decision in DECISIONS:
        assert decision in binding, decision


def test_all_four_decisions_are_binding() -> None:
    binding = _read(BINDING)
    for decision in DECISIONS:
        assert re.search(rf"^{decision}:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE), decision


def test_decision_authority_and_date() -> None:
    binding = _read(BINDING)
    assert "DECISION_AUTHORITY:\nProduct Owner" in binding
    assert "DECISION_DATE:\n2026-08-04" in binding
    assert "main 64467fe" in binding


# --- 66D-D01: layered model -------------------------------------------------------------------


def test_exactly_six_review_gate_actions() -> None:
    assert _enum(r"Review Gate Action \(exactly six\)") == REVIEW_ACTIONS


def test_exactly_three_final_decisions() -> None:
    assert _enum(r"Product Owner Final Decision \(exactly three\)") == FINAL_DECISIONS


def test_the_two_enums_are_disjoint_except_by_design() -> None:
    actions = set(_enum(r"Review Gate Action \(exactly six\)"))
    decisions = set(_enum(r"Product Owner Final Decision \(exactly three\)"))
    assert actions & decisions == set(), "the two enums must not share a value"


def test_review_actions_never_enter_the_decision_enum() -> None:
    decisions = _enum(r"Product Owner Final Decision \(exactly three\)")
    for forbidden in ("REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"):
        assert forbidden not in decisions, forbidden


def test_accepted_with_follow_up_never_enters_the_action_enum() -> None:
    assert "ACCEPTED_WITH_FOLLOW_UP" not in _enum(r"Review Gate Action \(exactly six\)")


def test_all_seven_separation_requirements_recorded() -> None:
    binding = _read(BINDING)
    for index in range(1, 10):
        assert f"D01-R{index}" in binding, f"D01-R{index}"


def test_mapping_table_covers_every_review_action() -> None:
    binding = _read(BINDING)
    table = re.search(r"\| Review Gate Action \|.*?(?=\n\n)", binding, re.DOTALL)
    assert table is not None
    body = table.group(0)
    for action in REVIEW_ACTIONS:
        assert f"`{action}`" in body, action
    assert body.count("| none |") == 4, "exactly four actions must carry no final decision"


# --- 66D-D02: lifecycle -----------------------------------------------------------------------


def test_delivery_review_status_may_project_outcomes() -> None:
    values = _enum(r"Delivery review status \(permitted values\)")
    for expected in ("ACCEPTED", "REJECTED", "CHANGES_REQUESTED", "QA_RERUN_REQUESTED"):
        assert expected in values, expected


def test_decision_record_is_immutable_and_supersedable() -> None:
    flat = _flat(_read(BINDING))
    assert "ProductOwnerDecision must never be overwritten in place." in flat
    assert "supersedes_decision_id" in flat
    assert "Decision history must never be deleted." in flat


def test_status_is_a_projection_not_the_record() -> None:
    assert "projection of the current effective decision" in _flat(_read(BINDING))


def test_accepted_with_follow_up_is_non_blocking_only() -> None:
    flat = _flat(_read(BINDING))
    assert "ACCEPTED_WITH_FOLLOW_UP may contain only non-blocking follow-up items." in flat
    assert "ACCEPTED_WITH_FOLLOW_UP projects to delivery review status ACCEPTED." in flat


def test_blocking_follow_up_forces_request_changes() -> None:
    flat = _flat(_read(BINDING))
    assert "Whenever a blocking follow-up exists, REQUEST_CHANGES must be used instead." in flat


def test_acceptance_is_not_production_approval() -> None:
    flat = _flat(_read(BINDING))
    assert "Acceptance is not production approval." in flat
    assert "does not bypass security, identity, deployment or production gates" in flat


def test_agent_completion_is_not_acceptance() -> None:
    flat = _flat(_read(BINDING))
    assert "not equivalent to Product Owner acceptance" in flat


def test_superseded_lifecycle_statement_is_recorded_as_superseded() -> None:
    """The earlier 'no acceptance in the lifecycle at all' rule must be visibly superseded."""
    binding = _read(BINDING)
    assert "### Superseded statement" in binding
    assert "is superseded" in _flat(binding)


# --- 66D-D03: anchors -------------------------------------------------------------------------


def test_execution_lineage_recorded() -> None:
    flat = _flat(_read(BINDING))
    assert "project_id -> work_item_id -> workflow_id -> run_id" in flat
    assert "Agent execution source of truth" in flat


def test_human_review_anchor_recorded() -> None:
    binding = _read(BINDING)
    assert "delivery_review_task_id" in binding
    assert "Task is the human-review and RBAC anchor." in _flat(binding)


def test_task_is_not_the_execution_source_of_truth() -> None:
    flat = _flat(_read(BINDING))
    assert "Task is not the Agent execution source of truth." in flat


def test_d1_binding_decision_is_preserved() -> None:
    """66D-D03 must not weaken the existing D-1 decision, which is still on main."""
    flat = _flat(_read(BINDING))
    assert "Dedicated POC Development Goal -> Project -> Work Item -> Workflow / Run" in flat
    d1 = _read(SYNC / "step66sync1-poc-scope-binding-decisions.md")
    assert "The existing Task API and Task UI remain non-dispatching." in d1


def test_task_roles_named() -> None:
    binding = _read(BINDING)
    assert "reviewer_approver" in binding
    assert "pm_engineering_lead" in binding


# --- 66D-D04: entity naming --------------------------------------------------------------------


def test_legacy_delivery_package_preserved() -> None:
    binding = _read(BINDING)
    assert "legacy Platform Ops evidence package" in _flat(binding)
    for req in ("D04-R1", "D04-R2", "D04-R3", "D04-R4"):
        assert req in binding, req


def test_legacy_delivery_package_source_untouched() -> None:
    """Re-derived from Git: no legacy source file may be modified by this stage."""
    changed = live_guard_changed_paths(CANONICAL_MAIN)
    assert [p for p in changed if "delivery_package" in p.lower()] == []
    assert [p for p in changed if "DeliveryPackage" in p] == []


def test_legacy_delivery_package_still_exists_in_the_repository() -> None:
    """The name collision is real only if the legacy object is actually there."""
    assert (REPO / "apps" / "orchestrator" / "src" / "delivery_package_api.py").is_file()
    assert (REPO / "docs" / "product" / "delivery-package-acceptance-gate.md").is_file()


def test_all_five_new_entities_named() -> None:
    binding = _read(BINDING)
    for entity in ENTITIES:
        assert entity in binding, entity


def test_every_entity_has_a_terminology_entry() -> None:
    terms = _read(TERMS)
    for entity in ENTITIES + ("DeliveryPackage",):
        assert f"## {entity}" in terms, entity


def test_terminology_entries_have_all_required_fields() -> None:
    terms = _read(TERMS)
    for field in (
        "Canonical definition:",
        "Not to be confused with:",
        "Authoritative source:",
        "Future implementation owner:",
    ):
        assert terms.count(field) >= 13, field


def test_product_surface_names_recorded() -> None:
    binding = _read(BINDING)
    assert "Delivery Inbox" in binding
    assert "Delivery Review" in binding


# --- active canonical alignment ------------------------------------------------------------------


def test_gates_document_has_a_separate_decision_gate() -> None:
    gates = _read(GATES)
    assert "Product Owner Decision Gate" in gates
    assert "6-action Review Gate" in gates
    assert "ACCEPTED_WITH_FOLLOW_UP" in gates


def test_definition_of_done_requires_all_seven_sub_criteria() -> None:
    dod = _flat(_read(DOD)).lower()
    for fragment in (
        "review gate action contract complete",
        "product owner final decision contract complete",
        "bounded qa rerun rule complete",
        "blocking versus non-blocking follow-up rule complete",
        "immutable decision history complete",
        "dual-anchor traceability complete",
        "legacy/new entity separation complete",
    ):
        assert fragment in dod, fragment


def test_milestone_manifest_requires_the_new_entities() -> None:
    manifest = _read(MILESTONES)
    for entity in ENTITIES:
        assert entity in manifest, entity
    assert "legacy `DeliveryPackage` remains the Step 47/49 Platform Ops evidence object" in _flat(
        manifest
    )


def test_milestone_manifest_records_the_projection_rule() -> None:
    assert "projection of the current effective" in _flat(_read(MILESTONES))


def test_master_plan_references_the_binding_decisions() -> None:
    assert "66D-D01..66D-D04" in _read(PLAN)


def test_precedence_index_records_the_supersession_rule() -> None:
    flat = _flat(_read(PRECEDENCE))
    assert "66D-D01..66D-D04 RESOLVED / BINDING" in flat
    assert (
        "binding decision record supersedes conflicting active terminology without rewriting "
        "historical evidence" in flat
    )


# --- historical preservation ----------------------------------------------------------------------


def test_every_annotated_file_carries_the_marker() -> None:
    for path in ANNOTATED:
        assert ANNOTATION_MARKER in _read(path), path.name


def test_annotations_deleted_no_lines() -> None:
    for path in ANNOTATED:
        rel = path.relative_to(REPO).as_posix()
        numstat = _git("diff", "--numstat", CANONICAL_MAIN, "--", rel)
        assert numstat, rel
        added, deleted = numstat.split("\t")[:2]
        assert deleted == "0", f"{rel} deleted {deleted} lines"
        assert int(added) > 0, rel


def test_design_spec_note_separates_the_two_layers() -> None:
    note = _flat(_read(DESIGN_SPEC).partition(ANNOTATION_MARKER)[2])
    assert "Review Gate Action -- exactly six" in note
    assert "Product Owner Final Decision -- exactly three" in note
    assert "REQUEST_CHANGES != RERUN_QA" in note
    assert "ACCEPTED_WITH_FOLLOW_UP requires at least one NON-BLOCKING follow-up" in note
    assert "The Delivery Inbox is task-anchored" in note
    assert "Execution evidence remains project/work-item/workflow/run anchored" in note


def test_design_spec_original_only_these_three_text_survives() -> None:
    """The original sentence must remain -- it is scoped, not deleted."""
    head = _read(DESIGN_SPEC).partition(ANNOTATION_MARKER)[0]
    assert "Product Owner decision (only these three)" in head


def test_design_spec_note_keeps_ia_options_unselected() -> None:
    note = _flat(_read(DESIGN_SPEC).partition(ANNOTATION_MARKER)[2])
    assert "Neither is selected" in note


def test_gap_register_notes_close_no_gap() -> None:
    for path in (UX_GAPS, POC0_GAPS):
        note = _flat(_read(path).partition(ANNOTATION_MARKER)[2])
        for conflict in CONFLICTS:
            assert conflict in note, f"{path.name}: {conflict}"
    poc0 = _flat(_read(POC0_GAPS).partition(ANNOTATION_MARKER)[2])
    assert "No gap in this register is closed" in poc0
    assert "Authorized: 0 of 23** remains correct" in poc0


# --- supersession matrix ----------------------------------------------------------------------------


def test_matrix_covers_all_four_conflicts() -> None:
    matrix = _read(MATRIX)
    for conflict in CONFLICTS:
        assert conflict in matrix, conflict


def test_matrix_records_paths_and_meanings() -> None:
    matrix = _read(MATRIX)
    assert matrix.count("Old effective meaning:") >= 8
    assert matrix.count("New binding meaning:") >= 8
    assert matrix.count("Historical preservation") >= 8


def test_matrix_explains_the_files_left_unedited() -> None:
    matrix = _read(MATRIX)
    assert "NOT edited (deliberately)" in matrix
    assert "next-executable-stage-sequence.md" in matrix


# --- QA rerun boundary --------------------------------------------------------------------------------


def test_qa_rerun_count_is_deferred_not_decided() -> None:
    flat = _flat(_read(BINDING))
    assert "deferred to Step 66D-ARCH contract freeze. NOT decided in this stage." in flat


def test_no_numeric_rerun_bound_was_fixed() -> None:
    binding = _read(BINDING)
    for pattern in (r"maximum rerun count\s*[:=]\s*\d", r"cooldown\s*[:=]\s*\d"):
        assert re.search(pattern, binding, re.IGNORECASE) is None, pattern


# --- authorization state ---------------------------------------------------------------------------------


def test_every_downstream_stage_is_unauthorized() -> None:
    binding = _read(BINDING)
    for label in ("STEP66D_ARCH1", "STEP66D_DESIGN", "STEP67POC0", "RA2I0"):
        assert re.search(
            rf"^{label}:\s+NOT STARTED / NOT AUTHORIZED$", binding, re.MULTILINE
        ), label


def test_retry_readiness_is_not_authorization() -> None:
    retry = _read(RETRY)
    assert "READY_FOR_PRODUCT_OWNER_AUTHORIZATION" in retry
    assert "Readiness is not authorization." in retry
    assert re.search(r"^STEP66D_ARCH1:\n\s*NOT STARTED / NOT AUTHORIZED$", retry, re.MULTILINE)


def test_binding_record_lists_prohibited_implications() -> None:
    binding = _read(BINDING)
    for phrase in (
        "Contracts are already frozen",
        "Step 66D-ARCH is complete",
        "DeliverySubmission is implemented",
        "Delivery Inbox is implemented",
        "The PO decision API is implemented",
        "TASK_ROLES has been updated",
    ):
        assert phrase in binding, phrase


def test_gap_register_authorizes_nothing() -> None:
    gaps = _read(GAPS)
    assert "Authorized: 0 of 10" in gaps
    assert "Implemented:           0" in gaps
    for index in range(1, 11):
        assert f"ALIGN1-G{index:02d}" in gaps, index


def test_be3_gates_still_default_false() -> None:
    resume = _read(REPO / "shared" / "sdk" / "tasks" / "resume_request_model.py")
    replay = _read(REPO / "shared" / "sdk" / "tasks" / "replay_request_model.py")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in replay
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in replay


# --- scope boundary -------------------------------------------------------------------------------------------


def _changed() -> list[str]:
    return live_guard_changed_paths(CANONICAL_MAIN)


def test_no_runtime_backend_or_agent_source_changed() -> None:
    forbidden = ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/")
    assert [p for p in _changed() if p.startswith(forbidden)] == []


def test_no_frontend_source_changed() -> None:
    suffixes = (".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss")
    assert [p for p in _changed() if p.endswith(suffixes)] == []


def test_no_manifest_compose_or_chart_changed() -> None:
    assert [
        p
        for p in _changed()
        if "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
        or p.endswith((".yaml", ".yml"))
    ] == []


def _verifier_module():
    """The verifier loaded as a module, so this test uses ITS admission rule, not a copy.

    GOV-STAGE-FAMILY-ALLOWLIST-01 (Step AT-M1-GOV1): this test previously restated the allowlist
    inline, giving two independent rules that could drift apart. There is now exactly one.
    """
    spec = importlib.util.spec_from_file_location("step66d_align1_verifier", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_paths_are_within_scope() -> None:
    is_admitted = _verifier_module().is_admitted_current_state_path
    assert [p for p in _changed() if not is_admitted(p)] == []


def test_current_state_admission_is_not_a_broad_path_allowlist() -> None:
    """A file being under scripts/ or tests/ must never be sufficient on its own."""
    is_admitted = _verifier_module().is_admitted_current_state_path
    for rejected in (
        "scripts/at_runtime_patch.py",
        "scripts/random_helper.py",
        "tests/at_random_helper.py",
        "tests/random_test_helper.py",
        "scripts/verify_.py",
        "tests/test_.py",
        "scripts/nested/verify_thing.py",
        "shared/sdk/tasks/rbac.py",
        "apps/orchestrator/src/main.py",
        "agents/qa-agent/src/agent.py",
        "migrations/037_example.sql",
        "infra/docker-compose/docker-compose.yml",
        ".github/workflows/ci.yml",
        "",
    ):
        assert not is_admitted(rejected), rejected


def test_governance_artifacts_are_admitted_by_domain_not_by_family() -> None:
    """GOV-DOMAIN-ADMISSION-01. Admission may not depend on the stage family in the name.

    The last two entries are families that do not exist in this repository. Under the previous
    registry model each of them had to be added by hand before it could land, which is how this
    defect recurred; under the domain rule they are already admitted.
    """
    is_admitted = _verifier_module().is_admitted_current_state_path
    for accepted in (
        "scripts/verify_step66d_align1_delivery_decision_model.py",
        "tests/test_step66d_align1_delivery_decision_model.py",
        "scripts/verify_at_m1_architecture_reset.py",
        "tests/test_at_m1_architecture_reset.py",
        "scripts/verify_at_m2_team_identity_collaboration.py",
        "tests/test_at_m2_team_identity_collaboration.py",
        "scripts/verify_pcp_v2_control_plane.py",
        "tests/test_pcp_v2_control_plane.py",
        "scripts/verify_unregistered_family.py",
        "tests/test_unregistered_family.py",
        "scripts/verify_zzz_family_nobody_has_invented_yet.py",
        "tests/test_zzz_family_nobody_has_invented_yet.py",
        "docs/anything/at/all.md",
        "source/progress.md",
    ):
        assert is_admitted(accepted), accepted


def test_admission_consults_no_stage_family_registry() -> None:
    """The registry must not merely be unused -- it must be gone, so it cannot come back."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "REGISTERED_GOVERNANCE_FAMILIES" not in source
    assert "step66" not in source.split("GOVERNANCE_ARTIFACT_PATTERNS")[1].split(")")[0]


def test_production_executed_true_count_is_zero_everywhere() -> None:
    for path in (BINDING, TERMS, MATRIX, GAPS, RETRY, EVIDENCE):
        text = _read(path)
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            assert value == "0", path.name


def test_evidence_document_records_the_marker() -> None:
    assert "STEP66D_ALIGN1_DELIVERY_DECISION_MODEL_VERIFY: PASS" in _read(EVIDENCE)


def test_evidence_discloses_the_stage_allowlist_repair() -> None:
    evidence = _read(EVIDENCE)
    assert "Pre-existing stage-allowlist regression" in evidence
    assert "9 failed, 479 passed" in evidence
