"""Step 66D-BE1 -- delivery acceptance persistence, domain and concurrency tests.

Three layers:

  1. Domain model tests            pure Python, always run
  2. Schema contract tests         read migration 036's SQL text, always run
  3. Real-PostgreSQL integration   skipped unless an isolated ephemeral database is supplied,
                                   following the established Step 66C.4 convention
                                   (BE1_TEST_DATABASE_URL + STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS,
                                   guarded fail-closed by tests/step66c4_pg_safety.py)

Layer 3 is where 66D-D05 is actually proven: only a real PostgreSQL partial unique index can show
that a closed and an active review task coexist while a second active one is refused. There is no
mock substitute for that, and the mock-only path is deliberately not offered.
"""

from __future__ import annotations

import ast
import asyncio
import os
import re
import uuid
from pathlib import Path

import pytest

from shared.sdk.delivery_acceptance import acceptance_model as model
from shared.sdk.delivery_acceptance import acceptance_repository as repo
from shared.sdk.tasks.rbac import TASK_ROLES
from tests.step66c4_pg_safety import destructive_pg_refusal_reason

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
MIGRATION_036 = MIGRATIONS / "036_delivery_acceptance_persistence.sql"
MIGRATION_036_DOWN = MIGRATIONS / "036_delivery_acceptance_persistence_down.sql"

ACCEPTANCE_TABLES = (
    "delivery_submissions",
    "delivery_review_tasks",
    "delivery_review_actions",
    "product_owner_decisions",
    "acceptance_follow_up_items",
)


# =================================================================================================
# 1. Domain model
# =================================================================================================


def test_submission_statuses_are_exactly_the_canonical_nine():
    assert model.SUBMISSION_STATUSES == {
        "DRAFT",
        "SUBMITTED",
        "UNDER_REVIEW",
        "CHANGES_REQUESTED",
        "QA_RERUN_REQUESTED",
        "ACCEPTED",
        "REJECTED",
        "ARCHIVED",
        "EXPIRED",
    }
    assert len(model.SUBMISSION_STATUSES) == 9


def test_review_actions_and_po_decisions_are_disjoint_enums():
    assert model.REVIEW_ACTION_TYPES == {
        "ACCEPT",
        "REJECT",
        "REQUEST_CHANGES",
        "RERUN_QA",
        "ESCALATE",
        "ARCHIVE",
    }
    assert model.PO_DECISION_TYPES == {"ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"}
    # D01-R1..R3: two contracts, not two names for one thing. No shared value.
    assert not (model.REVIEW_ACTION_TYPES & model.PO_DECISION_TYPES)
    # D01-R8 / D01-R9 stated as assertions rather than prose.
    assert "ACCEPTED_WITH_FOLLOW_UP" not in model.REVIEW_ACTION_TYPES
    assert not ({"REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"} & model.PO_DECISION_TYPES)


def test_follow_up_lifecycle_belongs_to_follow_up_items_only():
    assert model.FOLLOW_UP_STATUSES == {"OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED"}


def test_no_review_task_lifecycle_enum_exists_in_the_domain_model():
    """66D-D05 / D05-R8: the review-task lifecycle enum is NOT DEFINED.

    Asserted structurally: no module-level name defines a review-task status/lifecycle set, and
    none of the forbidden values is reachable as a review-task value anywhere in the model.
    """
    names = [n for n in dir(model) if not n.startswith("_")]
    offenders = [
        n
        for n in names
        if ("REVIEW_TASK" in n.upper() or "TASK_STATUS" in n.upper())
        and isinstance(getattr(model, n), (frozenset, set, tuple, list))
    ]
    assert offenders == [], f"review-task lifecycle collection defined: {offenders}"
    assert not hasattr(model, "REVIEW_TASK_STATUSES")
    assert not hasattr(model, "REVIEW_TASK_LIFECYCLE")
    assert not hasattr(model, "DELIVERY_REVIEW_TASK_STATUS")


def test_d05_active_predicate_reads_closed_at_and_nothing_else():
    assert model.review_task_is_active({"closed_at": None}) is True
    assert model.review_task_is_closed({"closed_at": None}) is False

    closed = {"closed_at": "2026-08-10T00:00:00Z"}
    assert model.review_task_is_active(closed) is False
    assert model.review_task_is_closed(closed) is True

    # D05-R3: the submission status must not influence the review task's structural state.
    for status in sorted(model.SUBMISSION_STATUSES):
        assert model.review_task_is_active({"closed_at": None, "status": status}) is True
        assert model.review_task_is_active({"closed_at": "t", "status": status}) is False


