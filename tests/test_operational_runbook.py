"""Static checks for docs/operations/observability-runbook.md.

The runbook is operator-facing. We only enforce shape (file exists,
required sections present, no secret/token strings, no production
instructions) — not prose.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUNBOOK = _REPO_ROOT / "docs" / "operations" / "observability-runbook.md"


def test_runbook_exists():
    assert _RUNBOOK.exists(), f"missing {_RUNBOOK}"


def test_runbook_has_required_sections():
    body = _RUNBOOK.read_text(encoding="utf-8")
    required = (
        "Platform service map",
        "Check Docker containers",
        "Check service health",
        "Prometheus",
        "Alertmanager",
        "Grafana",
        "Tempo",
        "Find a workflow by",
        "Find a full trace by",
        "Dead-letter queue",
        "Incidents",
        "terminal failure",
        "workflow failed state",
        "production_executed",
        "Common issues",
    )
    for marker in required:
        assert marker in body, f"runbook missing section / phrase: {marker!r}"


def test_runbook_documents_verification_scripts():
    body = _RUNBOOK.read_text(encoding="utf-8")
    for script in (
        "verify_platform_observability.sh",
        "check_runtime_state.sh",
        "verify_tracing_backend.sh",
        "verify_trace_flow.sh",
        "verify_alerting.sh",
        "verify_incident_flow.sh",
    ):
        assert script in body, f"runbook does not mention {script}"


def test_runbook_documents_safety_contract():
    body = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "null receiver" in body
    assert "local/test only" in body or "local / test only" in body
    assert "no production" in body or "never deploys to production" in body


def test_runbook_does_not_instruct_production_deploy():
    body = _RUNBOOK.read_text(encoding="utf-8").lower()
    banned = (
        "deploy to production",
        "kubectl apply",
        "kubectl create",
        "terraform apply",
        "helm install",
        "aws deploy",
        "gcloud deploy",
        "az deployment",
    )
    for phrase in banned:
        assert phrase not in body, f"runbook contains banned phrase: {phrase!r}"


def test_runbook_does_not_embed_secrets():
    body = _RUNBOOK.read_text(encoding="utf-8")
    # Allow placeholder env var names; reject anything that looks like a
    # baked-in credential.
    lower = body.lower()
    for needle in (
        "api_key=",
        "api-key=",
        "bearer ",
        "password=",
        "token=",
        "aws_secret",
        "slack_token",
    ):
        assert needle not in lower, f"runbook contains forbidden secret token: {needle!r}"


def test_runbook_uses_127_loopback_or_test_host():
    body = _RUNBOOK.read_text(encoding="utf-8")
    # The runbook is for 10.0.1.31; URLs use localhost / 127.0.0.1.
    assert "10.0.1.31" in body
    assert "localhost" in body or "127.0.0.1" in body
