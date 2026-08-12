"""Step 66D-BE1 -- scope, boundary and verifier tests for the persistence foundation.

Re-derives every fact the verifier asserts from git, the migration and the source, rather than
trusting the verifier's own output. Two of these tests guard the guard: they confirm the scope
registry is an exact set and that the D05 index check would actually fail if the index stopped
being partial.

Read-only. Starts no runtime, container, database or external provider.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_step66d_be1_persistence_foundation.py"
MIGRATION = ROOT / "migrations" / "036_delivery_acceptance_persistence.sql"
MODEL = ROOT / "shared" / "sdk" / "delivery_acceptance" / "acceptance_model.py"
REPOSITORY = ROOT / "shared" / "sdk" / "delivery_acceptance" / "acceptance_repository.py"
EVIDENCE = (
    ROOT
    / "docs"
    / "handoffs"
    / "66d-delivery-acceptance"
    / "step66d-be1-persistence-foundation-evidence.md"
)

BE1_BASELINE = "2d4da808b1a89ea278fbb760e27f49047995165e"

EXPECTED_PATHS = {
    "migrations/036_delivery_acceptance_persistence.sql",
    "migrations/036_delivery_acceptance_persistence_down.sql",
    "shared/sdk/delivery_acceptance/__init__.py",
    "shared/sdk/delivery_acceptance/acceptance_model.py",
    "shared/sdk/delivery_acceptance/acceptance_repository.py",
    "tests/test_step66d_be1_delivery_acceptance_persistence.py",
    "tests/test_step66d_be1_persistence_foundation.py",
    "scripts/verify_step66d_be1_persistence_foundation.py",
    "docs/handoffs/66d-delivery-acceptance/step66d-be1-persistence-foundation-evidence.md",
}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def changed_paths() -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{BE1_BASELINE}...HEAD").splitlines()
        if line.strip()
    }


def statements() -> str:
    lines = []
    for line in MIGRATION.read_text(encoding="utf-8").splitlines():
        code = line.split("--", 1)[0]
        if code.strip():
            lines.append(code)
    return "\n".join(lines)


def executable_python(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# ---- Baseline and scope -------------------------------------------------------------------------


def test_baseline_is_the_canonical_main_and_an_ancestor():
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", BE1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0
    )


def test_verifier_pins_the_exact_canonical_baseline():
    source = VERIFIER.read_text(encoding="utf-8")
    assert f'BE1_BASELINE = "{BE1_BASELINE}"' in source


def test_changed_paths_equal_the_registry_exactly():
    changed = changed_paths()
    assert (
        changed == EXPECTED_PATHS
    ), f"unexpected={sorted(changed - EXPECTED_PATHS)} missing={sorted(EXPECTED_PATHS - changed)}"


def test_scope_registry_is_a_set_equality_not_a_prefix_match():
    """Guard the guard: the verifier must compare by equality, never by a broad positive prefix."""
    source = VERIFIER.read_text(encoding="utf-8")
    assert "changed == BE1_EXPECTED_PATHS" in source
    assert "startswith" not in source.split("BE1_EXPECTED_PATHS = ")[1].split(")")[0]


def test_no_frontend_api_infra_or_deployment_path_changed():
    forbidden = (
        "apps/",
        "agents/",
        "services/",
        "frontend/",
        "infra/",
        "helm/",
        "k8s/",
        ".github/workflows/",
        "runtime/",
        "deploy/",
    )
    assert [p for p in changed_paths() if p.startswith(forbidden)] == []


def test_progress_md_and_rbac_and_legacy_migration_are_untouched():
    changed = changed_paths()
    assert "source/progress.md" not in changed
    assert "shared/sdk/tasks/rbac.py" not in changed
    assert "migrations/021_delivery_package_acceptance_gate.sql" not in changed
    assert "scripts/run_platform_migrations.py" not in changed


def test_no_historical_verifier_or_test_was_modified():
    changed = changed_paths()
    historical = [
        p
        for p in changed
        if (p.startswith("tests/") or p.startswith("scripts/verify_")) and "step66d_be1_" not in p
    ]
    assert historical == [], f"historical test/verifier modified: {historical}"


# ---- Migration facts, re-derived ----------------------------------------------------------------


def test_migration_036_is_the_next_migration_number():
    numbers = sorted(
        int(p.name[:3])
        for p in (ROOT / "migrations").glob("*.sql")
        if p.name[:3].isdigit() and not p.name.endswith("_down.sql")
    )
    assert max(numbers) == 36
    assert numbers.count(36) == 1


def test_migration_creates_five_tables_and_no_more():
    created = sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", statements()))
    assert created == [
        "acceptance_follow_up_items",
        "delivery_review_actions",
        "delivery_review_tasks",
        "delivery_submissions",
        "product_owner_decisions",
    ]


def test_d05_index_is_unique_and_partial():
    sql = statements()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission" in sql
    block = sql[sql.index("uq_drt_active_per_submission") :][:300]
    assert "ON delivery_review_tasks (delivery_submission_id)" in block
    assert "WHERE closed_at IS NULL" in block


def _verifier_module():
    spec = importlib.util.spec_from_file_location("step66d_be1_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifier_partial_index_check_rejects_a_plain_unique():
    """Guard the guard: feed the verifier's own extraction a migration in which the D05 index is a
    plain UNIQUE, and confirm the partial-index condition stops holding."""
    module = _verifier_module()
    original = MIGRATION.read_text(encoding="utf-8")
    mutated = original.replace(
        "    ON delivery_review_tasks (delivery_submission_id)\n    WHERE closed_at IS NULL;",
        "    ON delivery_review_tasks (delivery_submission_id);",
    )
    assert mutated != original, "the mutation did not apply -- the probe would be vacuous"

    def partial_predicate_present(text: str) -> bool:
        stmts = module.sql_statements(text)
        block = stmts[stmts.find("uq_drt_active_per_submission") :][:300]
        return "WHERE closed_at IS NULL" in block

    assert partial_predicate_present(original) is True
    assert partial_predicate_present(mutated) is False


def test_verifier_lifecycle_check_rejects_a_status_column():
    """Guard the guard: reintroduce a status column on delivery_review_tasks and confirm the
    verifier's own DDL extraction surfaces it."""
    module = _verifier_module()
    original = MIGRATION.read_text(encoding="utf-8")
    mutated = original.replace(
        "    closed_at                TIMESTAMPTZ,",
        "    status                   TEXT NOT NULL DEFAULT 'OPEN',\n"
        "    closed_at                TIMESTAMPTZ,",
    )
    assert mutated != original, "the mutation did not apply -- the probe would be vacuous"

    def has_status_column(text: str) -> bool:
        ddl = module.table_ddl(module.sql_statements(text), "delivery_review_tasks")
        columns = {
            line.strip().split()[0]
            for line in ddl.splitlines()[1:]
            if line.strip()
            and not line.strip().startswith(("CONSTRAINT", "REFERENCES", "ON DELETE"))
        }
        return "status" in columns

    assert has_status_column(original) is False
    assert has_status_column(mutated) is True