def test_d05_predicate_sql_is_the_canonical_text():
    assert model.REVIEW_TASK_ACTIVE_PREDICATE_SQL == "closed_at IS NULL"
    assert model.REVIEW_TASK_CLOSED_PREDICATE_SQL == "closed_at IS NOT NULL"


def test_assignable_roles_are_exactly_task_roles_unchanged():
    assert model.ASSIGNABLE_ROLES == TASK_ROLES
    assert model.assert_assigned_roles(["reviewer_approver", "pm_engineering_lead"])
    with pytest.raises(ValueError):
        model.assert_assigned_roles(["product_owner_supreme"])


def test_invalid_vocabulary_values_are_rejected():
    with pytest.raises(ValueError):
        model.assert_submission_status("APPROVED")
    with pytest.raises(ValueError):
        model.assert_review_action_type("ACCEPTED_WITH_FOLLOW_UP")
    with pytest.raises(ValueError):
        model.assert_po_decision_type("REQUEST_CHANGES")
    with pytest.raises(ValueError):
        model.assert_follow_up_status("PENDING")


def test_effective_decision_is_the_unsuperseded_highest_version():
    a = {
        "decision_id": "a",
        "decision_version": 1,
        "supersedes_decision_id": None,
        "decision_type": "REJECTED",
    }
    b = {
        "decision_id": "b",
        "decision_version": 2,
        "supersedes_decision_id": "a",
        "decision_type": "ACCEPTED",
    }
    c = {
        "decision_id": "c",
        "decision_version": 3,
        "supersedes_decision_id": "b",
        "decision_type": "ACCEPTED_WITH_FOLLOW_UP",
    }

    assert model.effective_decision([]) is None
    assert model.effective_decision([a])["decision_id"] == "a"
    assert model.effective_decision([a, b])["decision_id"] == "b"
    assert model.effective_decision([a, b, c])["decision_id"] == "c"
    # History order must not change the answer, and superseded rows stay in the list.
    assert model.effective_decision([c, a, b])["decision_id"] == "c"


def test_projection_never_invents_acceptance():
    assert model.projected_submission_status(None) is None
    assert model.projected_submission_status({"decision_type": "ACCEPTED"}) == "ACCEPTED"
    assert (
        model.projected_submission_status({"decision_type": "ACCEPTED_WITH_FOLLOW_UP"})
        == "ACCEPTED"
    )
    assert model.projected_submission_status({"decision_type": "REJECTED"}) == "REJECTED"


# =================================================================================================
# 2. Schema contract (migration text)
# =================================================================================================


def _sql() -> str:
    return MIGRATION_036.read_text(encoding="utf-8")


def _sql_statements() -> str:
    """Migration 036 with every `--` comment removed.

    Scans of what the migration DOES must read statements, never prose: a comment explaining that
    the migration performs no UPDATE would otherwise satisfy a naive substring search for UPDATE.
    """
    lines = []
    for line in _sql().splitlines():
        code = line.split("--", 1)[0]
        if code.strip():
            lines.append(code)
    return "\n".join(lines)


def _executable_python(path: Path) -> str:
    """PATH's source with comments and docstrings removed, via a round-trip through the AST.

    Same reason as `_sql_statements`: a docstring saying "no outbox row is written" must not be
    able to vouch for a module that writes one.
    """
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


def test_migration_036_creates_exactly_the_five_acceptance_tables():
    sql = _sql()
    for table in ACCEPTANCE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in sql
    created = sorted(
        line.split("CREATE TABLE IF NOT EXISTS ")[1].split(" ")[0]
        for line in sql.splitlines()
        if line.startswith("CREATE TABLE IF NOT EXISTS ")
    )
    assert created == sorted(ACCEPTANCE_TABLES)


def test_migration_036_is_strictly_additive():
    """No ALTER, DROP, UPDATE, DELETE or INSERT: the up-migration only creates."""
    sql = _sql_statements().upper()
    for forbidden in (
        "ALTER TABLE",
        "DROP TABLE",
        "DROP COLUMN",
        "UPDATE ",
        "DELETE FROM",
        "INSERT INTO",
        "TRUNCATE",
    ):
        assert forbidden not in sql, f"migration 036 is not additive: contains {forbidden!r}"


