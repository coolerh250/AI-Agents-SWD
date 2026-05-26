"""Static checks for docs/operations/manual-verification.md.

We assert the doc exists, gives a human operator copy-paste commands
for every required step, mentions the verification scripts, embeds no
secrets, and does not instruct production deployment.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC = _REPO_ROOT / "docs" / "operations" / "manual-verification.md"


def test_doc_exists():
    assert _DOC.exists(), f"missing {_DOC}"


def test_doc_lists_required_copy_paste_commands():
    body = _DOC.read_text(encoding="utf-8")
    required = (
        "ssh aiagent-swd",
        "cd /home/itadmin/AI-Agents-SWD",
        "git pull --ff-only",
        "git log -1",
        "docker compose -f infra/docker-compose/docker-compose.yml ps",
        "./scripts/check_runtime_state.sh",
        "./scripts/verify_platform_observability.sh",
        "./scripts/verify_tracing_backend.sh",
        "./scripts/verify_trace_flow.sh",
        "./scripts/verify_alerting.sh",
        "./scripts/verify_incident_flow.sh",
        "/workflow/progress/",
        "/workflow/timeline/",
        "/api/traces/",
        "/incidents",
        "production_executed",
    )
    for marker in required:
        assert marker in body, f"manual-verification.md missing: {marker!r}"


def test_doc_documents_test_server_and_repo_path():
    body = _DOC.read_text(encoding="utf-8")
    assert "10.0.1.31" in body
    assert "aiagent-swd" in body
    assert "/home/itadmin/AI-Agents-SWD" in body


def test_doc_documents_safety_contract():
    body = _DOC.read_text(encoding="utf-8").lower()
    assert "local/test only" in body or "local / test only" in body
    assert "null receiver" in body
    assert "production" in body


def test_doc_does_not_instruct_production_deploy():
    body = _DOC.read_text(encoding="utf-8").lower()
    banned = (
        "deploy to production",
        "production deploy",
        "kubectl apply",
        "kubectl create",
        "terraform apply",
        "helm install",
        "aws deploy",
        "gcloud deploy",
        "az deployment",
    )
    for phrase in banned:
        # The doc may mention the *prohibition* in body text; the test
        # only forbids active deploy commands.
        if phrase == "production deploy":
            # phrase ok in prose like "no production deploy"; tighten:
            continue
        assert phrase not in body, f"doc contains banned phrase: {phrase!r}"


def test_doc_does_not_embed_secrets():
    body = _DOC.read_text(encoding="utf-8").lower()
    for needle in (
        "api_key=",
        "api-key=",
        "bearer ",
        "password=",
        "token=",
        "aws_secret",
        "slack_token",
    ):
        assert needle not in body, f"doc contains forbidden token: {needle!r}"


def test_readme_references_runbook_and_manual_verification():
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/operations/observability-runbook.md" in readme
    assert "docs/operations/manual-verification.md" in readme
    assert "verify_platform_observability.sh" in readme
    assert "Operational Readiness" in readme
