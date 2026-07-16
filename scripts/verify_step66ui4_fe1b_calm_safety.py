from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MARKER = "STEP66UI4_FE1B_CALM_SAFETY_VERIFY: PASS"

REQUIRED_FILES = [
    "docs/stages/66ui4-fe1b/stage-manifest.yaml",
    "docs/stages/66ui4-fe1b/context-receipt.md",
    "docs/stages/66ui4-fe1b/stage-gate-report.md",
    "docs/frontend/66ui4-phase1-product-visual-language/fe1b-calm-safety-implementation-report.md",
    "docs/handoffs/66ui4-fe1b/codex-to-claude-code-handoff.md",
    "docs/test/step66ui4-fe1b-calm-safety-test-report.md",
    "apps/admin-console/src/components/CalmSafetyPosture.tsx",
    "apps/admin-console/src/components/SafetyStatusBar.tsx",
    "apps/admin-console/src/pages/SafetyCenter.tsx",
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

REQUIRED_RAW_FIELDS = [
    "production_executed_true_count",
    "workflow_production_executed_true_count",
    "dispatch_enabled",
    "resume_dispatch_enabled",
    "task_api_workflow_dispatch_enabled",
    "task_workroom_resume_dispatch_enabled",
    "github_external_write_enabled",
    "discord_external_send_enabled",
    "llm_external_call_enabled",
    "production_delegation_allowed",
    "approval_required",
    "requires_approval",
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
    manifest = read("docs/stages/66ui4-fe1b/stage-manifest.yaml")
    required_fragments = [
        'stage: "66UI.4-FE.1B"',
        'owner: "Codex"',
        'task_type: "frontend"',
        "codex_authorized: true",
        "frontend_only: true",
        "backend_allowed: false",
        "api_change_allowed: false",
        "database_change_allowed: false",
        "workflow_dispatch_allowed: false",
        "workflow_resume_allowed: false",
        "production_action_allowed: false",
        "external_action_allowed: false",
    ]
    for fragment in required_fragments:
        if fragment not in manifest:
            fail(f"manifest missing: {fragment}")


def assert_scope() -> None:
    changed = changed_paths()
    forbidden = [
        path
        for path in changed
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    ]
    if forbidden:
        fail(f"forbidden paths changed: {', '.join(sorted(forbidden))}")


def assert_runtime() -> None:
    component = read("apps/admin-console/src/components/CalmSafetyPosture.tsx")
    status_bar = read("apps/admin-console/src/components/SafetyStatusBar.tsx")
    safety_center = read("apps/admin-console/src/pages/SafetyCenter.tsx")
    combined = component + "\n" + status_bar + "\n" + safety_center

    for field in REQUIRED_RAW_FIELDS:
        if field not in component:
            fail(f"raw safety evidence field not preserved in CalmSafetyPosture: {field}")

    required_copy = [
        "Safe - no automated or production actions will run.",
        "No production actions have run",
        "Automated workflow dispatch",
        "External integrations",
        "Safety status unavailable - check system evidence.",
        "Evidence / details",
        "/operations/safety",
    ]
    for copy in required_copy:
        if copy not in combined:
            fail(f"calm safety copy missing: {copy}")

    forbidden_runtime = [
        "dangerouslySetInnerHTML",
        "workflowDispatch",
        "resumeWorkflow",
        "new safety endpoint",
        "new safety computation",
    ]
    lower = combined.lower()
    for phrase in forbidden_runtime:
        if phrase.lower() in lower:
            fail(f"forbidden runtime phrase found: {phrase}")


def assert_docs() -> None:
    docs = "\n".join(
        read(path)
        for path in [
            "docs/frontend/66ui4-phase1-product-visual-language/fe1b-calm-safety-implementation-report.md",
            "docs/handoffs/66ui4-fe1b/codex-to-claude-code-handoff.md",
            "docs/test/step66ui4-fe1b-calm-safety-test-report.md",
            "docs/stages/66ui4-fe1b/context-receipt.md",
            "docs/stages/66ui4-fe1b/stage-gate-report.md",
            "source/progress.md",
        ]
    )
    required = [
        MARKER,
        "Codex authorization limited to FE.1B",
        "FE.1C/FE.1D not started",
        "Existing /operations/safety data only",
        "Raw safety evidence remains accessible",
        "No new safety endpoint",
        "No new safety computation",
        "No Delivery real UI",
        "No Reminder/Expiry real UI",
        "No Pipeline board",
        "No drag/drop",
        "No new agent activity model",
        "No production action",
        "No external action",
    ]
    for text in required:
        if text not in docs:
            fail(f"documentation missing required statement: {text}")


def main() -> None:
    assert_required_files()
    assert_manifest()
    assert_scope()
    assert_runtime()
    assert_docs()
    print("[OK] FE.1B artifacts, calm safety posture, raw evidence, and scope boundaries verified")
    print(MARKER)


if __name__ == "__main__":
    main()