def test_migration_036_creates_no_trigger_or_function():
    """D05 forbids a trigger forcing an active task to exist; §14 forbids implementing the BE3
    blocking-follow-up rule early. The simplest structural proof is that 036 creates neither."""
    sql = _sql_statements().upper()
    assert "CREATE TRIGGER" not in sql
    assert "CREATE OR REPLACE FUNCTION" not in sql
    assert "CREATE FUNCTION" not in sql


def test_migration_036_declares_the_d05_partial_unique_index():
    sql = _sql()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission" in sql
    assert "ON delivery_review_tasks (delivery_submission_id)" in sql
    assert "WHERE closed_at IS NULL" in sql


def test_review_task_table_declares_no_status_or_lifecycle_column():
    """66D-D05 / D05-R2 and D05-R3, asserted against the DDL of that one table."""
    sql = _sql()
    start = sql.index("CREATE TABLE IF NOT EXISTS delivery_review_tasks (")
    end = sql.index("CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission")
    ddl = sql[start:end]
    body = ddl[: ddl.index("\n);")]
    columns = [
        line.strip().split()[0]
        for line in body.splitlines()[1:]
        if line.strip()
        and not line.strip().startswith(("--", "CONSTRAINT", ")", "'"))
        and not line.strip().startswith(("REFERENCES", "ON DELETE"))
    ]
    for forbidden in ("status", "review_status", "task_status", "lifecycle", "state"):
        assert forbidden not in columns, f"delivery_review_tasks must not have a {forbidden} column"
    assert "closed_at" in columns
    assert "delivery_submission_id" in columns


def test_migration_036_does_not_touch_the_legacy_delivery_package_family():
    """66D-D04 / D04-R1..R4: the legacy Step 47/49 object is preserved unchanged."""
    statements = _sql_statements()
    legacy = (
        "delivery_packages",
        "delivery_package_sections",
        "delivery_package_artifacts",
        "human_acceptance_status",
        "acceptance_gate_runs",
        "operator_acceptance_reviews",
    )
    for name in legacy:
        # A legacy table may be NAMED in a comment; it must never appear in a statement.
        assert name not in statements, f"migration 036 references legacy {name} in a statement"


def test_task_roles_allowlist_in_migration_matches_rbac_exactly():
    """The CHECK on assigned_roles references TASK_ROLES; it must not drift from rbac.py."""
    sql = _sql()
    start = sql.index("CONSTRAINT chk_drt_assigned_roles")
    fragment = sql[start : sql.index("]::text[]", start)]
    declared = {part.strip().strip("',") for part in fragment.split("'") if part.strip(" ,\n[]")}
    declared = {d for d in declared if d and d.replace("_", "").isalpha()}
    assert declared == set(TASK_ROLES)


def test_down_migration_drops_only_the_five_new_tables():
    down = MIGRATION_036_DOWN.read_text(encoding="utf-8")
    dropped = sorted(
        line.split("DROP TABLE IF EXISTS ")[1].split(" ")[0]
        for line in down.splitlines()
        if line.startswith("DROP TABLE IF EXISTS ")
    )
    assert dropped == sorted(ACCEPTANCE_TABLES)


def test_append_only_tables_expose_no_repository_mutation():
    """§24: the acceptance-domain repository exposes no update or delete for the two append-only
    entities. Checked against the module's public surface, not against prose."""
    public = [n for n in dir(repo) if not n.startswith("_")]
    for name in public:
        lowered = name.lower()
        if not any(verb in lowered for verb in ("update", "delete", "remove", "overwrite")):
            continue
        assert "action" not in lowered, f"repository exposes a mutating action op: {name}"
        assert "decision" not in lowered, f"repository exposes a mutating decision op: {name}"


def test_be1_modules_contain_no_api_router_event_or_outbox_code():
    """§29 and §36, checked against executable code with comments and docstrings stripped."""
    package = ROOT / "shared" / "sdk" / "delivery_acceptance"
    for path in sorted(package.glob("*.py")):
        code = _executable_python(path).lower()
        for forbidden in (
            "apirouter",
            "fastapi",
            "starlette",
            "outbox",
            "relay",
            "projector",
            "publish",
            "emit_event",
        ):
            assert forbidden not in code, f"{path.name} must contain no {forbidden!r} code"


