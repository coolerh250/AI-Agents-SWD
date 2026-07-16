from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI4_FE1B1_MAPPING_CALIBRATION_VERIFY: PASS"

REQUIRED_FILES = [
    "docs/stages/66ui4-fe1b1-implementation/stage-manifest.yaml",
    "docs/stages/66ui4-fe1b1-implementation/context-receipt.md",
    "docs/stages/66ui4-fe1b1-implementation/stage-gate-report.md",
    "docs/frontend/66ui4-phase1-product-visual-language/fe1b1-safety-field-mapping-implementation-report.md",
    "docs/handoffs/66ui4-fe1b1/codex-to-claude-code-handoff.md",
    "docs/test/step66ui4-fe1b1-safety-field-mapping-test-report.md",
    "apps/admin-console/src/components/CalmSafetyPosture.tsx",
    "apps/admin-console/src/__tests__/CalmSafetyPosture.test.tsx",
]

FORBIDDEN_PREFIXES = [
    "apps/orchestrator/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    full = ROOT / path
    if not full.exists():
        fail(f"missing required file: {path}")
    return full.read_text(encoding="utf-8")


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def changed_paths() -> set[str]:
    paths = set(git_lines("diff", "--name-only", "main...HEAD"))
    paths.update(git_lines("diff", "--name-only"))
    paths.update(git_lines("diff", "--name-only", "--cached"))
    return paths


def assert_required_files() -> None:
    for path in REQUIRED_FILES:
        read(path)


def assert_manifest() -> None:
    manifest = read("docs/stages/66ui4-fe1b1-implementation/stage-manifest.yaml")
    for fragment in [
        'stage: "66UI.4-FE.1B.1"',
        'owner: "Codex"',
        'task_type: "frontend"',
        'status: "implementation"',
        "design_only: false",
        "frontend_only: true",
        "backend_allowed: false",
        "api_change_allowed: false",
        "database_change_allowed: false",
        "workflow_dispatch_allowed: false",
        "workflow_resume_allowed: false",
        "production_action_allowed: false",
        "external_action_allowed: false",
        "codex_authorized: true",
        "merge_authorization_required: true",
        "deployment_authorization_required: true",
        "product_owner_validation_required: true",
    ]:
        if fragment not in manifest:
            fail(f"manifest missing: {fragment}")


def assert_scope() -> None:
    changed = changed_paths()
    forbidden = sorted(
        path
        for path in changed
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    )
    if forbidden:
        fail(f"forbidden paths changed: {', '.join(forbidden)}")
    api_changes = sorted(path for path in changed if path.startswith("apps/admin-console/src/api/"))
    if api_changes:
        fail(f"frontend API contract/client changed: {', '.join(api_changes)}")


def assert_mapping() -> None:
    component = read("apps/admin-console/src/components/CalmSafetyPosture.tsx")
    automation_block = component.split("const AUTOMATION_FIELDS = [", 1)[1].split("] as const;", 1)[0]
    for retired in ["dispatch_enabled", "resume_dispatch_enabled"]:
        if f'"{retired}"' in automation_block:
            fail(f"retired field remains in global automation mapping: {retired}")
    for actual in [
        "task_api_workflow_dispatch_enabled",
        "task_workroom_resume_dispatch_enabled",
        "production_executed_true_count",
        "workflow_production_executed_true_count",
        "github_external_write_enabled",
        "discord_external_send_enabled",
        "llm_external_call_enabled",
        "production_delegation_allowed",
        "result",
    ]:
        if actual not in component:
            fail(f"required actual global evidence field missing: {actual}")
    for required in [
        "Not applicable at this endpoint",
        "Approvals are tracked per task. Review task details for approval requirements.",
        'endpointResult === "safe"',
        'boolState(data, "production_delegation_allowed") === false',
        "Evidence / details",
    ]:
        if required not in component:
            fail(f"mapping calibration requirement missing: {required}")
    if "work_item_dispatch_enabled" in component:
        fail("semantically different work_item_dispatch_enabled was used")


def assert_tests() -> None:
    tests = read("apps/admin-console/src/__tests__/CalmSafetyPosture.test.tsx")
    fixture = tests.split("const SAFE_SAFETY = {", 1)[1].split("};", 1)[0]
    for retired in [
        "dispatch_enabled",
        "resume_dispatch_enabled",
        "approval_required",
        "requires_approval",
    ]:
        if re.search(rf"^\s*{re.escape(retired)}\s*:", fixture, re.MULTILINE):
            fail(f"real-schema fixture incorrectly contains retired field: {retired}")
    for phrase in [
        "sanitized real-schema fixture",
        "task_api_workflow_dispatch_enabled",
        "task_workroom_resume_dispatch_enabled",
        "production action count is positive",
        "External integrations",
        "Not applicable at this endpoint",
        "production delegation evidence",
    ]:
        if phrase not in tests:
            fail(f"required frontend test coverage missing: {phrase}")


def assert_docs() -> None:
    docs = "\n".join(
        read(path)
        for path in [
            "docs/frontend/66ui4-phase1-product-visual-language/fe1b1-safety-field-mapping-implementation-report.md",
            "docs/handoffs/66ui4-fe1b1/codex-to-claude-code-handoff.md",
            "docs/test/step66ui4-fe1b1-safety-field-mapping-test-report.md",
            "docs/stages/66ui4-fe1b1-implementation/context-receipt.md",
            "docs/stages/66ui4-fe1b1-implementation/stage-gate-report.md",
            "source/progress.md",
        ]
    )
    for statement in [
        MARKER,
        "Codex authorization limited to FE.1B.1",
        "FE.1C/FE.1D not started",
        "frontend mapping calibration only",
        "Existing /operations/safety data only",
        "No /operations/safety response shape change",
        "Raw safety evidence remains accessible",
        "Conservative fallback",
        "Not applicable at this endpoint",
        "real-schema",
        "No production action",
        "No external action",
    ]:
        if statement.lower() not in docs.lower():
            fail(f"documentation missing required statement: {statement}")


def main() -> None:
    assert_required_files()
    assert_manifest()
    assert_scope()
    assert_mapping()
    assert_tests()
    assert_docs()
    print("[OK] FE.1B.1 mapping, evidence, conservative fallback, tests, and scope verified")
    print(MARKER)


if __name__ == "__main__":
    main()
