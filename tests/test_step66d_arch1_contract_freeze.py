"""Tests for Step 66D-ARCH1 delivery and acceptance contract freeze.

Offline by design: no container, no database, no network, no secret access. Several tests parse
the frozen contracts and re-derive their claims rather than asserting a document agrees with itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import pathlib

# AT-M2 remediation: the rejection window ends where an authorized successor milestone
# takes over; without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import successor_window_end  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def successor_window_end(_baseline: str = "") -> str:
        """Strictest fallback: with no lifecycle module the window stays HEAD-relative."""
        return "HEAD"

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66d_arch1_contract_freeze.py"

CANONICAL_MAIN = "ccfee8ef47f72d5d67ea6bb58845018f306cfa0c"

ARCH = REPO / "docs" / "architecture" / "66d-delivery-acceptance"
HANDOFFS = REPO / "docs" / "handoffs" / "66d-delivery-acceptance"

FREEZE = ARCH / "step66d-arch1-contract-freeze.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
APIDOC = ARCH / "step66d-arch1-api-event-audit-contracts.md"
READMODEL = ARCH / "step66d-arch1-read-model-and-security-boundary.md"
ADRS = REPO / "docs" / "decisions" / "step66d-arch1-architecture-decisions.md"
INVENTORY = HANDOFFS / "step66d-arch1-existing-capability-inventory.md"
SLICES = HANDOFFS / "step66d-arch1-gap-and-implementation-slice-plan.md"
EVIDENCE = REPO / "docs" / "test" / "step66d-arch1-contract-freeze-evidence.md"

ALL_DOCS = (FREEZE, DOMAIN, APIDOC, READMODEL, ADRS, INVENTORY, SLICES, EVIDENCE)

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "QA_RERUN_REQUESTED",
    "ACCEPTED",
    "REJECTED",
    "ARCHIVED",
    "EXPIRED",
)
ENTITIES = (
    "DeliverySubmission",
    "DeliveryReviewTask",
    "DeliveryReviewAction",
    "ProductOwnerDecision",
    "AcceptanceFollowUpItem",
)
RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    return result.stdout.decode("utf-8").strip() if result.returncode == 0 else ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _enum(doc: Path, heading: str) -> tuple[str, ...]:
    match = re.search(rf"{heading}\n\n```text\n(.*?)```", _read(doc), re.S)
    assert match is not None, heading
    return tuple(line.strip() for line in match.group(1).splitlines() if line.strip())


def _changed() -> list[str]:
    return [
        p
        for p in _git(
            "diff", "--name-only", CANONICAL_MAIN, successor_window_end(CANONICAL_MAIN)
        ).splitlines()
        if p
    ]


# --- verifier -------------------------------------------------------------------------------


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
    assert "STEP66D_ARCH1_CONTRACT_FREEZE_VERIFY: PASS" in result.stdout.decode("utf-8")


@pytest.mark.parametrize("doc", ALL_DOCS)
def test_required_artifact_exists(doc: Path) -> None:
    assert doc.is_file(), doc


# --- binding decisions honoured, parsed not cited -------------------------------------------


def test_exactly_six_review_actions() -> None:
    assert _enum(FREEZE, r"### Review Gate Action \(exactly six\)") == REVIEW_ACTIONS


def test_exactly_three_final_decisions() -> None:
    assert _enum(FREEZE, r"### Product Owner Final Decision \(exactly three\)") == FINAL_DECISIONS


def test_the_two_enums_are_disjoint() -> None:
    actions = set(_enum(FREEZE, r"### Review Gate Action \(exactly six\)"))
    decisions = set(_enum(FREEZE, r"### Product Owner Final Decision \(exactly three\)"))
    assert actions & decisions == set()


def test_exactly_four_actions_carry_no_decision() -> None:
    assert _read(FREEZE).count("| none |") == 4


def test_exactly_nine_statuses() -> None:
    assert _enum(DOMAIN, r"### Canonical statuses \(exactly nine\)") == STATUSES


@pytest.mark.parametrize("entity", ENTITIES)
def test_entity_is_specified(entity: str) -> None:
    assert entity in _read(DOMAIN)


def test_no_extra_review_action_was_invented() -> None:
    """A seventh action would silently widen the gate."""
    body = _read(DOMAIN)
    section = body[body.index("## 3. DeliveryReviewAction") : body.index("## 4. ")]
    for invented in ("APPROVE", "DECLINE", "DEFER", "HOLD", "CANCEL"):
        assert invented not in section, f"{invented} is not a canonical Review Gate Action"


# --- the guarantees that matter --------------------------------------------------------------


def test_accept_and_reject_are_atomic_with_their_decision() -> None:
    text = _flat(_read(DOMAIN))
    assert "in ONE transaction" in text or "ONE transaction" in text
    assert "never be a persisted state where an `ACCEPT` action exists without" in text


def test_adr_10_states_the_atomicity_guarantee() -> None:
    body = _read(ADRS)
    assert "ADR-66D-10" in body
    section = body[body.index("## ADR-66D-10") :]
    assert "one transaction" in _flat(section).lower()


def test_decision_record_is_append_only_and_supersedable() -> None:
    domain = _flat(_read(DOMAIN))
    assert "never updated in place" in domain.lower()
    assert "supersedes_decision_id" in domain
    assert "Superseded statement" in domain


def test_status_is_a_projection_not_a_source_of_truth() -> None:
    assert "PROJECTION" in _read(DOMAIN) or "projection" in _read(DOMAIN)
    assert "DERIVED" in _read(DOMAIN)


def test_accepted_with_follow_up_is_non_blocking_only() -> None:
    assert "accepts only blocking = false" in _flat(_read(DOMAIN))


def test_blocking_follow_up_routes_to_request_changes() -> None:
    assert "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" in _read(APIDOC)
    assert "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" in _read(DOMAIN)


def test_escalate_never_becomes_a_decision() -> None:
    domain = _flat(_read(DOMAIN))
    assert "status stays `UNDER_REVIEW`" in domain or "status stays UNDER_REVIEW" in domain
    assert "never a final decision" in domain.lower()


def test_agent_completion_does_not_imply_pass() -> None:
    assert "Agent completion does not imply PASS" in _flat(_read(DOMAIN))


def test_task_is_not_the_agent_execution_source_of_truth() -> None:
    assert "Task is not the Agent execution source of truth" in _flat(_read(FREEZE))


def test_external_partners_are_not_runtime_agents() -> None:
    domain = _flat(_read(DOMAIN))
    assert "ai_partner" in domain
    assert "never be described or recorded as `runtime_agent`" in domain


def test_forbidden_generation_mode_excluded_from_first_poc() -> None:
    domain = _read(DOMAIN)
    assert "future_autonomous_runtime_generated" in domain
    assert "NOT PERMITTED IN THE FIRST POC" in domain
    assert "autonomous merge" in domain


# --- bounded QA rerun, the number this stage was authorized to choose ------------------------


def test_qa_rerun_limit_is_one_per_submission_version() -> None:
    assert "1 RERUN_QA action per submission version" in _flat(_read(FREEZE))


def test_adr_09_records_the_bound() -> None:
    body = _read(ADRS)
    assert "ADR-66D-09" in body
    assert "One bounded QA rerun per DeliverySubmission version" in body


def test_second_rerun_returns_the_limit_error() -> None:
    assert "409 QA_RERUN_LIMIT_REACHED" in _read(APIDOC)
    freeze = _flat(_read(FREEZE))
    assert "QA_RERUN_LIMIT_REACHED" in freeze


def test_rerun_counter_is_not_client_side() -> None:
    freeze = _flat(_read(FREEZE))
    assert "never a UI or client counter" in freeze


def test_new_version_resets_the_rerun_allowance() -> None:
    assert "fresh allowance" in _flat(_read(FREEZE))


# --- contracts present -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "/delivery-submissions",
        "/delivery-submissions/{submission_id}/submit",
        "/delivery-submissions/{submission_id}/review-actions",
        "/delivery-submissions/{submission_id}/po-decisions",
        "/product-owner-decisions/{decision_id}/follow-ups",
        "/acceptance-follow-ups/{follow_up_id}",
    ],
)
def test_endpoint_is_specified(endpoint: str) -> None:
    assert endpoint in _read(APIDOC)


@pytest.mark.parametrize(
    "code",
    [
        "409 DELIVERY_VERSION_CONFLICT",
        "409 FINAL_DECISION_ALREADY_EXISTS",
        "409 QA_RERUN_LIMIT_REACHED",
        "409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES",
        "409 SUBMISSION_EXPIRED",
        "422 ACCEPTANCE_CRITERIA_INCOMPLETE",
        "423 DELIVERY_REVIEW_BLOCKED",
    ],
)
def test_error_code_is_specified(code: str) -> None:
    assert code in _read(APIDOC)


@pytest.mark.parametrize(
    "event",
    [
        "delivery.submission.created",
        "delivery.review_action.recorded",
        "delivery.review.escalated",
        "delivery.po_decision.recorded",
        "delivery.po_decision.superseded",
        "delivery.follow_up.closed",
    ],
)
def test_event_is_specified(event: str) -> None:
    assert event in _read(APIDOC)


def test_review_and_decision_audit_names_are_distinct() -> None:
    api = _read(APIDOC)
    assert "review_action.accept" in api
    assert "po_decision.accepted" in api
    assert "review_action.accept" != "po_decision.accepted"


def test_outbox_is_specified_but_not_built() -> None:
    api = _read(APIDOC)
    assert "transactional outbox" in api.lower()
    assert "OUT OF SCOPE" in api
    assert "does not implement or wire it" in _flat(api)


def test_read_model_marks_missing_data_unknown() -> None:
    rm = _flat(_read(READMODEL))
    assert "never as zero, empty or healthy" in rm
    assert "EVENTUALLY CONSISTENT" in rm
    assert "is_stale" in rm


def test_cross_project_access_is_masked_as_404() -> None:
    assert "masked as 404" in _flat(_read(READMODEL))
    assert "masked as `404`" in _flat(_read(APIDOC))


def test_acceptance_grants_no_permission() -> None:
    rm = _flat(_read(READMODEL))
    for gate in ("production approval", "deployment", "secret provisioning"):
        assert gate in rm
    assert "not a permission grant" in rm


def test_rejection_does_not_restart_a_workflow() -> None:
    assert "MUST NOT automatically restart an Agent workflow" in _read(APIDOC)


# --- open questions stay open ------------------------------------------------------------------


def test_poc_control_center_ia_is_not_selected() -> None:
    rm = _read(READMODEL)
    assert "STILL OPEN" in rm
    assert "Unified Control Center" in rm and "Coordinated Existing Routes" in rm


def test_no_slice_is_authorized() -> None:
    assert _read(SLICES).count("Authorization status   NOT AUTHORIZED") >= 8


def test_no_gap_is_authorized_or_implemented() -> None:
    slices = _read(SLICES)
    assert "Authorized: 0 of 14" in slices
    assert "Implemented: 0 of 14" in slices


@pytest.mark.parametrize("stage", ["STEP66D_DESIGN", "STEP67POC0", "RA2I0"])
def test_stage_remains_unauthorized(stage: str) -> None:
    assert re.search(rf"{stage}:\s+NOT STARTED / NOT AUTHORIZED", _read(FREEZE))


def test_inventory_was_derived_from_real_source_paths() -> None:
    """Every source path the inventory claims must actually exist in the repository."""
    inventory = _read(INVENTORY)
    claimed = re.findall(
        r"(?:source path\s+)((?:apps|agents|shared|migrations)/[\w./-]+)", inventory
    )
    assert claimed, "the inventory records no source paths"
    missing = [p for p in claimed if not (REPO / p).exists()]
    assert missing == [], f"inventory cites non-existent paths: {missing}"


def test_legacy_delivery_package_really_exists_as_claimed() -> None:
    for rel in (
        "shared/sdk/delivery_package/models.py",
        "apps/orchestrator/src/delivery_package_api.py",
        "apps/admin-console/src/pages/DeliveryPackage.tsx",
    ):
        assert (REPO / rel).is_file(), rel


def test_task_roles_really_contains_the_two_named_roles() -> None:
    body = _read(REPO / "shared" / "sdk" / "tasks" / "rbac.py")
    assert "reviewer_approver" in body
    assert "pm_engineering_lead" in body


# --- scope and safety --------------------------------------------------------------------------


def test_no_runtime_or_infra_path_changed() -> None:
    changed = _changed()
    assert [p for p in changed if p.startswith(RUNTIME_PREFIXES)] == []
    assert [
        p for p in changed if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql"))
    ] == []


def test_advisory_files_untouched() -> None:
    changed = _changed()
    for rel in (
        "scripts/verify_step66sync1_claude_design_reconciliation.py",
        "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
    ):
        assert rel not in changed


def test_no_legacy_delivery_package_source_modified() -> None:
    assert [p for p in _changed() if "delivery_package" in p.lower()] == []


def test_be3_gates_still_default_false() -> None:
    for name in ("resume_request_model.py", "replay_request_model.py"):
        body = _read(REPO / "shared" / "sdk" / "tasks" / name)
        assert body.count('"false"') >= 2


@pytest.mark.parametrize("doc", ALL_DOCS)
def test_document_records_zero_production_executions(doc: Path) -> None:
    assert "production_executed_true_count" in _read(doc)


# --- Step 66D-ARCH1-M1 bounded post-merge contract-scope freeze --------------------------------


ARCH1_STAGE_HEAD = "ab19dad7a2e032e421927d71622bb22d6b9e3e36"


def test_positive_scope_is_frozen_not_worktree_relative() -> None:
    body = _read(SCRIPT)
    assert f'ARCH1_STAGE_HEAD = "{ARCH1_STAGE_HEAD}"' in body
    assert '"--name-only", CANONICAL_MAIN, ARCH1_STAGE_HEAD' in body


def test_frozen_range_holds_exactly_eleven_registered_paths() -> None:
    actual = {
        p
        for p in _git("diff", "--name-only", CANONICAL_MAIN, ARCH1_STAGE_HEAD).splitlines()
        if p.strip()
    }
    assert len(actual) == 11
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location("arch1_verifier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    _sys.modules["arch1_verifier"] = module
    spec.loader.exec_module(module)
    assert set(module.ARCH1_EXPECTED_PATHS) == actual


def test_denylists_stay_current_state_after_the_freeze() -> None:
    """Freezing the scope must not freeze the runtime denylist along with it."""
    body = _read(SCRIPT)
    assert 'git("diff", "--name-only", CANONICAL_MAIN).splitlines()' in body