def test_be1_sql_writes_only_acceptance_tables():
    """Every INSERT/UPDATE the repository issues must target one of the five new tables."""
    code = _executable_python(
        ROOT / "shared" / "sdk" / "delivery_acceptance" / "acceptance_repository.py"
    )
    written = re.findall(r"(?:INSERT\s+INTO|UPDATE)\s+(\w+)", code, flags=re.IGNORECASE)
    assert written, "no write statement found -- the scan would be vacuous"
    assert set(written) <= set(ACCEPTANCE_TABLES), f"writes outside the BE1 scope: {set(written)}"


# =================================================================================================
# 3. Real-PostgreSQL integration
# =================================================================================================

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REFUSAL = destructive_pg_refusal_reason()


def _pg_ok() -> bool:
    if _REFUSAL is not None or not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            c = await asyncpg.connect(dsn=_DSN, timeout=5)
            await c.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_ok(), reason=(_REFUSAL or "isolated ephemeral PostgreSQL 16 not reachable")
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _reset_and_migrate(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS acceptance_follow_up_items, product_owner_decisions, "
        "delivery_review_actions, delivery_review_tasks, delivery_submissions CASCADE;"
    )
    await conn.execute("DROP TABLE IF EXISTS operator_tasks CASCADE;")
    await conn.execute(
        "DROP TABLE IF EXISTS project_graph_snapshots, project_artifacts, project_risks, "
        "project_acceptance_criteria, project_work_item_dependencies, project_work_items, "
        "project_milestones, project_user_stories, project_briefs, projects CASCADE;"
    )
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in (
        "017_project_planner_task_graph.sql",
        "029_operator_task_api_foundation.sql",
        "036_delivery_acceptance_persistence.sql",
    ):
        await _apply(conn, name)


async def _lineage(conn) -> tuple[str, str, str]:
    """Create the execution-lineage and task-anchor parents a submission needs."""
    project_id = await conn.fetchval(
        "INSERT INTO projects (title) VALUES ('be1 fixture project') RETURNING id"
    )
    work_item_id = await conn.fetchval(
        "INSERT INTO project_work_items (project_id, title) VALUES ($1, 'be1 fixture item') "
        "RETURNING id",
        project_id,
    )
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by) "
        "VALUES ('be1 fixture task', 'software_delivery', 'fixture') RETURNING id",
    )
    return str(project_id), str(work_item_id), str(task_id)


async def _submission(conn, project_id: str, work_item_id: str, **kw) -> dict:
    return await repo.create_submission(
        conn,
        project_id=project_id,
        primary_work_item_id=work_item_id,
        created_by_actor="fixture-actor",
        **kw,
    )


