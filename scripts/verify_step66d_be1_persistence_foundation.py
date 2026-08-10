#!/usr/bin/env python3
"""Step 66D-BE1 -- delivery acceptance persistence foundation verifier.

Deterministic and read-only. Confirms that the five canonical acceptance entities are persisted,
that 66D-D05 is implemented EXACTLY (structural active state, no lifecycle enum, no submission
status mirroring, a partial unique index and no required-existence trigger), that CAS, idempotency,
append-only and supersession primitives exist, that the legacy DeliveryPackage family is untouched,
and that this stage created no API, frontend, event activation, read model, identity, TASK_ROLES,
deployment or infra change.

Positive scope is a fixed baseline plus an explicit path registry compared by SET EQUALITY -- never
a broad positive prefix. It is `BE1_BASELINE...HEAD` while the branch is open, which is safe only
because the registry bounds it exactly; the merge stage must freeze the endpoint to the stage head.

Starts no runtime, container, database, migration apply or external provider.

Marker: STEP66D_BE1_PERSISTENCE_FOUNDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "STEP66D_BE1_PERSISTENCE_FOUNDATION_VERIFY"

BE1_BASELINE = "2d4da808b1a89ea278fbb760e27f49047995165e"
BE1_BASELINE_SHORT = "2d4da80"
BE1_POSITIVE_RANGE = f"{BE1_BASELINE}...HEAD"

MIGRATION = "migrations/036_delivery_acceptance_persistence.sql"
MIGRATION_DOWN = "migrations/036_delivery_acceptance_persistence_down.sql"
PKG = "shared/sdk/delivery_acceptance"
PKG_INIT = f"{PKG}/__init__.py"
MODEL = f"{PKG}/acceptance_model.py"
REPOSITORY = f"{PKG}/acceptance_repository.py"
DOMAIN_TESTS = "tests/test_step66d_be1_delivery_acceptance_persistence.py"
SCOPE_TESTS = "tests/test_step66d_be1_persistence_foundation.py"
VERIFIER = "scripts/verify_step66d_be1_persistence_foundation.py"
EVIDENCE = "docs/handoffs/66d-delivery-acceptance/step66d-be1-persistence-foundation-evidence.md"

BE1_EXPECTED_PATHS = frozenset(
    {
        MIGRATION,
        MIGRATION_DOWN,
        PKG_INIT,
        MODEL,
        REPOSITORY,
        DOMAIN_TESTS,
        SCOPE_TESTS,
        VERIFIER,
        EVIDENCE,
    }
)

ACCEPTANCE_TABLES = (
    "delivery_submissions",
    "delivery_review_tasks",
    "delivery_review_actions",
    "product_owner_decisions",
    "acceptance_follow_up_items",
)

# Values 66D-D05 (D05-R8) forbids as a DeliveryReviewTask lifecycle.
FORBIDDEN_LIFECYCLE_VALUES = ("OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED", "PENDING", "ACTIVE")

# Paths BE1 must never touch. `migrations/` and `shared/` are deliberately absent: this stage owns
# a migration and an SDK package. The exact-set registry above is what bounds those two.
FORBIDDEN_SCOPE_PREFIXES = (
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

# Identifier-leak patterns, written as regexes with single-character classes so that this scanner
# does not itself contain the literals it forbids. A leak scanner whose own source trips the scan
# would have to be excluded from its own check, which is exactly how a real leak stays hidden.
LEAK_PATTERNS = (
    (r"\b10\.0\.1\.\d{1,3}\b", "internal IPv4 address"),
    (r"aiagent[-]swd", "SSH host alias"),
    (r"\bi[t]admin\b", "internal username"),
    (r"\bstp[a]dmin\b", "internal username"),
    (r"[C]:\\Users\\", "local absolute path"),
    (r"/hom[e]/\w", "local absolute path"),
    (r"post[g]res(?:ql)?://", "database DSN"),
)

# Files whose modification would breach an explicit BE1 boundary.
FORBIDDEN_EXACT_PATHS = (
    "source/progress.md",
    "shared/sdk/tasks/rbac.py",
    "migrations/021_delivery_package_acceptance_gate.sql",
    "scripts/run_platform_migrations.py",
)

failures: list[str] = []
checks_run = 0


def expect(ok: bool, label: str, message: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(f"{label}: {message}")
        print(f"  [FAIL] {label}: {message}")


def read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def sql_statements(text: str) -> str:
    """TEXT with every `--` comment removed.

    Every claim about what the migration DOES is checked against statements, never prose. A comment
    saying "no trigger is created" must never be able to satisfy a check for the absence of one.
    """
    lines = []
    for line in text.splitlines():
        code = line.split("--", 1)[0]
        if code.strip():
            lines.append(code)
    return "\n".join(lines)


def executable_python(relpath: str) -> str:
    """RELPATH's source with comments and docstrings removed, via an AST round-trip.

    Same reason as `sql_statements`: a docstring promising that no router is defined must not be
    able to vouch for a module that defines one.
    """
    source = read(relpath)
    if not source:
        return ""
    tree = ast.parse(source)
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


def table_ddl(statements: str, table: str) -> str:
    """The CREATE TABLE body for TABLE, from comment-stripped statements only."""
    marker = f"CREATE TABLE IF NOT EXISTS {table} ("
    if marker not in statements:
        return ""
    start = statements.index(marker)
    end = statements.find("\n);", start)
    return statements[start : end if end != -1 else len(statements)]


def main() -> int:
    migration_raw = read(MIGRATION)
    statements = sql_statements(migration_raw)
    model_code = executable_python(MODEL)
    repo_code = executable_python(REPOSITORY)

    # --- 1. baseline and exact positive scope -------------------------------------------------
    expect(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", BE1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0,
        "check01",
        f"the BE1 canonical baseline {BE1_BASELINE_SHORT} is not an ancestor of HEAD",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", BE1_POSITIVE_RANGE).splitlines()
        if line.strip()
    }
    expect(
        changed == BE1_EXPECTED_PATHS,
        "check02",
        "changed paths are not exactly the BE1 registry: "
        f"unexpected={sorted(changed - BE1_EXPECTED_PATHS)} "
        f"missing={sorted(BE1_EXPECTED_PATHS - changed)}",
    )
    expect(
        len(BE1_EXPECTED_PATHS) == 9,
        "check03",
        f"the BE1 path registry must hold exactly 9 paths, holds {len(BE1_EXPECTED_PATHS)}",
    )
    offenders = sorted(p for p in changed if p.startswith(FORBIDDEN_SCOPE_PREFIXES))
    expect(offenders == [], "check04", f"paths outside the BE1 boundary changed: {offenders}")
    breached = sorted(p for p in changed if p in FORBIDDEN_EXACT_PATHS)
    expect(breached == [], "check05", f"a protected file was modified: {breached}")
    expect(
        "source/progress.md" not in changed,
        "check06",
        "source/progress.md must remain unchanged (ADV-DRIFT-PROGRESS-01)",
    )

    # --- 2. the five canonical entities -------------------------------------------------------
    for index, table in enumerate(ACCEPTANCE_TABLES, start=7):
        expect(
            f"CREATE TABLE IF NOT EXISTS {table} (" in statements,
            f"check{index:02d}",
            f"migration 036 does not create {table}",
        )
    created = sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", statements))
    expect(
        created == sorted(ACCEPTANCE_TABLES),
        "check12",
        f"migration 036 creates tables outside the BE1 domain: {created}",
    )
    expect(
        sorted(re.findall(r"DROP TABLE IF EXISTS (\w+)", sql_statements(read(MIGRATION_DOWN))))
        == sorted(ACCEPTANCE_TABLES),
        "check13",
        "the down migration does not drop exactly the five new tables",
    )

    # --- 3. 66D-D05 implemented exactly -------------------------------------------------------
    review_task_ddl = table_ddl(statements, "delivery_review_tasks")
    expect(bool(review_task_ddl), "check14", "delivery_review_tasks DDL not found")
    expect(
        "closed_at" in review_task_ddl,
        "check15",
        "delivery_review_tasks has no closed_at column -- D05 active state is unimplementable",
    )
    review_task_columns = {
        line.strip().split()[0]
        for line in review_task_ddl.splitlines()[1:]
        if line.strip() and not line.strip().startswith(("CONSTRAINT", "REFERENCES", "ON DELETE"))
    }
    for forbidden in ("status", "review_status", "task_status", "lifecycle", "state"):
        expect(
            forbidden not in review_task_columns,
            f"check{16 + ('status', 'review_status', 'task_status', 'lifecycle', 'state').index(forbidden):02d}",
            f"delivery_review_tasks must not persist a {forbidden!r} column (D05-R2)",
        )
    expect(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission" in statements,
        "check21",
        "the D05 partial unique index uq_drt_active_per_submission is absent",
    )
    index_block = statements[statements.find("uq_drt_active_per_submission") :][:300]
    expect(
        "ON delivery_review_tasks (delivery_submission_id)" in index_block,
        "check22",
        "the D05 index is not keyed on delivery_submission_id alone",
    )
    expect(
        "WHERE closed_at IS NULL" in index_block,
        "check23",
        "the D05 index is not PARTIAL -- a plain UNIQUE would forbid closed tasks coexisting",
    )
    expect(
        "CREATE TRIGGER" not in statements.upper()
        and "CREATE FUNCTION" not in statements.upper()
        and "CREATE OR REPLACE FUNCTION" not in statements.upper(),
        "check24",
        "migration 036 creates a trigger or function -- required existence must stay DEFERRED",
    )
    expect(
        'REVIEW_TASK_ACTIVE_PREDICATE_SQL = "closed_at IS NULL"' in model_code
        or "REVIEW_TASK_ACTIVE_PREDICATE_SQL = 'closed_at IS NULL'" in model_code,
        "check25",
        "the domain model does not declare the canonical D05 active predicate",
    )
    expect(
        "def review_task_is_active" in model_code and "closed_at" in model_code,
        "check26",
        "the domain model has no structural active-state predicate",
    )

    # --- 4. no lifecycle enum, no status mirroring --------------------------------------------
    lifecycle_names = [
        name
        for name in re.findall(r"^(\w+)\s*:", model_code, flags=re.MULTILINE)
        if ("REVIEW_TASK" in name.upper() or "TASK_STATUS" in name.upper())
        and "PREDICATE" not in name.upper()
    ]
    expect(
        lifecycle_names == [],
        "check27",
        f"a DeliveryReviewTask lifecycle collection is defined: {lifecycle_names}",
    )
    for value in FORBIDDEN_LIFECYCLE_VALUES:
        expect(
            f"'{value}'" not in review_task_ddl and f'"{value}"' not in review_task_ddl,
            f"check{28 + FORBIDDEN_LIFECYCLE_VALUES.index(value):02d}",
            f"{value!r} appears in the delivery_review_tasks DDL as a lifecycle value (D05-R8)",
        )
    # D05-R3: the review task must never carry a copy of the submission's status. The submission
    # status vocabulary must appear nowhere in that table's DDL.
    mirrored = [
        status
        for status in (
            "DRAFT",
            "SUBMITTED",
            "UNDER_REVIEW",
            "CHANGES_REQUESTED",
            "QA_RERUN_REQUESTED",
            "ACCEPTED",
            "REJECTED",
            "ARCHIVED",
            "EXPIRED",
        )
        if status in review_task_ddl
    ]
    expect(
        mirrored == [],
        "check34",
        f"submission statuses are mirrored into delivery_review_tasks: {mirrored} (D05-R3)",
    )
    expect(
        "delivery_review_task_status" not in statements,
        "check35",
        "delivery_review_task_status must stay PLANNED / NOT IMPLEMENTED (D05-R9)",
    )
    expect(
        "delivery_review_task_status" not in model_code
        and "delivery_review_task_status" not in repo_code,
        "check36",
        "delivery_review_task_status must have no BE1 persistence source (D05-R9)",
    )

    # --- 5. CAS, idempotency, append-only, supersession ---------------------------------------
    for table in ("delivery_submissions", "delivery_review_tasks"):
        expect(
            "row_version" in table_ddl(statements, table),
            f"check{37 + ('delivery_submissions', 'delivery_review_tasks').index(table):02d}",
            f"{table} has no row_version CAS column",
        )
    expect(
        repo_code.count("row_version=row_version + 1") >= 3,
        "check39",
        "the repository does not advance row_version on its CAS mutations",
    )
    expect(
        "expected_row_version" in repo_code
        and "WHERE delivery_submission_id=$1 AND row_version=$3" in repo_code,
        "check40",
        "the repository has no guarded CAS update for DeliverySubmission",
    )
    expect(
        "AND row_version=$2 AND closed_at IS NULL" in repo_code,
        "check41",
        "close_review_task is not a guarded CAS primitive",
    )
    expect(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_dra_submission_idempotency_key" in statements,
        "check42",
        "the review-action idempotency uniqueness constraint is absent",
    )
    expect(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pod_submission_idempotency_key" in statements,
        "check43",
        "the decision idempotency uniqueness constraint is absent",
    )
    for table in ("delivery_review_actions", "product_owner_decisions"):
        ddl = table_ddl(statements, table)
        expect(
            "updated_at" not in ddl and "row_version" not in ddl,
            f"check{44 + ('delivery_review_actions', 'product_owner_decisions').index(table):02d}",
            f"{table} is append-only and must carry no updated_at / row_version",
        )
    mutating = [
        name
        for name in re.findall(r"^async def (\w+)", repo_code, flags=re.MULTILINE)
        if any(verb in name.lower() for verb in ("update", "delete", "remove", "overwrite"))
        and ("action" in name.lower() or "decision" in name.lower())
    ]
    expect(
        mutating == [],
        "check46",
        f"the repository exposes a mutating append-only operation: {mutating}",
    )
    expect(
        "supersedes_decision_id" in statements and "uq_pod_supersedes" in statements,
        "check47",
        "decision supersession linkage or its no-fork index is absent",
    )
    expect(
        "supersedes_submission_id" in statements and "uq_ds_supersedes" in statements,
        "check48",
        "submission supersession linkage or its no-fork index is absent",
    )
    expect(
        "cross-submission supersession is not permitted" in repo_code,
        "check49",
        "the repository does not reject cross-submission supersession",
    )

    # --- 6. legacy DeliveryPackage untouched ---------------------------------------------------
    legacy_names = (
        "delivery_packages",
        "delivery_package_sections",
        "delivery_package_artifacts",
        "human_acceptance_status",
        "acceptance_gate_runs",
        "operator_acceptance_reviews",
    )
    leaked = [name for name in legacy_names if name in statements]
    expect(
        leaked == [],
        "check50",
        f"migration 036 references the legacy DeliveryPackage family in a statement: {leaked}",
    )
    expect(
        all(name not in repo_code for name in legacy_names),
        "check51",
        "the BE1 repository reads or writes the legacy DeliveryPackage family",
    )
    expect(
        "legacy_delivery_package_refs" in statements,
        "check52",
        "the additive legacy reference field is absent (D04-R5)",
    )

    # --- 7. no API, frontend, event, read model, identity, deployment --------------------------
    for index, forbidden in enumerate(
        ("apirouter", "fastapi", "starlette", "outbox", "relay", "projector", "publish"),
        start=53,
    ):
        expect(
            forbidden not in (model_code + repo_code).lower(),
            f"check{index:02d}",
            f"BE1 code contains {forbidden!r} -- API/event activation is out of scope",
        )
    written = set(re.findall(r"(?:INSERT\s+INTO|UPDATE)\s+(\w+)", repo_code, flags=re.IGNORECASE))
    expect(
        bool(written) and written <= set(ACCEPTANCE_TABLES),
        "check60",
        f"the repository writes outside the five acceptance tables: {sorted(written)}",
    )
    expect(
        "TASK_ROLES" in model_code and "TASK_ROLES: frozenset" not in model_code,
        "check61",
        "BE1 must reference canonical TASK_ROLES, never redefine them",
    )
    expect(
        "shared/sdk/tasks/rbac.py" not in changed,
        "check62",
        "TASK_ROLES must remain UNCHANGED",
    )
    for index, marker in enumerate(
        ("authenticate", "verified_identity", "issue_token", "oidc"), start=63
    ):
        expect(
            marker not in (model_code + repo_code).lower(),
            f"check{index:02d}",
            f"BE1 must implement no identity ({marker!r} found)",
        )

    # --- 8. no shared migration apply, no deployment, no production ---------------------------
    expect(
        MIGRATION not in read("scripts/run_platform_migrations.py"),
        "check67",
        "migration 036 was wired into the operator migration chain -- shared apply is not "
        "authorized by this stage",
    )
    expect(
        "PLATFORM_MIGRATIONS_DATABASE_URL" not in (model_code + repo_code),
        "check68",
        "BE1 code reaches for the operator migration DSN",
    )
    expect(
        "production" not in statements.lower(),
        "check69",
        "migration 036 mentions production in a statement",
    )
    expect(
        "production_executed" not in (model_code + repo_code + statements),
        "check70",
        "BE1 introduces a production_executed surface",
    )

    # --- 9. evidence and tests ----------------------------------------------------------------
    evidence = read(EVIDENCE)
    expect(bool(evidence), "check71", "the BE1 evidence document is missing")
    for index, needle in enumerate(
        (
            BE1_BASELINE_SHORT,
            "66D-D05",
            "closed_at IS NULL",
            "uq_drt_active_per_submission",
            "036",
            "SHARED_MIGRATION_APPLIED",
        ),
        start=72,
    ):
        expect(
            needle in evidence,
            f"check{index:02d}",
            f"the evidence document does not record {needle!r}",
        )
    # Every file this stage introduces is scanned, not only the evidence document -- and this
    # verifier scans itself, which the single-character-class patterns above make possible.
    scanned = "\n".join(read(path) for path in sorted(BE1_EXPECTED_PATHS))
    for index, (pattern, label) in enumerate(LEAK_PATTERNS, start=78):
        expect(
            re.search(pattern, scanned) is None,
            f"check{index:02d}",
            f"a BE1 file leaks a {label}",
        )
    expect(bool(read(DOMAIN_TESTS)), "check85", "the BE1 domain test module is missing")
    expect(bool(read(SCOPE_TESTS)), "check86", "the BE1 scope test module is missing")
    expect(
        "requires_pg" in read(DOMAIN_TESTS),
        "check87",
        "the BE1 domain tests declare no real-PostgreSQL gate",
    )
    expect(
        "test_pg_concurrency_a_submission_cas_race_has_exactly_one_winner" in read(DOMAIN_TESTS)
        and "test_pg_concurrency_b_active_review_task_create_race_has_exactly_one_winner"
        in read(DOMAIN_TESTS),
        "check88",
        "the two mandatory PostgreSQL concurrency races are not both declared",
    )
    expect(
        "test_pg_d05_closed_and_active_review_tasks_coexist_but_a_second_active_is_refused"
        in read(DOMAIN_TESTS)
        and "test_pg_expired_submission_may_hold_an_active_review_task" in read(DOMAIN_TESTS),
        "check89",
        "the D05 coexistence and submission-independence tests are not both declared",
    )

    print(f"{MARKER}: checks={checks_run} failures={len(failures)}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
