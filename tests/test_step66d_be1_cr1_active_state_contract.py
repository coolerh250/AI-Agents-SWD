"""Step 66D-BE1-CR1 -- tests for the DeliveryReviewTask active-state canonical contract.

Positive checks plus negative mutation probes A-H. Each probe copies the contract package into a
temporary git repository, tampers with exactly one thing, and asserts the verifier REJECTS it. No
probe is committed to this repository and none touches the working tree.

Must run with 0 failed and 0 skipped. Starts no runtime, container or external provider.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CR1_BASELINE = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"

CONTRACTS = ROOT / "docs/contracts/66d-delivery-acceptance"
ARCH = ROOT / "docs/architecture/66d-delivery-acceptance"
DESIGN = ROOT / "docs/design/66d-delivery-acceptance"
HANDOFF = ROOT / "docs/handoffs/66d-delivery-acceptance"

D05 = CONTRACTS / "step66d-d05-review-task-active-state-amendment.md"
BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"
REGISTRY = CONTRACTS / "step66d-canonical-terminology-registry.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
INBOX = DESIGN / "step66d-design-delivery-inbox-spec.md"
MANIFEST = DESIGN / "step66d-design-contract-manifest.json"
MATRIX = HANDOFF / "step66d-canonical-conflict-supersession-matrix.md"
EVIDENCE = HANDOFF / "step66d-be1-cr1-active-state-contract-evidence.md"
VERIFIER = ROOT / "scripts/verify_step66d_be1_cr1_active_state_contract.py"

COPIED = [D05, BINDING, REGISTRY, DOMAIN, INBOX, MANIFEST, MATRIX, EVIDENCE]

EXPECTED_PATHS = {
    "docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md",
    "docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md",
    "docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md",
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md",
    "docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md",
    "docs/design/66d-delivery-acceptance/step66d-design-contract-manifest.json",
    "docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-be1-cr1-active-state-contract-evidence.md",
    "scripts/verify_step66d_be1_cr1_active_state_contract.py",
    "tests/test_step66d_be1_cr1_active_state_contract.py",
}


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- positive
def test_d05_is_binding_and_records_authority():
    text = D05.read_text(encoding="utf-8")
    assert "66D-D05" in text
    assert "BINDING" in text
    assert "Product Owner" in text
    assert CR1_BASELINE in text or "af40b3b" in text


def test_predicates_are_structural():
    for path in (D05, BINDING, DOMAIN, REGISTRY):
        text = path.read_text(encoding="utf-8")
        assert "closed_at IS NULL" in text, path.name
        assert "closed_at IS NOT NULL" in text, path.name


def test_manifest_records_the_canonical_block():
    block = manifest()["review_task_active_state"]
    assert block["decision_id"] == "66D-D05"
    assert block["review_task_active_predicate"] == "closed_at_is_null"
    assert block["review_task_closed_predicate"] == "closed_at_is_not_null"
    assert block["review_task_lifecycle_enum"] == "deferred"
    assert block["submission_status_mirroring"] == "forbidden"
    assert block["delivery_review_task_status"] == "planned_not_implemented"
    assert block["persistence_invariant"] == "at_most_one_active_per_delivery_submission_id"
    assert block["partial_unique_boundary"] == "delivery_submission_id"
    assert block["required_existence_semantics"] == "deferred"
    assert block["transition_semantics"] == "deferred"
    assert block["closed_at_implies_decision"] is False


def test_all_ten_binding_requirements_present():
    text = BINDING.read_text(encoding="utf-8")
    for n in range(1, 11):
        assert f"D05-R{n}" in text, f"missing D05-R{n}"


def test_arch1_statement_is_annotated_not_deleted():
    text = DOMAIN.read_text(encoding="utf-8")
    assert "mirrors submission review state" in text, "the original sentence was deleted"
    assert "SUPERSEDED BY 66D-D05" in text
    assert "NOT AUTHORITATIVE FOR BE1 PERSISTENCE" in text


def test_design_non_interchangeability_preserved():
    text = INBOX.read_text(encoding="utf-8")
    assert "not interchangeable" in text.lower()
    assert "MUST NOT map DeliverySubmission.status" in text
    names = {f["name"] for f in manifest()["inbox_filters"]}
    assert {"delivery_review_task_status", "delivery_submission_status"} <= names


def test_at_most_one_not_exactly_one():
    for path in (D05, BINDING):
        flat = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        assert re.search(r"(?i)at most one", flat), path.name
        assert not re.search(r"(?i)exactly one .{0,40}always exists", flat), path.name


def test_no_migration_or_implementation_was_created():
    assert not list((ROOT / "migrations").glob("*delivery_review_task*"))
    assert not list((ROOT / "migrations").glob("*delivery_submission*"))
    assert not (ROOT / "shared/sdk/delivery_acceptance").exists()


def test_conflict_matrix_records_the_resolution():
    text = MATRIX.read_text(encoding="utf-8")
    assert "66D-D05" in text
    assert "closed_at" in text
    assert re.search(r"(?i)DESIGN did not define review.task lifecycle values", text)


def test_verifier_passes_on_the_committed_tree():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert "STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: PASS" in result.stdout, result.stdout


def test_scope_registry_is_exactly_ten_paths():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "CR1_EXPECTED_PATHS" in source
    assert f'CR1_BASELINE = "{CR1_BASELINE}"' in source
    assert len(EXPECTED_PATHS) == 10


# --------------------------------------------------------------------- probe harness
def _probe_copy(tmp: Path) -> Path:
    work = tmp / "repo"
    for sub in (
        "docs/contracts/66d-delivery-acceptance",
        "docs/architecture/66d-delivery-acceptance",
        "docs/design/66d-delivery-acceptance",
        "docs/handoffs/66d-delivery-acceptance",
        "scripts",
        "migrations",
    ):
        (work / sub).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.email", "probe@example.invalid"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.name", "probe"], cwd=work, check=True)
    (work / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=work, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True, check=True
    ).stdout.strip()
    for path in COPIED:
        shutil.copy2(path, work / path.relative_to(ROOT))
    verifier = work / "scripts/verify_step66d_be1_cr1_active_state_contract.py"
    shutil.copy2(VERIFIER, verifier)
    (work / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), work / "tests" / Path(__file__).name)
    # Re-point only the scope diff base at the probe's synthetic baseline. CR1_BASELINE itself is
    # left in place so the recorded-baseline string checks still exercise the real value.
    source = verifier.read_text(encoding="utf-8")
    source = source.replace(
        'f"{CR1_BASELINE}...HEAD"',
        f'"{base}...HEAD"',
    ).replace(
        '["git", "merge-base", "--is-ancestor", CR1_BASELINE, "HEAD"]',
        f'["git", "merge-base", "--is-ancestor", "{base}", "HEAD"]',
    )
    verifier.write_text(source, encoding="utf-8")
    return work


def _run_probe(work: Path) -> subprocess.CompletedProcess:
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "probe"], cwd=work, check=True)
    return subprocess.run(
        [sys.executable, "scripts/verify_step66d_be1_cr1_active_state_contract.py"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_rejected(result: subprocess.CompletedProcess, label: str) -> None:
    assert (
        "STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: FAIL" in result.stdout
    ), f"probe '{label}' was ACCEPTED:\n{result.stdout}\n{result.stderr}"


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"probe anchor not found in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_probe_control_untampered_tree_passes(tmp_path):
    work = _probe_copy(tmp_path)
    result = _run_probe(work)
    assert (
        "STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: PASS" in result.stdout
    ), f"the untampered control failed:\n{result.stdout}\n{result.stderr}"


def test_probe_a_mirrored_submission_status_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / BINDING.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nDeliveryReviewTask.review_status mirrors submission review state and is authoritative.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "A mirrored submission status")


def test_probe_b_added_open_closed_enum_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / BINDING.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nDeliveryReviewTask.status is an enum with the values OPEN and CLOSED.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "B OPEN/CLOSED lifecycle enum")


def test_probe_c_status_based_active_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / D05.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nFor DeliveryReviewTask, active is defined as status IN (PENDING, IN_PROGRESS).\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "C status-based active predicate")


def test_probe_d_filter_mapped_to_submission_status_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / MANIFEST.relative_to(ROOT)
    data = json.loads(target.read_text(encoding="utf-8"))
    for entry in data["inbox_filters"]:
        if entry["name"] == "delivery_review_task_status":
            entry["source_field"] = "DeliverySubmission.status"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _assert_rejected(_run_probe(work), "D filter mapped to submission status")


def test_probe_e_closed_at_implies_decision_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / D05.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nA row where closed_at IS NOT NULL means a ProductOwnerDecision was recorded.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "E closed_at implies a decision")


def test_probe_f_exactly_one_existence_claim_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / BINDING.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nThe database guarantees exactly one review task always exists per submission.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "F exactly-one existence claim")


def test_probe_g_reopen_semantics_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / D05.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\nA reopen operation MUST clear closed_at and return the task to active state.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), "G reopen semantics")


def test_probe_h_implementation_path_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    target = work / "migrations/030_delivery_review_tasks.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "CREATE TABLE delivery_review_tasks (id uuid PRIMARY KEY);\n", encoding="utf-8"
    )
    _assert_rejected(_run_probe(work), "H implementation/migration path")


@pytest.mark.parametrize(
    "label,forbidden",
    [
        ("lifecycle OPEN", "OPEN"),
        ("lifecycle CLOSED", "CLOSED"),
        ("lifecycle CANCELLED", "CANCELLED"),
    ],
)
def test_probe_lifecycle_values_are_rejected(tmp_path, label, forbidden):
    work = _probe_copy(tmp_path)
    target = work / REGISTRY.relative_to(ROOT)
    target.write_text(
        target.read_text(encoding="utf-8")
        + f"\n\nThe DeliveryReviewTask lifecycle status is {forbidden}.\n",
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), label)
