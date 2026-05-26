import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SLO_PATH = _REPO_ROOT / "infra" / "observability" / "slo" / "aiagents-slo.yml"
_VERIFY_SCRIPT = _REPO_ROOT / "scripts" / "verify_incident_flow.sh"

REQUIRED_SLO_NAMES = (
    "workflow_completion_p95_seconds",
    "workflow_success_rate",
    "agent_failure_rate",
    "dlq_growth_rate",
    "approval_pending_duration_seconds",
    "service_availability",
)

REQUIRED_SLO_FIELDS = (
    "name",
    "description",
    "target",
    "window",
    "query",
    "severity",
    "owner",
    "runbook_url",
)


def _load_slos() -> dict:
    return yaml.safe_load(_SLO_PATH.read_text(encoding="utf-8"))


def test_slo_file_exists():
    assert _SLO_PATH.exists(), f"missing {_SLO_PATH}"


def test_slo_yaml_is_valid_and_has_top_level_block():
    config = _load_slos()
    assert isinstance(config, dict)
    assert isinstance(config.get("slos"), list)
    assert config["slos"], "SLO file must declare at least one SLO"


def test_every_required_slo_is_present():
    config = _load_slos()
    names = {slo["name"] for slo in config["slos"]}
    for required in REQUIRED_SLO_NAMES:
        assert required in names, f"SLO {required!r} missing from aiagents-slo.yml"


def test_every_slo_has_required_fields():
    config = _load_slos()
    for slo in config["slos"]:
        for key in REQUIRED_SLO_FIELDS:
            assert key in slo, f"{slo.get('name')!r} is missing field {key!r}"
        # severity is restricted to the same set the alert rules use.
        assert slo["severity"] in ("critical", "warning", "info"), slo["name"]


def test_planned_slos_must_declare_a_todo():
    """A SLO whose underlying metric does not exist yet must carry a `todo`
    field explaining the follow-up — we must never silently ship a placeholder."""
    config = _load_slos()
    for slo in config["slos"]:
        if slo.get("status") == "planned":
            assert slo.get("todo"), f"{slo['name']!r} is planned but has no `todo`"
            # The query must be obviously a placeholder, e.g. vector(0).
            assert "vector(" in slo["query"], (slo["name"], slo["query"])


def test_active_slos_query_references_a_real_metric():
    """Active SLOs must reference at least one of the metric names already
    emitted by `shared/sdk/observability/metrics.py` (or the Prometheus
    built-in `up`). Cheap grep, not a parser — we just want to keep contributors
    honest."""
    config = _load_slos()
    known_metrics = (
        "workflow_completed_total",
        "workflow_failed_total",
        "workflow_duration_seconds_bucket",
        "agent_execution_total",
        "agent_execution_failures_total",
        "agent_latency_seconds_bucket",
        "deadletter_total",
        "retry_total",
        "notification_total",
        "up",
    )
    for slo in config["slos"]:
        if slo.get("status") != "active":
            continue
        query = slo["query"]
        assert any(
            metric in query for metric in known_metrics
        ), f"active SLO {slo['name']!r} references no known metric: {query!r}"


def test_verify_incident_flow_script_exists_and_is_executable_in_index():
    assert _VERIFY_SCRIPT.exists(), f"missing {_VERIFY_SCRIPT}"
    res = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/verify_incident_flow.sh"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0 or not res.stdout:
        pytest.skip("git ls-files unavailable; cannot check index mode")
    mode = res.stdout.split()[0]
    assert mode.startswith("1007"), f"verify_incident_flow.sh is not +x in git index (mode={mode})"


def test_verify_incident_flow_script_is_syntactically_valid():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available on PATH")
    res = subprocess.run(
        [bash, "-n", str(_VERIFY_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, f"verify_incident_flow.sh syntax error: {res.stderr}"


def test_verify_incident_flow_script_emits_required_markers():
    body = _VERIFY_SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "INCIDENT_FLOW_SMOKE: PASS",
        "INCIDENT_FLOW_SMOKE: FAIL",
        "VERIFY_INCIDENT_FLOW_DONE",
    ):
        assert marker in body, f"verify_incident_flow.sh missing marker {marker}"


def test_check_runtime_state_includes_incident_smokes():
    body = (_REPO_ROOT / "scripts" / "check_runtime_state.sh").read_text(encoding="utf-8")
    for marker in (
        "INCIDENT_API_SMOKE",
        "INCIDENT_CREATE_SMOKE",
        "INCIDENT_ACK_SMOKE",
        "INCIDENT_RESOLVE_SMOKE",
        "TERMINAL_FAILURE_INCIDENT_SMOKE",
        "WORKFLOW_FAILED_STATE_SMOKE",
        "SLO_CONFIG_SMOKE",
    ):
        assert marker in body, f"check_runtime_state.sh missing incident smoke {marker}"


def test_migration_005_exists_and_is_idempotent_shaped():
    path = _REPO_ROOT / "migrations" / "005_incident_management.sql"
    assert path.exists(), f"missing {path}"
    body = path.read_text(encoding="utf-8")
    # Every column add must use ADD COLUMN IF NOT EXISTS — otherwise re-running
    # the migration on the existing incident_records table would error out.
    assert "ADD COLUMN IF NOT EXISTS task_id" in body
    assert "ADD COLUMN IF NOT EXISTS workflow_id" in body
    assert "ADD COLUMN IF NOT EXISTS source" in body
    assert "ADD COLUMN IF NOT EXISTS details" in body
    assert "ADD COLUMN IF NOT EXISTS acknowledged_at" in body
    assert "ADD COLUMN IF NOT EXISTS resolved_at" in body
    # Indexes must use IF NOT EXISTS too.
    assert "CREATE INDEX IF NOT EXISTS idx_incident_records_status" in body
    assert "CREATE INDEX IF NOT EXISTS idx_incident_records_workflow_id" in body
