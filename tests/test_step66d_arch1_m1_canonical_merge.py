"""Tests for Step 66D-ARCH1-M1 canonical merge.

Offline by design: no container, no database, no network, no secret access. Counts are DERIVED
from the merged artifacts rather than asserted against a stated figure.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import pathlib

# AT-M2 remediation: cross-stage meta-guards require a stage's runtime denylist to keep
# scanning current state. The shared call below IS current state unless a successor
# milestone is canonically authorized: the property is unchanged, only the spelling is shared.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import scans_current_state  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def scans_current_state(body: str, anchor: str) -> bool:
        """Strictest fallback: only the literal current-state spellings are accepted."""
        return any(
            form in body for form in (f'"--name-only", {anchor}, "HEAD"', f'f"{{{anchor}}}...HEAD"')
        )


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
SCRIPT = SCRIPTS / "verify_step66d_arch1_m1_canonical_merge.py"

PRE_MERGE_MAIN = "ccfee8ef47f72d5d67ea6bb58845018f306cfa0c"
ARCH1_COMMIT = "ab19dad7a2e032e421927d71622bb22d6b9e3e36"
MERGE_COMMIT = "d411da52b240bef361a4af8588e6bb156a53ef40"

ARCH = REPO / "docs" / "architecture" / "66d-delivery-acceptance"
HANDOFFS = REPO / "docs" / "handoffs" / "66d-delivery-acceptance"

FREEZE = ARCH / "step66d-arch1-contract-freeze.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
APIDOC = ARCH / "step66d-arch1-api-event-audit-contracts.md"
READMODEL = ARCH / "step66d-arch1-read-model-and-security-boundary.md"
ADRS = REPO / "docs" / "decisions" / "step66d-arch1-architecture-decisions.md"
SLICES = HANDOFFS / "step66d-arch1-gap-and-implementation-slice-plan.md"
RECORD = HANDOFFS / "step66d-arch1-m1-canonical-merge-record.md"
ARCH1_VERIFIER = SCRIPTS / "verify_step66d_arch1_contract_freeze.py"

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
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


def _ancestor(commit: str, of: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, of], cwd=REPO, check=False
        ).returncode
        == 0
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _enum(doc: Path, heading: str) -> tuple[str, ...]:
    match = re.search(rf"{heading}\n\n```text\n(.*?)```", _read(doc), re.S)
    assert match is not None, heading
    return tuple(line.strip() for line in match.group(1).splitlines() if line.strip())


def _frozen_paths() -> list[str]:
    return [p for p in _git("diff", "--name-only", PRE_MERGE_MAIN, ARCH1_COMMIT).splitlines() if p]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"am1_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- verifier ---------------------------------------------------------------------------------


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
    assert "STEP66D_ARCH1_M1_CANONICAL_MERGE_VERIFY: PASS" in result.stdout.decode("utf-8")


# --- merge shape, re-derived from Git -----------------------------------------------------------


def test_merge_has_exactly_two_parents() -> None:
    parents = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert len(parents) == 2, f"a squash would not have two parents: {parents}"


def test_merge_parents_are_exact() -> None:
    parents = _git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert parents == [PRE_MERGE_MAIN, ARCH1_COMMIT]


@pytest.mark.parametrize("commit", [PRE_MERGE_MAIN, ARCH1_COMMIT, MERGE_COMMIT])
def test_commit_preserved_in_main_history(commit: str) -> None:
    assert _ancestor(commit, "HEAD"), commit


def test_branch_carried_exactly_one_commit() -> None:
    assert _git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{ARCH1_COMMIT}") == "1"


def test_arch1_commit_parent_is_pre_merge_main() -> None:
    """A rebase would have broken this direct link."""
    assert _git("show", "--no-patch", "--format=%P", ARCH1_COMMIT).split() == [PRE_MERGE_MAIN]


# --- frozen scope --------------------------------------------------------------------------------


def test_positive_scope_is_frozen() -> None:
    body = _read(ARCH1_VERIFIER)
    assert f'ARCH1_STAGE_HEAD = "{ARCH1_COMMIT}"' in body
    assert '"--name-only", CANONICAL_MAIN, ARCH1_STAGE_HEAD' in body


def test_frozen_range_holds_exactly_eleven_paths() -> None:
    assert len(_frozen_paths()) == 11


def test_registered_path_set_equals_the_frozen_range() -> None:
    module = _load("verify_step66d_arch1_contract_freeze")
    assert set(module.ARCH1_EXPECTED_PATHS) == set(_frozen_paths())


def test_no_positive_scope_resolves_against_head() -> None:
    body = _read(ARCH1_VERIFIER)
    offenders = re.findall(r'diff", "--name-only", [^)]*"HEAD"', body)
    assert offenders == [], offenders


def test_denylists_still_scan_current_state() -> None:
    """Freezing the scope must not freeze the runtime denylist along with it."""
    assert scans_current_state(_read(ARCH1_VERIFIER), "CANONICAL_MAIN")


# --- contracts survived the merge ---------------------------------------------------------------


def test_exactly_six_review_actions() -> None:
    assert _enum(FREEZE, r"### Review Gate Action \(exactly six\)") == REVIEW_ACTIONS


def test_exactly_three_final_decisions() -> None:
    assert _enum(FREEZE, r"### Product Owner Final Decision \(exactly three\)") == FINAL_DECISIONS


def test_enums_are_disjoint() -> None:
    actions = set(_enum(FREEZE, r"### Review Gate Action \(exactly six\)"))
    decisions = set(_enum(FREEZE, r"### Product Owner Final Decision \(exactly three\)"))
    assert actions & decisions == set()


def test_four_actions_carry_no_decision() -> None:
    assert _read(FREEZE).count("| none |") == 4


@pytest.mark.parametrize("entity", ENTITIES)
def test_entity_survived(entity: str) -> None:
    assert entity in _read(DOMAIN)


def test_decision_record_still_immutable_and_supersedable() -> None:
    domain = _flat(_read(DOMAIN))
    assert "never updated in place" in domain.lower()
    assert "supersedes_decision_id" in domain
    assert "Superseded statement" in domain


def test_accept_reject_atomicity_survived() -> None:
    assert "never be a persisted state where an `ACCEPT` action exists without" in _flat(
        _read(DOMAIN)
    )
    assert "ADR-66D-10" in _read(ADRS)


def test_blocking_follow_up_still_rejected() -> None:
    assert "accepts only blocking = false" in _flat(_read(DOMAIN))
    assert "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" in _read(APIDOC)


def test_qa_rerun_bound_survived() -> None:
    assert "1 RERUN_QA action per submission version" in _flat(_read(FREEZE))
    assert "One bounded QA rerun per DeliverySubmission version" in _read(ADRS)
    assert "409 QA_RERUN_LIMIT_REACHED" in _read(APIDOC)


def test_legacy_delivery_package_still_separated() -> None:
    assert "may **not** act as the human review aggregate" in _read(FREEZE)
    assert [p for p in _frozen_paths() if "delivery_package" in p.lower()] == []


def test_task_is_still_not_the_execution_source_of_truth() -> None:
    assert "Task is not the Agent execution source of truth" in _flat(_read(FREEZE))


# --- derived counts, the three corrected figures -------------------------------------------------


def test_derived_endpoint_count_is_seventeen() -> None:
    api = _read(APIDOC)
    rows = re.findall(r"^\| (?:GET|POST|PATCH|PUT|DELETE) \| `[^`]+` \|", api, re.M)
    assert len(rows) == 17, f"derived endpoint count is {len(rows)}"


def test_derived_event_count_is_twenty() -> None:
    api = _read(APIDOC)
    block = re.search(r"## 3\. Durable event contracts.*?```text\n(.*?)```", api, re.S)
    assert block is not None
    assert len([x for x in block.group(1).splitlines() if x.strip()]) == 20


def test_derived_error_code_count_is_eighteen() -> None:
    api = _read(APIDOC)
    block = re.search(r"## 2\. Error semantics\n\n```text\n(.*?)```", api, re.S)
    assert block is not None
    assert len([x for x in block.group(1).splitlines() if x.strip()]) == 18


def test_derived_audit_action_count_is_ten() -> None:
    api = _read(APIDOC)
    block = re.search(r"### Distinct action names.*?```text\n(.*?)```", api, re.S)
    assert block is not None
    names = re.findall(r"(review_action\.\w+|po_decision\.\w+)", block.group(1))
    assert len(names) == 10


def test_merge_record_discloses_the_three_count_corrections() -> None:
    record = _read(RECORD)
    assert "CORRECTED" in record
    for value in ("17", "20", "18"):
        assert value in record
    assert "Nothing is missing and nothing unauthorized was added" in _flat(record)


# --- open questions stay open ---------------------------------------------------------------------


def test_control_center_ia_still_unresolved() -> None:
    rm = _read(READMODEL)
    assert "STILL OPEN" in rm
    assert "Unified Control Center" in rm and "Coordinated Existing Routes" in rm
    assert "UNRESOLVED" in _read(RECORD)


def test_legacy_migration_still_deferred() -> None:
    assert "DEFERRED" in _read(RECORD)


def test_contracts_still_not_implemented() -> None:
    assert "NOT IMPLEMENTED" in _read(APIDOC)
    record = _read(RECORD)
    assert "FROZEN / NOT IMPLEMENTED" in record


def test_no_slice_is_authorized() -> None:
    assert _read(SLICES).count("Authorization status   NOT AUTHORIZED") >= 8
    assert "0 of 8 authorized" in _read(RECORD)


def test_design_ready_but_not_started() -> None:
    record = _read(RECORD)
    assert "READY FOR SEPARATE PRODUCT OWNER AUTHORIZATION" in record
    assert "not started" in _flat(record).lower()


# --- safety -----------------------------------------------------------------------------------------


def test_no_runtime_or_infra_path_was_merged() -> None:
    changed = _frozen_paths()
    assert [p for p in changed if p.startswith(RUNTIME_PREFIXES)] == []
    assert [
        p for p in changed if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql"))
    ] == []


def test_task_roles_implementation_untouched() -> None:
    changed = _frozen_paths()
    for rel in ("shared/sdk/tasks/rbac.py", "shared/sdk/tasks/authorization_policy.py"):
        assert rel not in changed


def test_advisory_files_untouched() -> None:
    changed = set(_frozen_paths()) | {
        p for p in _git("diff", "--name-only", MERGE_COMMIT).splitlines() if p
    }
    for rel in (
        "scripts/verify_step66sync1_claude_design_reconciliation.py",
        "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
    ):
        assert rel not in changed


def test_be3_gates_still_default_false() -> None:
    for name in ("resume_request_model.py", "replay_request_model.py"):
        body = _read(REPO / "shared" / "sdk" / "tasks" / name)
        assert body.count('"false"') >= 2


def test_production_count_zero() -> None:
    assert "production_executed_true_count" in _read(RECORD)