def test_no_trigger_or_function_is_created():
    upper = statements().upper()
    assert "CREATE TRIGGER" not in upper
    assert "CREATE FUNCTION" not in upper
    assert "CREATE OR REPLACE FUNCTION" not in upper


def test_migration_has_a_matching_down_script():
    assert (ROOT / "migrations" / "036_delivery_acceptance_persistence_down.sql").is_file()


def test_measured_schema_counts_are_non_trivial():
    sql = statements()
    assert len(re.findall(r"REFERENCES ", sql)) >= 8
    assert len(re.findall(r"CONSTRAINT chk_", sql)) >= 20
    assert len(re.findall(r"CREATE UNIQUE INDEX", sql)) >= 5
    assert len(re.findall(r"CREATE INDEX", sql)) >= 10


# ---- Domain and repository boundaries -----------------------------------------------------------


def test_repository_exposes_the_required_operations():
    code = executable_python(REPOSITORY)
    for name in (
        "create_submission",
        "get_submission",
        "create_next_submission_version",
        "cas_update_submission_status",
        "create_review_task",
        "get_review_task",
        "get_active_review_task",
        "cas_update_review_task_assignment",
        "close_review_task",
        "list_review_tasks",
        "append_review_action",
        "list_review_actions",
        "append_decision",
        "list_decisions",
        "get_effective_decision",
        "create_follow_up_item",
        "list_follow_up_items",
    ):
        assert f"async def {name}" in code, f"missing repository operation: {name}"