@requires_pg
def test_pg_migration_applies_cleanly_and_is_reversible():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            for table in ACCEPTANCE_TABLES:
                assert await conn.fetchval(f"SELECT to_regclass('{table}') IS NOT NULL")

            # The D05 index exists, is UNIQUE and is PARTIAL.
            index_def = await conn.fetchval(
                "SELECT indexdef FROM pg_indexes WHERE indexname='uq_drt_active_per_submission'"
            )
            assert "UNIQUE" in index_def
            assert "WHERE (closed_at IS NULL)" in index_def

            # Down reverses it, and re-applying is idempotent.
            await _apply(conn, "036_delivery_acceptance_persistence_down.sql")
            for table in ACCEPTANCE_TABLES:
                assert await conn.fetchval(f"SELECT to_regclass('{table}') IS NULL")
            await _apply(conn, "036_delivery_acceptance_persistence.sql")
            await _apply(conn, "036_delivery_acceptance_persistence.sql")
            for table in ACCEPTANCE_TABLES:
                assert await conn.fetchval(f"SELECT to_regclass('{table}') IS NOT NULL")

            # Legacy compatibility: 036 created no legacy table and altered none.
            assert await conn.fetchval("SELECT to_regclass('delivery_packages') IS NULL")
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_review_task_table_has_no_lifecycle_column_in_the_live_schema():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            columns = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='delivery_review_tasks'"
                )
            }
            assert "closed_at" in columns
            for forbidden in ("status", "review_status", "task_status", "lifecycle", "state"):
                assert forbidden not in columns
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_submission_status_vocabulary_matches_the_domain_model():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            for status in sorted(model.SUBMISSION_STATUSES):
                row = await _submission(conn, project_id, work_item_id, status=status)
                assert row["status"] == status
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO delivery_submissions "
                    "(project_id, primary_work_item_id, created_by_actor, status) "
                    "VALUES ($1,$2,'a','APPROVED')",
                    project_id,
                    work_item_id,
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_submission_version_chain_is_linear_and_monotonic():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            v1 = await _submission(conn, project_id, work_item_id)
            assert v1["submission_version"] == 1
            assert v1["supersedes_submission_id"] is None

            v2 = await repo.create_next_submission_version(
                conn,
                supersedes_submission_id=str(v1["delivery_submission_id"]),
                created_by_actor="fixture-actor",
            )
            assert v2["submission_version"] == 2
            assert str(v2["supersedes_submission_id"]) == str(v1["delivery_submission_id"])
            # Lineage is inherited, never silently moved.
            assert str(v2["project_id"]) == project_id
            assert str(v2["primary_work_item_id"]) == work_item_id

            # Duplicate version: a second successor for the same predecessor is refused by the DB.
            with pytest.raises(asyncpg.UniqueViolationError):
                await repo.create_next_submission_version(
                    conn,
                    supersedes_submission_id=str(v1["delivery_submission_id"]),
                    created_by_actor="fixture-actor",
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_submission_version_two_without_a_predecessor_is_refused():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO delivery_submissions "
                    "(project_id, primary_work_item_id, created_by_actor, submission_version) "
                    "VALUES ($1,$2,'a',2)",
                    project_id,
                    work_item_id,
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_d05_closed_and_active_review_tasks_coexist_but_a_second_active_is_refused():
    """Step 66D-BE1 §21 -- the test that proves the index is PARTIAL, not a plain UNIQUE."""

    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            submission = await _submission(conn, project_id, work_item_id)
            sid = str(submission["delivery_submission_id"])

            task_a = await repo.create_review_task(
                conn, delivery_submission_id=sid, task_id=task_id
            )
            assert model.review_task_is_active(task_a)

            closed_a = await repo.close_review_task(
                conn,
                str(task_a["delivery_review_task_id"]),
                expected_row_version=int(task_a["row_version"]),
            )
            assert closed_a is not None and model.review_task_is_closed(closed_a)

            # Task B: active, same submission, while a CLOSED task already exists -> ALLOWED.
            task_b = await repo.create_review_task(
                conn, delivery_submission_id=sid, task_id=task_id
            )
            assert model.review_task_is_active(task_b)
            assert len(await repo.list_review_tasks(conn, sid)) == 2

            # Task C: a SECOND active task for the same submission -> REFUSED by the DB.
            with pytest.raises(asyncpg.UniqueViolationError):
                await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_expired_submission_may_hold_an_active_review_task():
    """Step 66D-BE1 §22 -- submission state and review-task structural state are independent."""

    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            submission = await _submission(conn, project_id, work_item_id, status="EXPIRED")
            sid = str(submission["delivery_submission_id"])

            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            assert model.review_task_is_active(task)

            reread = await repo.get_submission(conn, sid)
            assert reread["status"] == "EXPIRED"
            active = await repo.get_active_review_task(conn, sid)
            assert active is not None

            # And the reverse pairing, which DESIGN section 3 explicitly requires to be
            # expressible: a CLOSED review task against an EXPIRED submission.
            closed = await repo.close_review_task(
                conn,
                str(task["delivery_review_task_id"]),
                expected_row_version=int(task["row_version"]),
            )
            assert model.review_task_is_closed(closed)
            assert (await repo.get_submission(conn, sid))["status"] == "EXPIRED"
            assert await repo.get_active_review_task(conn, sid) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_zero_active_review_tasks_is_a_legal_state():
    """66D-D05 / D05-R6: required existence is DEFERRED. Nothing forces a task to exist."""

    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            submission = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(submission["delivery_submission_id"])
            assert await repo.get_active_review_task(conn, sid) is None
            assert await repo.list_review_tasks(conn, sid) == []
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_review_action_append_only_and_idempotent():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            submission = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(submission["delivery_submission_id"])
            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            rtid = str(task["delivery_review_task_id"])

            key = f"escalate:{uuid.uuid4()}"
            action = await repo.append_review_action(
                conn,
                delivery_submission_id=sid,
                delivery_review_task_id=rtid,
                action_type="ESCALATE",
                actor_ref="reviewer-1",
                reason="needs a different decider",
                idempotency_key=key,
            )
            assert action["action_type"] == "ESCALATE"

            # Durable duplicate prevention on (submission, idempotency_key).
            with pytest.raises(asyncpg.UniqueViolationError):
                await repo.append_review_action(
                    conn,
                    delivery_submission_id=sid,
                    delivery_review_task_id=rtid,
                    action_type="ESCALATE",
                    actor_ref="reviewer-1",
                    reason="needs a different decider",
                    idempotency_key=key,
                )

            # The table is structurally append-only: no updated_at, no row_version to advance.
            columns = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='delivery_review_actions'"
                )
            }
            assert "updated_at" not in columns
            assert "row_version" not in columns

            assert len(await repo.list_review_actions(conn, sid)) == 1
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_review_action_vocabulary_and_required_evidence():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            submission = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(submission["delivery_submission_id"])
            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            rtid = str(task["delivery_review_task_id"])

            # A Product Owner decision value is not a Review Gate Action (D01-R9).
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO delivery_review_actions (delivery_submission_id, "
                    "delivery_review_task_id, action_type, actor_ref, idempotency_key) "
                    "VALUES ($1,$2,'ACCEPTED_WITH_FOLLOW_UP','a',$3)",
                    sid,
                    rtid,
                    str(uuid.uuid4()),
                )
            # REQUEST_CHANGES without a reason is refused.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO delivery_review_actions (delivery_submission_id, "
                    "delivery_review_task_id, action_type, actor_ref, idempotency_key) "
                    "VALUES ($1,$2,'REQUEST_CHANGES','a',$3)",
                    sid,
                    rtid,
                    str(uuid.uuid4()),
                )
            # RERUN_QA without a scope and a previous QA reference is refused.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO delivery_review_actions (delivery_submission_id, "
                    "delivery_review_task_id, action_type, actor_ref, reason, idempotency_key) "
                    "VALUES ($1,$2,'RERUN_QA','a','because',$3)",
                    sid,
                    rtid,
                    str(uuid.uuid4()),
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_decision_supersession_history_and_integrity():
    """Step 66D-BE1 §12 -- A, B supersedes A, C supersedes B: history = A,B,C; effective = C."""

    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])
            other = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            other_sid = str(other["delivery_submission_id"])
            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            rtid = str(task["delivery_review_task_id"])

            async def decide(dtype, supersedes=None):
                return await repo.append_decision(
                    conn,
                    delivery_submission_id=sid,
                    delivery_review_task_id=rtid,
                    decision_type=dtype,
                    decision_reason="fixture reason",
                    decided_by_actor="po-1",
                    idempotency_key=str(uuid.uuid4()),
                    supersedes_decision_id=supersedes,
                )

            a = await decide("REJECTED")
            b = await decide("ACCEPTED", str(a["decision_id"]))
            c = await decide("ACCEPTED_WITH_FOLLOW_UP", str(b["decision_id"]))
            assert [a["decision_version"], b["decision_version"], c["decision_version"]] == [
                1,
                2,
                3,
            ]

            history = await repo.list_decisions(conn, sid)
            assert [str(d["decision_id"]) for d in history] == [
                str(a["decision_id"]),
                str(b["decision_id"]),
                str(c["decision_id"]),
            ]
            effective = await repo.get_effective_decision(conn, sid)
            assert str(effective["decision_id"]) == str(c["decision_id"])
            # Superseded decisions remain permanently queryable.
            assert all(
                await conn.fetchval(
                    "SELECT count(*) FROM product_owner_decisions WHERE decision_id=$1", d
                )
                == 1
                for d in (a["decision_id"], b["decision_id"])
            )

            # Forked history: a second successor for the same predecessor is refused.
            with pytest.raises(asyncpg.UniqueViolationError):
                await decide("REJECTED", str(b["decision_id"]))

            # Cross-submission supersession is refused by the repository, before any write.
            with pytest.raises(ValueError, match="cross-submission"):
                await repo.append_decision(
                    conn,
                    delivery_submission_id=other_sid,
                    decision_type="ACCEPTED",
                    decision_reason="fixture reason",
                    decided_by_actor="po-1",
                    idempotency_key=str(uuid.uuid4()),
                    supersedes_decision_id=str(c["decision_id"]),
                )
            assert await repo.get_effective_decision(conn, other_sid) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_decision_self_supersession_and_cycles_are_impossible():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])
            did = str(uuid.uuid4())

            # Self-supersession is refused by a DB CHECK, not by application code.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO product_owner_decisions (decision_id, delivery_submission_id, "
                    "decision_type, decision_reason, decided_by_actor, supersedes_decision_id, "
                    "decision_version, idempotency_key) "
                    "VALUES ($1,$2,'ACCEPTED','r','po',$1,2,$3)",
                    did,
                    sid,
                    str(uuid.uuid4()),
                )

            # A cycle needs a row that both is and is not the chain root: refused structurally.
            a = await repo.append_decision(
                conn,
                delivery_submission_id=sid,
                decision_type="ACCEPTED",
                decision_reason="r",
                decided_by_actor="po",
                idempotency_key=str(uuid.uuid4()),
            )
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE product_owner_decisions SET supersedes_decision_id=$1 "
                    "WHERE decision_id=$1",
                    a["decision_id"],
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_decision_type_vocabulary_and_duplicate_idempotency_key():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])

            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO product_owner_decisions (delivery_submission_id, decision_type, "
                    "decision_reason, decided_by_actor, idempotency_key) "
                    "VALUES ($1,'REQUEST_CHANGES','r','po',$2)",
                    sid,
                    str(uuid.uuid4()),
                )

            key = str(uuid.uuid4())
            await repo.append_decision(
                conn,
                delivery_submission_id=sid,
                decision_type="ACCEPTED",
                decision_reason="r",
                decided_by_actor="po",
                idempotency_key=key,
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await repo.append_decision(
                    conn,
                    delivery_submission_id=sid,
                    decision_type="REJECTED",
                    decision_reason="r",
                    decided_by_actor="po",
                    idempotency_key=key,
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_follow_up_items_carry_their_own_lifecycle_and_no_be3_rule():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, _ = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])
            decision = await repo.append_decision(
                conn,
                delivery_submission_id=sid,
                decision_type="ACCEPTED_WITH_FOLLOW_UP",
                decision_reason="r",
                decided_by_actor="po",
                idempotency_key=str(uuid.uuid4()),
            )
            did = str(decision["decision_id"])

            for status in sorted(model.FOLLOW_UP_STATUSES):
                item = await repo.create_follow_up_item(
                    conn,
                    decision_id=did,
                    description="tidy the docs",
                    owner_actor_ref="dev-1",
                    severity="low",
                    status=status,
                )
                assert item["status"] == status

            # §14: BE1 stores `blocking` and enforces NOTHING about it. A blocking follow-up under
            # ACCEPTED_WITH_FOLLOW_UP is persistable here; refusing it is BE3 action policy.
            blocking = await repo.create_follow_up_item(
                conn,
                decision_id=did,
                description="unfinished migration",
                owner_actor_ref="dev-1",
                severity="high",
                blocking=True,
            )
            assert blocking["blocking"] is True

            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO acceptance_follow_up_items (decision_id, description, "
                    "owner_actor_ref, severity, status) VALUES ($1,'d','o','low','PENDING')",
                    did,
                )
            assert len(await repo.list_follow_up_items(conn, did)) == 5
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_referential_integrity_has_no_silent_cascade_loss():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])
            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            rtid = str(task["delivery_review_task_id"])
            decision = await repo.append_decision(
                conn,
                delivery_submission_id=sid,
                delivery_review_task_id=rtid,
                decision_type="ACCEPTED",
                decision_reason="r",
                decided_by_actor="po",
                idempotency_key=str(uuid.uuid4()),
            )
            await repo.create_follow_up_item(
                conn,
                decision_id=str(decision["decision_id"]),
                description="d",
                owner_actor_ref="o",
                severity="low",
            )

            # Unknown parents are refused.
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await repo.create_review_task(
                    conn, delivery_submission_id=str(uuid.uuid4()), task_id=task_id
                )
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await repo.create_submission(
                    conn,
                    project_id=str(uuid.uuid4()),
                    primary_work_item_id=work_item_id,
                    created_by_actor="a",
                )

            # RESTRICT, not CASCADE: acceptance history is never silently lost.
            for statement, args in (
                ("DELETE FROM delivery_submissions WHERE delivery_submission_id=$1", (sid,)),
                ("DELETE FROM delivery_review_tasks WHERE delivery_review_task_id=$1", (rtid,)),
                (
                    "DELETE FROM product_owner_decisions WHERE decision_id=$1",
                    (decision["decision_id"],),
                ),
                ("DELETE FROM projects WHERE id=$1", (project_id,)),
            ):
                with pytest.raises(asyncpg.ForeignKeyViolationError):
                    await conn.execute(statement, *args)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_stale_cas_is_rejected_on_both_cas_entities():
    async def scenario():
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            project_id, work_item_id, task_id = await _lineage(conn)
            s1 = await _submission(conn, project_id, work_item_id)
            sid = str(s1["delivery_submission_id"])

            ok = await repo.cas_update_submission_status(
                conn, sid, status="SUBMITTED", expected_row_version=1
            )
            assert ok is not None and ok["row_version"] == 2
            stale = await repo.cas_update_submission_status(
                conn, sid, status="UNDER_REVIEW", expected_row_version=1
            )
            assert stale is None
            assert (await repo.get_submission(conn, sid))["status"] == "SUBMITTED"

            task = await repo.create_review_task(conn, delivery_submission_id=sid, task_id=task_id)
            rtid = str(task["delivery_review_task_id"])
            assert (
                await repo.cas_update_review_task_assignment(
                    conn, rtid, expected_row_version=1, assigned_roles=["reviewer_approver"]
                )
            )["row_version"] == 2
            assert (
                await repo.cas_update_review_task_assignment(
                    conn, rtid, expected_row_version=1, assigned_roles=["platform_admin"]
                )
                is None
            )
            # A stale close is refused, and closing twice is refused.
            assert await repo.close_review_task(conn, rtid, expected_row_version=1) is None
            assert await repo.close_review_task(conn, rtid, expected_row_version=2) is not None
            assert await repo.close_review_task(conn, rtid, expected_row_version=3) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrency_a_submission_cas_race_has_exactly_one_winner():
    """Step 66D-BE1 §20 Test A -- two transactions, same row, same expected version."""

    async def scenario():
        c1 = await asyncpg.connect(dsn=_DSN)
        c2 = await asyncpg.connect(dsn=_DSN)
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            project_id, work_item_id, _ = await _lineage(setup)
            s1 = await _submission(setup, project_id, work_item_id)
            sid = str(s1["delivery_submission_id"])
            assert s1["row_version"] == 1

            t1 = c1.transaction()
            t2 = c2.transaction()
            await t1.start()
            await t2.start()

            r1 = await repo.cas_update_submission_status(
                c1, sid, status="SUBMITTED", expected_row_version=1
            )
            # c2 races for the same row with the same expected version; it blocks on the row lock
            # until c1 commits, then re-evaluates its guard against the committed row.
            pending = asyncio.create_task(
                repo.cas_update_submission_status(
                    c2, sid, status="UNDER_REVIEW", expected_row_version=1
                )
            )
            await asyncio.sleep(0.3)
            assert not pending.done(), "the second transaction did not contend for the row"
            await t1.commit()
            r2 = await pending
            await t2.commit()

            winners = [r for r in (r1, r2) if r is not None]
            losers = [r for r in (r1, r2) if r is None]
            assert len(winners) == 1, "exactly one CAS must succeed"
            assert len(losers) == 1, "exactly one CAS must report a conflict"

            final = await repo.get_submission(setup, sid)
            assert final["row_version"] == 2, "the version must increment exactly once"
            assert final["status"] == "SUBMITTED"
        finally:
            await c1.close()
            await c2.close()
            await setup.close()

    _run(scenario())


