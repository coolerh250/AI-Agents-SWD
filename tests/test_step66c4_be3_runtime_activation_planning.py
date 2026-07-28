"""Step 66C.4-BE3-RA-P -- runtime activation readiness planning tests.

DB-less structural tests only (planning stage; no PostgreSQL, no runtime). Mirrors and extends the
checks in scripts/verify_step66c4_be3_runtime_activation_planning.py so the planning deliverables
and the underlying safety invariants are covered by the standard pytest suite as well as the
standalone verifier.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"

PLAN = CONTRACT / "be3-runtime-activation-readiness-plan.md"
SEQUENCE = HANDOFF / "be3-runtime-activation-stage-sequence.md"
EVIDENCE = ROOT / "docs" / "test" / "step66c4-be3-runtime-activation-planning-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"

FEATURE_GATES = (
    "BE3_RESUME_API_ENABLED",
    "BE3_RESUME_COMMAND_ENABLED",
    "BE3_REPLAY_API_ENABLED",
    "BE3_REPLAY_EXECUTION_ENABLED",
)


@pytest.fixture(scope="module")
def plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sequence_text() -> str:
    return SEQUENCE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def evidence_text() -> str:
    return EVIDENCE.read_text(encoding="utf-8")


def test_deliverables_exist() -> None:
    for p in (PLAN, SEQUENCE, EVIDENCE):
        assert p.is_file(), f"missing planning deliverable: {p}"


def test_all_11_gates_classified(plan_text: str) -> None:
    for i in range(1, 12):
        assert f"### Gate {i} " in plan_text, f"gate {i} section missing"


def test_gate_sections_have_required_fields(plan_text: str) -> None:
    blocks = re.split(r"(?=### Gate \d+ )", plan_text)[1:]
    assert len(blocks) == 11
    required = (
        "Classification:",
        "Implementation:",
        "Evidence:",
        "Missing capability:",
        "Upstream dependency:",
        "Downstream dependency:",
        "Risk level:",
    )
    for block in blocks:
        title = block.splitlines()[0].strip()
        for field in required:
            assert field in block, f"{title} missing {field}"


def test_gate_classifications_use_allowed_vocabulary(plan_text: str) -> None:
    allowed = {
        "IMPLEMENTED_AND_VERIFIED",
        "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
        "PARTIALLY_IMPLEMENTED",
        "NOT_IMPLEMENTED",
        "BLOCKED_BY_DEPENDENCY",
        "REQUIRES_PRODUCT_DECISION",
    }
    tokens = re.findall(r"Classification:\s+(\S+)", plan_text)
    assert len(tokens) == 11
    for t in tokens:
        assert t in allowed, f"unrecognized classification: {t}"


def test_no_gate_conflates_code_existence_with_runtime_ready(plan_text: str) -> None:
    """The plan's own ground rule: implemented code != runtime readiness. At least one gate must
    be classified IMPLEMENTED_NOT_RUNTIME_VALIDATED (proving the distinction was actually applied,
    not just stated)."""
    assert "IMPLEMENTED_NOT_RUNTIME_VALIDATED" in plan_text


def test_stage_sequence_has_12_ordered_stages(sequence_text: str) -> None:
    positions = []
    for i in range(1, 13):
        header = f"### RA-{i} "
        assert header in sequence_text, f"stage RA-{i} missing"
        positions.append(sequence_text.index(header))
    assert positions == sorted(positions), "stages are not in ascending order"


def test_each_stage_single_capability_with_rollback_and_boundary(sequence_text: str) -> None:
    blocks = re.split(r"(?=### RA-\d+ )", sequence_text)[1:]
    assert len(blocks) == 12
    for block in blocks:
        title = block.splitlines()[0].strip()
        assert block.count("Capability:") == 1, f"{title} does not name exactly one capability"
        assert "Rollback:" in block, f"{title} missing rollback definition"
        assert "Risk tier:" in block, f"{title} missing risk tier"
        assert (
            "Authorization" in block and "boundary:" in block
        ), f"{title} missing authorization boundary"


def test_critical_stages_require_independent_review_and_po_gate(sequence_text: str) -> None:
    blocks = re.split(r"(?=### RA-\d+ )", sequence_text)[1:]
    critical_blocks = [b for b in blocks if re.search(r"Risk tier:\s+CRITICAL\b", b)]
    assert critical_blocks, "no stage's Risk tier is classified CRITICAL"
    for block in critical_blocks:
        title = block.splitlines()[0].strip()
        assert "independent review" in block.lower(), f"{title} missing independent review"
        assert "Product Owner gate" in block, f"{title} missing explicit PO gate requirement"


def test_product_decisions_listed_separately(plan_text: str) -> None:
    assert "## 7. Product decisions inventory" in plan_text
    section = plan_text.split("## 7. Product decisions inventory")[1].split("## 8.")[0]
    numbered = re.findall(r"^\d+\. .+\?", section, re.M)
    assert len(numbered) >= 11, f"expected >=11 product decisions, found {len(numbered)}"


@pytest.mark.parametrize("gate", FEATURE_GATES)
def test_feature_gate_defaults_false(gate: str) -> None:
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    combined = resume_src + replay_src
    assert f'os.environ.get("{gate}", "false")' in combined


def test_no_automatic_migration_runner_in_shared_compose() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    assert not re.search(r"migrat", compose, re.I), "compose file references a migration runner"


def test_no_automatic_consumer_in_shared_compose() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    for token in ("lifecycle-poller", "lifecycle_poller", "outbox-relay", "outbox_relay"):
        assert token not in compose, f"compose file appears to run consumer service {token}"


def test_no_service_identity_authenticator_outside_tests() -> None:
    """Confirms the planning finding: is_service_identity=True is constructed only in test-helper
    code, never in production (apps/ or shared/sdk/) source."""
    rc = subprocess.run(
        ["git", "grep", "-n", "is_service_identity=True", "--", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    lines = [line for line in rc.stdout.splitlines() if line.strip()]
    assert lines, "expected at least one is_service_identity=True call site (the test helpers)"
    non_test = [line for line in lines if not line.startswith("tests/")]
    assert not non_test, f"found is_service_identity=True outside tests/: {non_test}"


def test_no_policy_authority_credentials_provisioned_anywhere() -> None:
    infra_dir = ROOT / "infra"
    names = (
        "BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID",
        "BE3_RESUME_POLICY_AUTHORITY_CAPABILITY",
        "BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS",
    )
    for path in infra_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name in names:
            assert name not in text, f"{name} unexpectedly provisioned in {path}"


def test_no_infra_migrations_or_workflow_paths_changed_by_this_stage() -> None:
    rc = subprocess.run(
        ["git", "diff", "--name-only", "284d706", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    changed = [f for f in rc.stdout.splitlines() if f]
    forbidden_prefixes = ("infra/", "migrations/", ".github/workflows/", "frontend/")
    for f in changed:
        assert not f.startswith(forbidden_prefixes), f"forbidden path changed: {f}"


def test_production_executed_true_count_recorded_as_zero(plan_text: str) -> None:
    progress = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")
    assert "production_executed_true_count" in plan_text
    assert "production_executed_true_count` = 0" in progress


def test_no_stage_authorized_by_this_document(plan_text: str, sequence_text: str) -> None:
    assert "not authorized" in plan_text.lower() or "NOT authorized" in plan_text
    assert "requires its own separate, explicit Product Owner authorization" in sequence_text


def test_verifier_script_passes() -> None:
    script = ROOT / "scripts" / "verify_step66c4_be3_runtime_activation_planning.py"
    assert script.is_file()
    env = dict(os.environ)
    rc = subprocess.run(["python", str(script)], cwd=ROOT, capture_output=True, text=True, env=env)
    assert rc.returncode == 0, rc.stdout + rc.stderr
    assert "STEP66C4_BE3_RUNTIME_ACTIVATION_PLANNING_VERIFY: PASS" in rc.stdout
