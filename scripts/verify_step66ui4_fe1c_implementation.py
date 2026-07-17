from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI4_FE1C_IMPLEMENTATION_VERIFY: PASS"

REQUIRED_FILES = [
    "docs/stages/66ui4-fe1c-implementation/stage-manifest.yaml",
    "docs/stages/66ui4-fe1c-implementation/context-receipt.md",
    "docs/stages/66ui4-fe1c-implementation/stage-gate-report.md",
    "docs/frontend/66ui4-fe1c-overview-attention-first/implementation-report.md",
    "docs/handoffs/66ui4-fe1c/codex-to-claude-code-handoff.md",
    "docs/test/step66ui4-fe1c-implementation-test-report.md",
    "apps/admin-console/src/pages/ExecutiveOverview.tsx",
    "apps/admin-console/src/__tests__/OverviewAttentionFirst.test.tsx",
]

FORBIDDEN_PREFIXES = [
    "apps/orchestrator/", "services/", "infra/", "migrations/", "database/",
    "helm/", "k8s/", ".github/workflows/",
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
        ["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode not in (0, 1):
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def changed_paths() -> set[str]:
    paths = set(git_lines("diff", "--name-only", "main...HEAD"))
    paths.update(git_lines("diff", "--name-only"))
    paths.update(git_lines("diff", "--name-only", "--cached"))
    return paths


def assert_manifest() -> None:
    manifest = read(REQUIRED_FILES[0])
    for fragment in [
        'stage: "66UI.4-FE.1C"', 'owner: "Codex"', 'task_type: "frontend"',
        'status: "implementation"', "frontend_only: true", "backend_allowed: false",
        "api_change_allowed: false", "database_change_allowed: false",
        "workflow_dispatch_allowed: false", "workflow_resume_allowed: false",
        "production_action_allowed: false", "external_action_allowed: false",
        "codex_authorized: true", "merge_authorization_required: true",
        "deployment_authorization_required: true", "product_owner_validation_required: true",
    ]:
        if fragment not in manifest:
            fail(f"manifest missing: {fragment}")


def assert_scope() -> None:
    changed = changed_paths()
    forbidden = sorted(path for path in changed if any(path.startswith(p) for p in FORBIDDEN_PREFIXES))
    if forbidden:
        fail(f"forbidden paths changed: {', '.join(forbidden)}")
    api_changes = sorted(path for path in changed if path.startswith("apps/admin-console/src/api/"))
    if api_changes:
        fail(f"frontend API client changed: {', '.join(api_changes)}")


def assert_implementation() -> None:
    source = read("apps/admin-console/src/pages/ExecutiveOverview.tsx")
    tests = read("apps/admin-console/src/__tests__/OverviewAttentionFirst.test.tsx")
    for fragment in [
        'status: "clarification_needed"', 'status: "blocked"', ".slice(0, 5)",
        "timestamp(b.updated_at) - timestamp(a.updated_at)", 'status === "completed"',
        'status === "failed"', 'return "Not reported"', "Needs your attention",
        "AI team activity", "Current work", "System posture", "Platform &amp; delivery metrics",
        "Requires Step 66D", "Requires Step 66C.4", "showDetails={false}", 'to="/safety"',
    ]:
        if fragment not in source:
            fail(f"implementation requirement missing: {fragment}")
    for phrase in [
        "exactly five current tasks sorted by updated_at descending",
        "maps only observed contract statuses", "without fake counts or controls",
        "uses calm empty states",
    ]:
        if phrase not in tests:
            fail(f"frontend test coverage missing: {phrase}")
    if "dangerouslySetInnerHTML" in source:
        fail("raw HTML rendering introduced")


def assert_docs() -> None:
    docs = "\n".join(read(path) for path in REQUIRED_FILES[:6]) + "\n" + read("source/progress.md")
    for statement in [
        MARKER, "Existing-data-only", "five", "updated_at", "Observed live status values: none",
        "blocking Claude Code review dependency", "No new endpoint", "No fake counts",
        "No fake controls", "FE.1D remains unauthorized", "Product Owner validation remains pending",
        "No backend", "API", "database", "workflow",
    ]:
        if statement.lower() not in docs.lower():
            fail(f"documentation missing required statement: {statement}")


def main() -> None:
    for path in REQUIRED_FILES:
        read(path)
    assert_manifest()
    assert_scope()
    assert_implementation()
    assert_docs()
    print("[OK] FE.1C hierarchy, data mapping, tests, artifacts, and scope verified")
    print(MARKER)


if __name__ == "__main__":
    main()