@requires_pg
def test_pg_concurrency_b_active_review_task_create_race_has_exactly_one_winner():
    """Step 66D-BE1 §20 Test B -- the direct runtime proof of 66D-D05 / D05-R4.

    Two transactions create an active review task for the same submission at the same time. The
    authoritative PostgreSQL partial unique index, not application code, decides.
    """

    async def scenario():
        c1 = await asyncpg.connect(dsn=_DSN)
        c2 = await asyncpg.connect(dsn=_DSN)
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            project_id, work_item_id, task_id = await _lineage(setup)
            s1 = await _submission(setup, project_id, work_item_id, status="UNDER_REVIEW")
            sid = str(s1["delivery_submission_id"])

            t1 = c1.transaction()
            t2 = c2.transaction()
            await t1.start()
            await t2.start()

            first = await repo.create_review_task(c1, delivery_submission_id=sid, task_id=task_id)
            assert first["closed_at"] is None

            pending = asyncio.create_task(
                repo.create_review_task(c2, delivery_submission_id=sid, task_id=task_id)
            )
            await asyncio.sleep(0.3)
            assert not pending.done(), "the second insert did not contend on the unique index"
            await t1.commit()

            with pytest.raises(asyncpg.UniqueViolationError):
                await pending
            await t2.rollback()

            rows = await repo.list_review_tasks(setup, sid)
            assert len(rows) == 1, "exactly one active review task must survive the race"
            assert model.review_task_is_active(rows[0])
        finally:
            await c1.close()
            await c2.close()
            await setup.close()

    _run(scenario())
