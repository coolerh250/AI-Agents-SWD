"""Step 66GOV.1 -- Stage Gate & Context Guard Skill Pack compliance (docs-only checks).

Governance stage: this file itself changes no runtime code. It confirms the
repo-level skill pack (.agents skills, docs/stages standard/templates/
examples, docs/process governance docs, PR template sections) exists and is
internally consistent.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_FILES = {
    "shared-context": ROOT / ".agents" / "skills" / "shared-context" / "SKILL.md",
    "stage-gate": ROOT / ".agents" / "skills" / "stage-gate" / "SKILL.md",
    "security-governance": ROOT / ".agents" / "skills" / "security-governance" / "SKILL.md",
    "design-collaboration": ROOT / ".agents" / "skills" / "design-collaboration" / "SKILL.md",
    "frontend-implementation": ROOT / ".agents" / "skills" / "frontend-implementation" / "SKILL.md",
}

PROCESS_DOCS = {
    "stage-gate-checkpoint-protocol": ROOT
    / "docs"
    / "process"
    / "stage-gate-checkpoint-protocol.md",
    "context-guard-protocol": ROOT / "docs" / "process" / "context-guard-protocol.md",
    "source-of-truth-policy": ROOT / "docs" / "process" / "source-of-truth-policy.md",
    "stop-conditions": ROOT / "docs" / "process" / "stop-conditions.md",
    "partner-handoff-standard": ROOT / "docs" / "process" / "partner-handoff-standard.md",
}

STAGES_DOCS = {
    "stages-readme": ROOT / "docs" / "stages" / "README.md",
    "stage-manifest-standard": ROOT / "docs" / "stages" / "stage-manifest-standard.yaml",
    "context-receipt-template": ROOT / "docs" / "stages" / "context-receipt-template.md",
    "stage-gate-report-template": ROOT / "docs" / "stages" / "stage-gate-report-template.md",
    "design-example": ROOT / "docs" / "stages" / "examples" / "design-stage-manifest.example.yaml",
    "frontend-example": ROOT
    / "docs"
    / "stages"
    / "examples"
    / "frontend-stage-manifest.example.yaml",
    "review-example": ROOT / "docs" / "stages" / "examples" / "review-stage-manifest.example.yaml",
}

PR_TEMPLATE = ROOT / ".github" / "pull_request_template.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def test_agents_readme_exists() -> None:
    assert (ROOT / ".agents" / "README.md").is_file()


def test_all_skill_files_exist() -> None:
    for name, p in SKILL_FILES.items():
        assert p.is_file(), name


def test_all_process_docs_exist() -> None:
    for name, p in PROCESS_DOCS.items():
        assert p.is_file(), name


def test_all_stages_docs_exist() -> None:
    for name, p in STAGES_DOCS.items():
        assert p.is_file(), name


def test_decisions_readme_exists() -> None:
    assert (ROOT / "docs" / "decisions" / "README.md").is_file()


def test_pr_template_has_required_sections() -> None:
    text = _norm(PR_TEMPLATE.read_text(encoding="utf-8"))
    for section in ("shared context", "scope", "authorization", "safety", "evidence"):
        assert section in text, section


def test_security_skill_has_required_restrictions() -> None:
    text = _norm(SKILL_FILES["security-governance"].read_text(encoding="utf-8"))
    for term in (
        "production action",
        "workflow dispatch",
        "external action",
        "secrets",
        "client-side-only rbac",
    ):
        assert term in text, term


def test_frontend_skill_has_local_only_prohibition() -> None:
    text = _norm(SKILL_FILES["frontend-implementation"].read_text(encoding="utf-8"))
    assert "local-only" in text
    assert "not deliverables" in text


def test_design_skill_has_no_runtime_code_rule() -> None:
    text = _norm(SKILL_FILES["design-collaboration"].read_text(encoding="utf-8"))
    assert "does not modify runtime code" in text


def test_stage_gate_skill_defines_nine_gates() -> None:
    text = _norm(SKILL_FILES["stage-gate"].read_text(encoding="utf-8"))
    for gate in (
        "shared context sync gate",
        "architecture direction gate",
        "design review gate",
        "implementation efficiency gate",
        "security / governance gate",
        "product owner validation gate",
        "merge gate",
        "deployment gate",
        "post-deployment review gate",
    ):
        assert gate in text, gate


def test_manifest_standard_has_required_fields() -> None:
    text = STAGES_DOCS["stage-manifest-standard"].read_text(encoding="utf-8")
    for field in (
        "stage:",
        "owner:",
        "task_type:",
        "allowed_paths:",
        "forbidden_paths:",
        "codex_authorized:",
        "production_action_allowed:",
        "workflow_dispatch_allowed:",
        "stop_conditions:",
    ):
        assert field in text, field


def test_no_secret_shapes_in_new_docs() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    all_docs = {**SKILL_FILES, **PROCESS_DOCS}
    for name, p in all_docs.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers_in_new_docs() -> None:
    all_docs = {**SKILL_FILES, **PROCESS_DOCS}
    for name, p in all_docs.items():
        text = p.read_text(encoding="utf-8").lower()
        for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
            assert forbidden not in text, f"{name}: {forbidden}"


def test_verifier_marker_pass() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_stage_gate_compliance.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert "STEP66GOV1_STAGE_GATE_CONTEXT_GUARD_VERIFY: PASS" in result.stdout
    assert result.returncode == 0
