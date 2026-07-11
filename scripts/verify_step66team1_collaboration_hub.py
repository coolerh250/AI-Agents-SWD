#!/usr/bin/env python3
"""Step 66TEAM.1 -- GitHub Team Collaboration Hub & Development Protocol verifier.

Confirms the full docs/process, docs/design, docs/contracts, docs/frontend,
docs/handoffs, docs/decisions structure and the .github issue/PR templates
exist, that the 66C.3 frontend contract exists, that the public-repo masking
rule and no-production-action posture are documented, and that this stage's
docs do not themselves contain any runtime code (a light proxy for "no
runtime code changed").

Marker: STEP66TEAM1_COLLABORATION_HUB_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
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

# A light proxy for "no runtime code changed": none of this stage's own docs
# should contain a fenced code block that looks like actual runtime source
# (import/export/def/class of real project modules), only illustrative
# snippets/templates.
_RUNTIME_CODE_MARKERS = (
    "from fastapi import",
    "import asyncpg",
    "from shared.sdk",
    "@router.",
)

MARKER = "STEP66TEAM1_COLLABORATION_HUB_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in ALL_DOCS.items():
        if not p.is_file():
            bad(f"missing file: {p} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in ALL_DOCS.items()}
    # Collapse whitespace (incl. markdown line-wrap newlines) so substring checks
    # don't break on a phrase that happens to wrap across a line.
    low = re.sub(r"\s+", " ", "\n".join(texts.values()).lower())

    if "role" not in low or "responsibility" not in low:
        bad("role responsibility matrix content not found")
    if "single source of truth" not in low:
        bad("github collaboration hub content (single source of truth) not found")
    if "branch" not in low or "pull request" not in low:
        bad("branch/PR naming standard content not found")
    if "visible" not in low or "not_visible" not in low or "partial_with_gaps" not in low:
        bad("operator validation response values not documented")
    if "pass_with_gaps" not in low or "fail" not in low:
        bad("implementation-completion response values (PASS/PASS_WITH_GAPS/FAIL) not documented")

    if "audit_event_id" not in low or "body_hash" not in low:
        bad("66C.3 frontend contract allowed fields not documented")
    if "raw message body" not in low or "raw clarification answer" not in low:
        bad("66C.3 frontend contract forbidden fields not documented")

    masking_phrase = "internal ip addresses"
    if masking_phrase not in low:
        bad("public repo masking rule not documented")

    for phrase in ("no production action",):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    for name, text in texts.items():
        text_low = text.lower()
        for marker in _RUNTIME_CODE_MARKERS:
            if marker.lower() in text_low:
                bad(
                    f"{name} appears to contain real runtime source, not a template/illustration: {marker}"
                )

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] process/design/contracts/frontend/handoffs/decisions docs present;")
    print("       .github issue + PR templates present; 66C.3 frontend contract present;")
    print("       operator validation values + masking rule + no-production-action documented;")
    print("       no runtime source detected in these docs")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
