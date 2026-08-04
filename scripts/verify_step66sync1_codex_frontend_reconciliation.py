from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


MARKER = "STEP66SYNC1_CODEX_FRONTEND_RECONCILIATION_VERIFY: PASS"
REPO = Path(__file__).resolve().parents[1]

ACK_DOC = REPO / "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md"
GAP_DOC = REPO / "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md"
EVIDENCE_DOC = REPO / "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
SCRIPT = REPO / "scripts/verify_step66sync1_codex_frontend_reconciliation.py"
TEST_FILE = REPO / "tests/test_step66sync1_codex_frontend_reconciliation.py"
APP_TSX = REPO / "apps/admin-console/src/App.tsx"

REQUIRED_FILES = [ACK_DOC, GAP_DOC, EVIDENCE_DOC, SCRIPT, TEST_FILE]

REQUIRED_TOKENS = [
    "AIAT-SYNC-20260803-01",
    "c1db4cc",
    "828ea90",
    "STEP66SYNC1_CLAUDE_CODE_RECONCILIATION_VERIFY: PASS",
    "STEP66SYNC1_A1_CONTEXT_TAXONOMY_VERIFY: PASS",
    MARKER,
    "UNRESOLVED_CANONICAL_MISMATCHES: 0",
    "OPEN_PRODUCT_OWNER_DECISIONS: 3",
    "production_executed_true_count=0",
    "Implementation started:\nNO",
    "D-1",
    "D-2",
    "D-3",
    "DECISION_DEPENDENT",
]

KEY_ROUTES = [
    "/",
    "/tasks",
    "/tasks/new",
    "/tasks/:taskId",
    "/tasks/:taskId/workroom",
    "/delivery",
    "/agent-executions",
    "/task-graph",
    "/qa-code",
    "/audit-evidence",
    "/safety",
    "/approvals",
    "/dlq-retry",
    "/metrics",
    "/demo-evidence",
    "/delivery-inbox",
    "/delivery-detail",
]

CONTROL_CENTER_AREAS = [
    "Goal and Acceptance",
    "Work Items and Task Graph",
    "Agent and Partner Activity Timeline",
    "Artifacts and Evidence",
    "Approvals, Blockers and Failures",
    "QA, Delivery and Final Acceptance",
]

POC_QUESTIONS = [
    "What is currently being worked on?",
    "Which Agent or AI partner is responsible?",
    "Which requirement does the work correspond to?",
    "What generation mode is currently used?",
    "Which artifacts are complete?",
    "What commits, branches, or Draft PRs exist?",
    "Which step failed or retried?",
    "Did it enter DLQ?",
    "Who needs to approve?",
    "Did QA pass?",
    "Is it deliverable now?",
    "How much LLM cost?",
    "How many external actions occurred?",
    "What is production action count?",
    "Has PO accepted delivery?",
]

API_AREAS = [
    "Projects",
    "Work items",
    "Tasks",
    "Workflows",
    "Agent executions",
    "Partner executions",
    "Task graph",
    "Approvals",
    "Audit",
    "QA",
    "Code evidence",
    "Delivery",
    "Failures/DLQ",
    "Cost",
    "Safety",
    "PO acceptance",
]

FORBIDDEN_SOURCE_PREFIXES = (
    "apps/",
    "services/",
    "infra/",
    "shared/",
    "migrations/",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"VERIFY FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def route_paths_from_app() -> list[str]:
    text = read(APP_TSX)
    return re.findall(r'<Route\s+path="([^"]+)"', text)


def assert_required_files() -> None:
    missing = [str(path.relative_to(REPO)) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def assert_required_tokens() -> None:
    combined = "\n".join(read(path) for path in [ACK_DOC, GAP_DOC, EVIDENCE_DOC])
    missing = [token for token in REQUIRED_TOKENS if token not in combined]
    if missing:
        fail(f"missing required tokens: {', '.join(missing)}")


def assert_routes_inventoried() -> None:
    evidence = read(EVIDENCE_DOC)
    routes = route_paths_from_app()
    if not routes:
        fail("no routes parsed from App.tsx")

    missing = [route for route in routes if f"| `{route}` |" not in evidence]
    if missing:
        fail(f"routes missing from evidence inventory: {', '.join(missing)}")

    missing_key = [route for route in KEY_ROUTES if route not in routes or f"| `{route}` |" not in evidence]
    if missing_key:
        fail(f"key routes missing from source or evidence: {', '.join(missing_key)}")


def assert_control_center_and_questions() -> None:
    evidence = read(EVIDENCE_DOC)
    missing_areas = [area for area in CONTROL_CENTER_AREAS if area not in evidence]
    if missing_areas:
        fail(f"missing control center areas: {', '.join(missing_areas)}")

    missing_questions = [question for question in POC_QUESTIONS if question not in evidence]
    if missing_questions:
        fail(f"missing POC questions: {', '.join(missing_questions)}")

    for classification in ["YES: 1", "PARTIAL: 10", "NO: 2", "DECISION_DEPENDENT: 2"]:
        if classification not in evidence:
            fail(f"missing POC classification summary: {classification}")


def assert_api_inventory() -> None:
    evidence = read(EVIDENCE_DOC)
    missing_areas = [area for area in API_AREAS if f"| {area} |" not in evidence]
    if missing_areas:
        fail(f"missing API inventory areas: {', '.join(missing_areas)}")

    required_fragments = [
        "| Partner executions | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED |",
        "| Approvals | Placeholder only | NOT_IMPLEMENTED for UI | NOT_IMPLEMENTED |",
        "| PO acceptance | latest delivery state only; formal inbox/detail missing | partial |",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in evidence]
    if missing:
        fail(f"missing API gap fragments: {', '.join(missing)}")


def assert_no_runtime_source_changes() -> None:
    changed = git_lines("diff", "--name-only", "HEAD", "--", "apps", "services", "infra", "shared", "migrations")
    staged = git_lines(
        "diff",
        "--cached",
        "--name-only",
        "--",
        "apps",
        "services",
        "infra",
        "shared",
        "migrations",
    )
    if changed or staged:
        fail(f"runtime/source files changed: {', '.join(changed + staged)}")


def assert_allowed_tracked_changes() -> None:
    allowed_exact = {
        "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
        "tests/test_step66sync1_codex_frontend_reconciliation.py",
    }
    allowed_prefixes = ("docs/handoffs/program-sync/", "docs/test/")
    tracked = set(git_lines("diff", "--name-only", "HEAD"))
    tracked.update(git_lines("diff", "--cached", "--name-only"))

    forbidden = [
        path
        for path in sorted(tracked)
        if path not in allowed_exact and not any(path.startswith(prefix) for prefix in allowed_prefixes)
    ]
    if forbidden:
        fail(f"tracked changes outside allowed paths: {', '.join(forbidden)}")

    source_changes = [path for path in tracked if path.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if source_changes:
        fail(f"forbidden source changes present: {', '.join(source_changes)}")


def main() -> int:
    assert_required_files()
    assert_required_tokens()
    assert_routes_inventoried()
    assert_control_center_and_questions()
    assert_api_inventory()
    assert_no_runtime_source_changes()
    assert_allowed_tracked_changes()
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
