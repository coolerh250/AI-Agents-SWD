from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI4_FE1D_S1_IMPLEMENTATION_VERIFY: PASS"

REQUIRED_FILES = [
    "docs/stages/66ui4-fe1d-s1-navigation-polish/stage-manifest.yaml",
    "docs/stages/66ui4-fe1d-s1-navigation-polish/context-receipt.md",
    "docs/stages/66ui4-fe1d-s1-navigation-polish/stage-gate-report.md",
    "docs/frontend/66ui4-fe1d-navigation-microcopy/slice1-navigation-polish-implementation-report.md",
    "docs/handoffs/66ui4-fe1d-s1/codex-to-claude-code-handoff.md",
    "docs/test/step66ui4-fe1d-s1-navigation-polish-implementation-test-report.md",
    "apps/admin-console/src/components/Nav.tsx",
    "apps/admin-console/src/components/NavGroup.tsx",
    "apps/admin-console/src/styles.css",
    "apps/admin-console/src/__tests__/NavigationGrouping.test.tsx",
]

ALLOWED_FRONTEND_CHANGES = {
    "apps/admin-console/src/components/Nav.tsx",
    "apps/admin-console/src/components/NavGroup.tsx",
    "apps/admin-console/src/styles.css",
    "apps/admin-console/src/__tests__/NavigationGrouping.test.tsx",
}

FORBIDDEN_PREFIXES = [
    "apps/orchestrator/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
    "apps/admin-console/src/features/",
]

FORBIDDEN_EXACT = {
    "apps/admin-console/src/App.tsx",
}


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


def assert_manifest() -> None:
    manifest = read(REQUIRED_FILES[0])
    for fragment in [
        'stage: "66UI.4-FE.1D-S1"',
        'owner: "Codex"',
        'task_type: "frontend"',
        'status: "implementation"',
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
        if path in FORBIDDEN_EXACT or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    )
    if forbidden:
        fail(f"forbidden paths changed: {', '.join(forbidden)}")
    frontend = {path for path in changed if path.startswith("apps/admin-console/")}
    unexpected = sorted(frontend - ALLOWED_FRONTEND_CHANGES)
    if unexpected:
        fail(f"unexpected frontend scope: {', '.join(unexpected)}")


def assert_nav_implementation() -> None:
    nav = read("apps/admin-console/src/components/Nav.tsx")
    nav_group = read("apps/admin-console/src/components/NavGroup.tsx")
    styles = read("apps/admin-console/src/styles.css")
    tests = read("apps/admin-console/src/__tests__/NavigationGrouping.test.tsx")

    for fragment in [
        'badge?: "Soon" | "Read-only" | "Evidence"',
        "subtitle?: string",
        'label: "Platform Ops"',
        "defaultExpanded: false",
        "compact: true",
        'to: "/delivery-package"',
        'label: "Delivery Package"',
        'subtitle: "Delivery evidence / package record"',
        'badge: "Evidence"',
        'label: "Work Items"',
        'label: "Task Graph"',
        'label: "Sandbox GitHub"',
        'label: "Backup & DR"',
        'label: "Production Readiness"',
        'label: "Rollout Review"',
    ]:
        if fragment not in nav:
            fail(f"Nav polish missing: {fragment}")

    for fragment in [
        "nav-group-subtitle",
        "nav-item-badge",
        "nav-group-compact",
        "nav-item-subtitle",
    ]:
        if fragment not in nav_group + styles:
            fail(f"rendering or style support missing: {fragment}")

    for fragment in [
        "EXPECTED_NAV_ROUTES",
        "renders FE.1D-S1 group subtitles",
        "marks planned placeholder nav items with Soon",
        "renders read-only and evidence badges",
        "keeps Platform Ops compact",
        "does not introduce FE.1D Slice 2 text changes",
    ]:
        if fragment not in tests:
            fail(f"frontend test coverage missing: {fragment}")


def assert_docs() -> None:
    docs = "\n".join(read(path) for path in REQUIRED_FILES[:6]) + "\n" + read("source/progress.md")
    for statement in [
        MARKER,
        "Nav polish",
        "Group subtitles",
        "Soon",
        "Read-only",
        "Evidence",
        "Platform Ops compact",
        "Delivery Package remains under Platform Ops",
        "No route",
        "No backend",
        "No API",
        "No database",
        "No workflow",
        "No new endpoint",
        "No new route",
        "Slice 2",
        "+ Create task",
        "delivery_package_ready_for_admin_console",
        "SPA deep-link fallback",
        "Product Owner validation",
    ]:
        if statement.lower() not in docs.lower():
            fail(f"documentation missing required statement: {statement}")


def assert_forbidden_source_strings() -> None:
    app = read("apps/admin-console/src/App.tsx")
    task_list = read("apps/admin-console/src/pages/TaskList.tsx")
    overview = read("apps/admin-console/src/pages/ExecutiveOverview.tsx")
    if "+ Create task" not in task_list:
        fail("+ Create task changed or removed")
    if "Ready to publish" in overview:
        fail("delivery package ready label was renamed in FE.1D-S1")
    if 'path="/delivery-package"' not in app:
        fail("Delivery Package route missing")
    if 'path="/delivery-inbox"' not in app or 'path="/delivery-detail"' not in app:
        fail("Delivery placeholder routes missing")


def main() -> None:
    for path in REQUIRED_FILES:
        read(path)
    assert_manifest()
    assert_scope()
    assert_nav_implementation()
    assert_docs()
    assert_forbidden_source_strings()
    print("[OK] FE.1D-S1 navigation polish, artifacts, tests, and scope verified")
    print(MARKER)


if __name__ == "__main__":
    main()
