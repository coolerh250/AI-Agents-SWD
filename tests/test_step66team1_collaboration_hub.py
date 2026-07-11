"""Step 66TEAM.1 -- GitHub Team Collaboration Hub & Development Protocol (docs-only checks).

Pure documentation/process stage: no backend/frontend runtime change, no
workflow execution. This file follows the repo's tests/test_stepNN_*.py
convention -- it confirms the full collaboration-hub directory structure and
required content exist.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GITHUB = ROOT / ".github"

PROCESS_DOCS = {
    "collaboration-protocol": DOCS
    / "process"
    / "frontend-design-engineering-collaboration-protocol.md",
    "role-matrix": DOCS / "process" / "role-responsibility-matrix.md",
    "github-hub": DOCS / "process" / "github-collaboration-hub.md",
    "branch-pr-standard": DOCS / "process" / "branch-pr-naming-standard.md",
    "operator-validation-standard": DOCS / "process" / "operator-validation-standard.md",
}

DESIGN_FILES = {
    "design-readme": DOCS / "design" / "README.md",
    "design-brief-template": DOCS / "design" / "templates" / "design-brief-template.md",
    "wireframe-notes-template": DOCS / "design" / "templates" / "wireframe-notes-template.md",
    "interaction-flow-template": DOCS / "design" / "templates" / "interaction-flow-template.md",
    "component-spec-template": DOCS / "design" / "templates" / "component-spec-template.md",
    "design-handoff-template": DOCS / "design" / "templates" / "design-handoff-template.md",
    "design-66c3-readme": DOCS / "design" / "66c3-workroom-audit-visibility" / "README.md",
}

CONTRACT_FILES = {
    "contracts-readme": DOCS / "contracts" / "README.md",
    "frontend-api-contract-template": DOCS
    / "contracts"
    / "templates"
    / "frontend-api-contract-template.md",
    "frontend-data-contract-template": DOCS
    / "contracts"
    / "templates"
    / "frontend-data-contract-template.md",
    "rbac-error-contract-template": DOCS
    / "contracts"
    / "templates"
    / "rbac-error-contract-template.md",
    "safety-contract-template": DOCS / "contracts" / "templates" / "safety-contract-template.md",
    "66c3-frontend-contract": DOCS
    / "contracts"
    / "66c3-workroom-audit-visibility"
    / "frontend-contract.md",
}

FRONTEND_FILES = {
    "frontend-readme": DOCS / "frontend" / "README.md",
    "implementation-plan-template": DOCS
    / "frontend"
    / "templates"
    / "frontend-implementation-plan-template.md",
    "test-evidence-template": DOCS
    / "frontend"
    / "templates"
    / "frontend-test-evidence-template.md",
    "handoff-report-template": DOCS
    / "frontend"
    / "templates"
    / "frontend-handoff-report-template.md",
    "frontend-66c3-readme": DOCS / "frontend" / "66c3-workroom-audit-visibility" / "README.md",
}

HANDOFF_FILES = {
    "handoffs-readme": DOCS / "handoffs" / "README.md",
    "design-to-engineering-template": DOCS
    / "handoffs"
    / "templates"
    / "design-to-engineering-handoff-template.md",
    "contract-to-frontend-template": DOCS
    / "handoffs"
    / "templates"
    / "contract-to-frontend-handoff-template.md",
    "frontend-to-integration-template": DOCS
    / "handoffs"
    / "templates"
    / "frontend-to-integration-handoff-template.md",
    "operator-validation-handoff-template": DOCS
    / "handoffs"
    / "templates"
    / "operator-validation-handoff-template.md",
    "handoff-index-66c3": DOCS / "handoffs" / "66c3-workroom-audit-visibility" / "handoff-index.md",
}

DECISION_FILES = {
    "decisions-readme": DOCS / "decisions" / "README.md",
    "adr-template": DOCS / "decisions" / "adr-template.md",
}

GITHUB_FILES = {
    "issue-design": GITHUB / "ISSUE_TEMPLATE" / "design-task.md",
    "issue-frontend": GITHUB / "ISSUE_TEMPLATE" / "frontend-task.md",
    "issue-backend": GITHUB / "ISSUE_TEMPLATE" / "backend-contract-task.md",
    "issue-operator-validation": GITHUB / "ISSUE_TEMPLATE" / "operator-validation-task.md",
    "issue-gap-remediation": GITHUB / "ISSUE_TEMPLATE" / "gap-remediation-task.md",
    "pr-template": GITHUB / "pull_request_template.md",
}

ALL_DOCS = {
    **PROCESS_DOCS,
    **DESIGN_FILES,
    **CONTRACT_FILES,
    **FRONTEND_FILES,
    **HANDOFF_FILES,
    **DECISION_FILES,
    **GITHUB_FILES,
}


def _norm(text: str) -> str:
    """Collapse whitespace (incl. markdown line-wrap newlines) for substring checks."""
    return re.sub(r"\s+", " ", text.lower())


def _all_low() -> str:
    return _norm("\n".join(p.read_text(encoding="utf-8") for p in ALL_DOCS.values()))


def test_process_docs_exist() -> None:
    for name, p in PROCESS_DOCS.items():
        assert p.is_file(), name


def test_design_structure_exists() -> None:
    for name, p in DESIGN_FILES.items():
        assert p.is_file(), name


def test_contracts_structure_exists() -> None:
    for name, p in CONTRACT_FILES.items():
        assert p.is_file(), name


def test_frontend_structure_exists() -> None:
    for name, p in FRONTEND_FILES.items():
        assert p.is_file(), name


def test_handoffs_structure_exists() -> None:
    for name, p in HANDOFF_FILES.items():
        assert p.is_file(), name


def test_decisions_structure_exists() -> None:
    for name, p in DECISION_FILES.items():
        assert p.is_file(), name


def test_github_templates_exist() -> None:
    for name, p in GITHUB_FILES.items():
        assert p.is_file(), name


def test_role_matrix_names_all_five_roles() -> None:
    text = PROCESS_DOCS["role-matrix"].read_text(encoding="utf-8")
    for role in ("Zachary", "ChatGPT", "Claude Code", "Codex", "Claude Design"):
        assert role in text, role


def test_operator_validation_response_values_documented() -> None:
    low = _all_low()
    for token in ("visible", "not_visible", "partial_with_gaps", "pass_with_gaps"):
        assert token in low, token


def test_operator_is_only_acceptance_authority_documented() -> None:
    text = PROCESS_DOCS["operator-validation-standard"].read_text(encoding="utf-8")
    assert "must not decide final product acceptance" in text


def test_66c3_contract_allowed_fields_documented() -> None:
    text = CONTRACT_FILES["66c3-frontend-contract"].read_text(encoding="utf-8")
    for field in (
        "audit_event_id",
        "task_id",
        "event_type",
        "created_at",
        "actor",
        "role",
        "action",
        "status",
        "message_id",
        "clarification_id",
        "message_type",
        "visibility",
        "body_length",
        "body_hash",
    ):
        assert field in text, field


def test_66c3_contract_forbidden_fields_documented() -> None:
    text = CONTRACT_FILES["66c3-frontend-contract"].read_text(encoding="utf-8").lower()
    for forbidden in (
        "raw message body",
        "raw clarification answer",
        "headers",
        "cookies",
        "tokens",
        "secrets",
        ".env values",
        "raw full payload",
    ):
        assert forbidden in forbidden and forbidden.lower() in text, forbidden


def test_masking_rule_documented_everywhere() -> None:
    for name, p in ALL_DOCS.items():
        text_norm = _norm(p.read_text(encoding="utf-8"))
        assert "internal ip addresses" in text_norm, name


def test_no_production_action_documented() -> None:
    low = _all_low()
    assert "no production action" in low


def test_branch_naming_examples_present() -> None:
    text = PROCESS_DOCS["branch-pr-standard"].read_text(encoding="utf-8")
    for example in (
        "design/66d-delivery-inbox",
        "contract/66d-delivery-api",
        "frontend/66d-delivery-inbox",
        "backend/66d-delivery-api",
        "docs/66c3-operator-validation",
        "fix/66c3-ui-feedback",
    ):
        assert example in text, example


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in ALL_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
