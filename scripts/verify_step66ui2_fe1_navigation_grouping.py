#!/usr/bin/env python3
"""Step 66UI.2-FE.1 -- frontend navigation grouping verifier.

Checks the Admin Console grouped navigation shell, placeholder safety rules,
route preservation, and scope boundaries for the frontend-only implementation.

Marker: STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY"

APP = ROOT / "apps" / "admin-console" / "src" / "App.tsx"
NAV = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"
NAV_GROUP = ROOT / "apps" / "admin-console" / "src" / "components" / "NavGroup.tsx"
PLACEHOLDER = ROOT / "apps" / "admin-console" / "src" / "components" / "PlaceholderPanel.tsx"
SAFETY_BAR = ROOT / "apps" / "admin-console" / "src" / "components" / "SafetyStatusBar.tsx"
NAV_TEST = ROOT / "apps" / "admin-console" / "src" / "__tests__" / "NavigationGrouping.test.tsx"

REPORT = ROOT / "docs" / "frontend" / "66ui2-navigation-ia" / "fe1-navigation-grouping-implementation-report.md"
GAPS = ROOT / "docs" / "frontend" / "66ui2-navigation-ia" / "fe1-open-questions-and-gaps.md"
HANDOFF = ROOT / "docs" / "handoffs" / "66ui2-navigation-ia" / "codex-to-claude-code-handoff.md"
TEST_REPORT = ROOT / "docs" / "test" / "step66ui2-fe1-navigation-grouping-test-report.md"
PROGRESS = ROOT / "source" / "progress.md"

GROUPS = (
    "Overview",
    "Team Work",
    "Deliveries",
    "Operator Center",
    "Governance",
    "Platform Ops",
    "Settings",
)

EXISTING_ROUTES = (
    "/",
    "/tasks",
    "/tasks/new",
    "/tasks/:taskId/workroom",
    "/tasks/:taskId",
    "/demo-evidence",
    "/agent-executions",
    "/qa-code",
    "/audit-evidence",
    "/projects",
    "/projects/:projectId",
    "/task-graph",
    "/design-review",
    "/workspace",
    "/mini-delivery",
    "/delivery-package",
    "/safety",
    "/regression",
    "/cost-llm",
    "/incidents",
    "/operator",
    "/runtime",
    "/identity",
    "/secrets",
    "/security",
    "/delivery",
    "/metrics",
    "/sandbox-github",
    "/release-governance",
    "/backup-dr",
    "/production-readiness",
    "/controlled-rollout-review",
)

PLACEHOLDER_ROUTES = {
    "/delivery-inbox": "66D",
    "/delivery-detail": "66D",
    "/clarifications": "66C.4",
    "/clarification-reminders": "66C.4",
    "/approvals": "66D",
    "/dlq-retry": "66D",
    "/settings/roles-permissions": "66S",
    "/settings/identity-session": "66S",
    "/settings/integrations": "66S or later",
    "/settings/web-research-sources": "66S or later",
    "/settings/approval-policy": "66S or later",
}

FORBIDDEN_CHANGED_PREFIXES = (
    "apps/orchestrator/",
    "apps/policy-engine/",
    "apps/approval-engine/",
    "apps/audit-service/",
    "apps/audit-worker/",
    "migrations/",
    "infra/",
    "shared/",
    "docs/contracts/",
)

FORBIDDEN_SOURCE_PATTERNS = (
    re.compile(r"dangerouslySetInnerHTML"),
    re.compile(r"\bdraggable\b|onDrag|dragStart|drop=", re.IGNORECASE),
    re.compile(r"Dispatch Workflow|Resume Workflow|Production Action", re.IGNORECASE),
    re.compile(r"\b(taskPost|workroomPost|apiPost|apiPut|apiPatch|apiDelete)\b"),
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|p[@]ssw0rd)"
)
INFRA_SHAPES = re.compile(r"(10[.]0[.]1[.](31|32)|it[a]dmin)", re.IGNORECASE)

failures: list[str] = []


def bad(message: str) -> None:
    failures.append(message)
    print(f"  [FAIL] {message}")


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing file: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


def git_status_paths() -> list[str]:
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        bad("git status failed")
        return []

    paths: list[str] = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        raw = line[3:].replace("\\", "/")
        if " -> " in raw:
            paths.extend(raw.split(" -> "))
        else:
            paths.append(raw)
    return paths


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        bad(f"{label} missing {needle!r}")


def main() -> int:
    app = read(APP)
    nav = read(NAV)
    nav_group = read(NAV_GROUP)
    placeholder = read(PLACEHOLDER)
    safety = read(SAFETY_BAR)
    nav_test = read(NAV_TEST)
    report = read(REPORT)
    gaps = read(GAPS)
    handoff = read(HANDOFF)
    test_report = read(TEST_REPORT)
    progress = read(PROGRESS)

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    for group in GROUPS:
        assert_contains(nav, f'label: "{group}"', "Nav groups")

    if 'id: "platform-ops"' not in nav or "defaultExpanded: false" not in nav:
        bad("Platform Ops is not configured as a collapsed group")
    if "collapsible: true" not in nav:
        bad("Platform Ops is not expandable")

    deliveries_section = re.search(r'id: "deliveries".*?id: "operator-center"', nav, re.DOTALL)
    if not deliveries_section:
        bad("Deliveries group not found")
    elif 'to: "/delivery-package"' in deliveries_section.group(0):
        bad("Delivery Package must not be in the Deliveries group")
    elif 'to: "/delivery-inbox"' not in deliveries_section.group(0) or 'to: "/delivery-detail"' not in deliveries_section.group(0):
        bad("Deliveries group must keep only the 66D delivery placeholders")

    platform_ops_section = re.search(r'id: "platform-ops".*?id: "settings"', nav, re.DOTALL)
    if not platform_ops_section or 'to: "/delivery-package"' not in platform_ops_section.group(0):
        bad("Delivery Package must be preserved under the Platform Ops group")

    if "/demo-evidence" in nav:
        bad("Demo Evidence still appears in navigation")
    assert_contains(app, 'path="/demo-evidence"', "App routes")

    for route in EXISTING_ROUTES:
        assert_contains(app, f'path="{route}"', "Existing route preservation")

    for route, step in PLACEHOLDER_ROUTES.items():
        assert_contains(app, f'path="{route}"', "Placeholder route")
        assert_contains(app, f'requiredStep="{step}"', "Placeholder step")

    for text in (
        "Not yet available.",
        "Requires Step {requiredStep}.",
        "No workflow action available.",
    ):
        assert_contains(placeholder, text, "PlaceholderPanel")

    for text in ("getSafety", "production_executed_true_count", "dispatch_enabled", "resume_dispatch_enabled"):
        assert_contains(safety, text, "SafetyStatusBar")

    for text in ("useLocation", "aria-expanded", "setExpanded"):
        assert_contains(nav_group, text, "NavGroup")

    for text in (
        "renders the seven required navigation groups",
        "Requires Step 66D.",
        "Requires Step 66C.4.",
        "Delivery Package under Platform Ops",
        "does not introduce drag/drop",
    ):
        assert_contains(nav_test, text, "NavigationGrouping frontend test")

    for path in git_status_paths():
        if any(path.startswith(prefix) for prefix in FORBIDDEN_CHANGED_PREFIXES):
            bad(f"forbidden scoped path changed: {path}")

    scoped_source = "\n".join([app, nav, nav_group, placeholder, safety])
    for pattern in FORBIDDEN_SOURCE_PATTERNS:
        if pattern.search(scoped_source):
            bad(f"forbidden source pattern found: {pattern.pattern}")

    for text in (
        "What Changed",
        "Files Changed",
        "Routes Preserved",
        "Navigation Groups Implemented",
        "Placeholder Pages Implemented",
        "Tests Added",
        "Build Result",
        "Safety Constraints Preserved",
        "Known Gaps",
        "Items Requiring Claude Code Review",
        "Items Requiring Product Owner Validation",
    ):
        assert_contains(handoff, text, "Codex to Claude Code handoff")

    for text in (
        "Open Questions",
        "Delivery Package group placement",
        "Safety status bar field contract",
        "Implementation Limits",
        "Review Requests",
    ):
        assert_contains(gaps, text, "Open questions and gaps")

    authored_text = "\n".join(
        [app, nav, nav_group, placeholder, safety, nav_test, report, gaps, handoff, test_report]
    )
    if SECRET_SHAPES.search(authored_text) or INFRA_SHAPES.search(authored_text):
        bad("authored frontend/report content contains secret-shaped or internal-infra content")

    for text in (
        "STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY: PASS",
        "Navigation Grouping / IA Shell",
    ):
        assert_contains(report + "\n" + gaps + "\n" + handoff + "\n" + test_report + "\n" + progress, text, "Docs/progress")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] grouped navigation, route preservation, safe placeholders, Platform Ops collapse, "
        "Demo Evidence direct-route handling, safety bar, tests, docs, and frontend-only scope verified"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