def test_repository_never_opens_its_own_connection():
    """Every operation must compose inside the caller's transaction."""
    code = executable_python(REPOSITORY)
    assert "asyncpg.connect" not in code
    assert "create_pool" not in code


def test_repository_uses_db_authoritative_time_only():
    code = executable_python(REPOSITORY)
    assert "statement_timestamp()" in code
    for forbidden in ("datetime.now", "utcnow", "time.time"):
        assert forbidden not in code, f"BE1 must not use a client clock ({forbidden})"


def test_no_review_task_transition_semantics_are_implemented():
    code = executable_python(REPOSITORY)
    for forbidden in ("reopen", "close_on_accept", "close_on_expiry", "auto_close"):
        assert forbidden not in code.lower(), f"D05 defers transition semantics ({forbidden})"


def test_be1_implements_no_blocking_follow_up_rule():
    """§14: the ACCEPTED_WITH_FOLLOW_UP + blocking validation belongs to Step 66D-BE3.

    ACCEPTED_WITH_FOLLOW_UP itself IS canonical here -- it is one of the three Product Owner Final
    Decisions and must be storable. What must not exist is any constraint or code that couples it
    to the `blocking` flag.
    """
    sql = statements()
    code = executable_python(REPOSITORY)
    assert "ACCEPTED_WITH_FOLLOW_UP" in sql, "the canonical decision value must be storable"
    assert "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" not in sql + code
    # No CHECK constraint mentions `blocking` at all, so none can couple it to a decision type.
    for constraint in re.findall(r"CONSTRAINT chk_\w+ CHECK \(([^;]*?)\),", sql):
        assert "blocking" not in constraint, f"a CHECK constrains blocking: {constraint}"
    assert "blocking" not in code.lower().split("def create_follow_up_item")[0]


def test_model_declares_no_review_task_lifecycle():
    code = executable_python(MODEL)
    names = re.findall(r"^(\w+): frozenset", code, flags=re.MULTILINE)
    assert not [n for n in names if "REVIEW_TASK" in n.upper() or "TASK_STATUS" in n.upper()], names


# ---- Verifier ------------------------------------------------------------------------------------


def test_verifier_runs_and_passes():
    result = subprocess.run(
        ["python", str(VERIFIER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "STEP66D_BE1_PERSISTENCE_FOUNDATION_VERIFY: PASS" in result.stdout, result.stdout
    assert result.returncode == 0


def test_verifier_reports_a_measured_check_count():
    result = subprocess.run(
        ["python", str(VERIFIER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    match = re.search(r"checks=(\d+) failures=(\d+)", result.stdout)
    assert match, result.stdout
    assert int(match.group(1)) >= 80
    assert int(match.group(2)) == 0


# ---- Evidence -------------------------------------------------------------------------------------


def test_evidence_records_the_canonical_facts():
    text = EVIDENCE.read_text(encoding="utf-8")
    for needle in (
        "2d4da80",
        "66D-D05",
        "closed_at IS NULL",
        "uq_drt_active_per_submission",
        "036_delivery_acceptance_persistence.sql",
        "SHARED_MIGRATION_APPLIED",
        "CONCURRENCY_VALIDATION",
    ):
        assert needle in text, f"evidence does not record {needle!r}"


# Written as regexes with single-character classes so this test file does not itself contain the
# literals it forbids -- otherwise it would have to be excluded from its own scan.
LEAK_PATTERNS = (
    (r"\b10\.0\.1\.\d{1,3}\b", "internal IPv4 address"),
    (r"aiagent[-]swd", "SSH host alias"),
    (r"\bi[t]admin\b", "internal username"),
    (r"\bstp[a]dmin\b", "internal username"),
    (r"[C]:\\Users\\", "local absolute path"),
    (r"/hom[e]/\w", "local absolute path"),
    (r"post[g]res(?:ql)?://", "database DSN"),
    (r"pass[w]ord\s*[=:]", "credential"),
)


@pytest.mark.parametrize(
    "relpath",
    sorted(EXPECTED_PATHS),
)
def test_new_files_leak_no_internal_identifier_or_credential(relpath):
    """Every file this stage introduces is scanned, including this test and the verifier."""
    text = (ROOT / relpath).read_text(encoding="utf-8")
    for pattern, label in LEAK_PATTERNS:
        assert re.search(pattern, text) is None, f"{relpath} leaks a {label}"
