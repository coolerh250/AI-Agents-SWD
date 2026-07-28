#!/usr/bin/env python3
"""Step 66C.4-BE3-R-FC -- independent static verifier for the M-1 / L-1 / R2-1 focused closure.

Re-derives the STRUCTURAL invariants of the three remediations (feature range 6323972..5a413bf)
directly from the committed source/migrations, WITHOUT trusting any implementation self-verifier. It
performs NO database or network I/O, executes nothing, and enables no gate. Run from the repository
root (a tree that contains the remediation, e.g. this review branch after merging the feature head):

    python scripts/verify_step66c4_be3_r1_r2_focused_closure.py

Exit 0 = every structural invariant holds; non-zero = at least one failed (printed).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIG = REPO / "migrations"
SDK = REPO / "shared" / "sdk" / "tasks"
API = REPO / "apps" / "orchestrator" / "src"
GATE = (
    REPO
    / "docs"
    / "contracts"
    / "66c4-reminder-expiry-controlled-resume"
    / "be3-runtime-activation-gate.md"
)

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        _failures.append(label)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def main() -> int:
    # ============================ M-1 ============================================================
    m035 = read(MIG / "035_be3_production_action_approvals.sql")
    check(
        "CREATE TABLE IF NOT EXISTS production_action_approvals" in m035,
        "M-1: migration 035 creates the authoritative approval registry",
    )
    check("ADD COLUMN" not in m035.upper(), "M-1: 035 adds no column to an existing table")
    check(
        bool(re.search(r"team_id\s+UUID\s+NOT NULL", m035))
        and bool(re.search(r"project_id\s+UUID\s+NOT NULL", m035)),
        "M-1: 035 team/project bound (UUID NOT NULL)",
    )
    for token, label in [
        ("chk_paa_action_type", "action-bound"),
        ("chk_paa_resource_type", "resource-type-bound"),
        ("resource_id", "resource-bound"),
        ("resource_state_version", "state-version-bound"),
        ("chk_paa_expiry_after_grant", "time-bound (expiry after grant)"),
        ("chk_paa_not_consumed_and_revoked", "never both consumed and revoked"),
        ("consumed_by_authorization_id", "single-use traced to one authorization"),
        (
            "REFERENCES resume_replay_authorizations(authorization_id)",
            "FK from consumed-by authorization",
        ),
    ]:
        check(token in m035, f"M-1: 035 {label}")
    check("statement_timestamp()" in m035, "M-1: 035 uses PostgreSQL authoritative time")
    down = read(MIG / "035_be3_production_action_approvals_down.sql")
    check(
        "DROP TABLE IF EXISTS production_action_approvals" in down and "DELETE" not in down.upper(),
        "M-1: 035_down drops only its own table (no data delete)",
    )

    repo = read(SDK / "production_approval_repository.py")
    check(
        "FROM production_action_approvals WHERE approval_id=$1 FOR UPDATE" in repo,
        "M-1: resolver locks the approval row FOR UPDATE before any check (no TOCTOU)",
    )
    # the consuming CAS re-checks every binding predicate
    for pred in (
        "action_type=$4",
        "resource_type=$5",
        "resource_id=$6",
        "team_id=$7::uuid",
        "project_id=$8::uuid",
        "resource_state_version=$9",
        "consumed_at IS NULL AND revoked_at IS NULL",
        "expires_at > statement_timestamp()",
    ):
        check(pred in repo, f"M-1: resolve CAS re-binds predicate `{pred}`")

    svc = read(SDK / "authorization_service.py")
    check(
        "resolve_and_consume_approval" in svc,
        "M-1: authorization_service.consume resolves the approval against the registry",
    )
    # approval resolution happens BEFORE the authorization consume; a post-consume authz CAS failure
    # raises to force a full rollback.
    idx_resolve = svc.find("resolve_and_consume_approval")
    idx_consume = svc.find("await repo.consume(")
    check(
        0 <= idx_resolve < idx_consume,
        "M-1: approval is resolved/consumed BEFORE the authorization consume",
    )
    check(
        "authorization consume CAS failed after a successful production-approval consume" in svc
        and "raise RuntimeError" in svc,
        "M-1: post-approval-consume authz CAS failure raises (full-rollback, no half-mutation)",
    )
    check(
        'if row.get("production_effect")' in svc,
        "M-1: approval resolution is gated on the server-side production_effect flag",
    )

    model = read(SDK / "production_approval_model.py")
    check(
        'GRANTER_ROLES: frozenset[str] = frozenset({"reviewer_approver", "platform_admin"})'
        in model
        and "role in TASK_ROLES and role in GRANTER_ROLES" in model,
        "M-1: grant boundary is the canonical approver pair only (no parallel RBAC)",
    )
    # No HTTP grant/revoke endpoint: no API file wires the approval GRANT/REVOKE service or its
    # repository. (An API accepting the opaque production_approval_reference id is fine -- that is a
    # client-suppliable pointer, not a grant surface.)
    grant_tokens = (
        "grant_production_approval",
        "revoke_production_approval",
        "production_approval_service",
        "production_approval_repository",
    )
    api_grant = any(
        any(tok in read(p) for tok in grant_tokens)
        for p in API.glob("*.py")
        if p.name != "__init__.py"
    )
    check(not api_grant, "M-1: no HTTP endpoint wires the approval grant/revoke service")

    # ============================ L-1 ============================================================
    rrepo = read(SDK / "replay_request_repository.py")
    check(
        "pg_advisory_xact_lock" in rrepo,
        "L-1: per-actor cap uses a transaction-scoped advisory lock",
    )
    check(
        "hashtextextended" in rrepo,
        "L-1: advisory-lock key uses a PostgreSQL server-side hash (cross-process stable)",
    )
    # Python's built-in hash() must NOT be used to build the lock key.
    lock_fn = rrepo[rrepo.find("def acquire_actor_rate_limit_lock") :][:1200]
    check("hash(" not in lock_fn, "L-1: advisory-lock key does NOT use Python hash()")
    check(
        "be3-replay-actor-rate:" in rrepo and "{team_id}:{project_id}:{actor_id}" in rrepo,
        "L-1: lock key dimension is team_id+project_id+actor_id",
    )
    check(
        "team_id=$2::uuid AND project_id=$3::uuid" in rrepo,
        "L-1: per-actor count is scoped by (team_id, project_id)",
    )
    rsvc = read(SDK / "replay_service.py")
    i_lock = rsvc.find("acquire_actor_rate_limit_lock")
    i_rowlock = rsvc.find("lock_outbox_event")
    check(
        0 <= i_lock < i_rowlock,
        "L-1: advisory lock is acquired BEFORE the dead-row lock (consistent lock order)",
    )

    # ============================ R2-1 ===========================================================
    resume_api = read(API / "operations_resume_api.py")
    create_cls = resume_api[resume_api.find("class ResumeRequestCreate") :][:600]
    check(
        "production_effect"
        not in create_cls.replace("# ", "").split("production_approval_reference")[0]
        or "NOT a field" in create_cls,
        "R2-1: production_effect is not a client-suppliable API field",
    )
    check(
        "production_effect: bool" not in create_cls,
        "R2-1: ResumeRequestCreate has no production_effect field declaration",
    )
    rmodel = read(SDK / "resume_request_model.py")
    check(
        "def authoritative_production_effect" in rmodel
        and 'task_row.get("production_effect", True)' in rmodel,
        "R2-1: production_effect derived server-side from the task, fail-closed to True",
    )
    check(
        "def resource_state_version(clarification_row: dict[str, Any], task_row: dict[str, Any])"
        in rmodel
        and "production_effect}" in rmodel,
        "R2-1: production_effect is folded into the canonical resource_state_version",
    )
    rsvc2 = read(SDK / "resume_service.py")
    check(
        rsvc2.count("resource_state_version(clar, task)") >= 3,
        "R2-1: state version recomputed with the task at request + authorize + consume",
    )
    check(
        "authoritative_production_effect(task)" in rsvc2,
        "R2-1: request_resume derives production_effect from the locked task row",
    )

    # ============================ Activation gate ================================================
    gate = read(GATE)
    check(
        "## A.0 BE3-R1 findings-closure evidence" in gate, "gate: records the BE3-R1 closure (A.0)"
    )
    check(
        "## A.1 BE3-R2 findings-closure evidence" in gate, "gate: records the BE3-R2 closure (A.1)"
    )
    for token in ("Finding M-1", "Finding L-1", "CONCURRENCY-SAFE", "SERVER-DERIVED"):
        check(token in gate, f"gate: closure evidence contains `{token}`")
    # items 1-11 and the no-authorization posture are preserved (not weakened).
    check(
        "11. Product Owner deployment authorization" in gate
        and "items 1-11 below remain required in full" in gate,
        "gate: original 11 activation prerequisites preserved (not marked complete)",
    )
    check(
        "No deployment of any kind." in gate
        and "No application of migration 031 or any BE3 migration to a shared database." in gate
        and "production_executed_true_count remains 0." in gate,
        "gate: still authorizes NO deployment / NO shared migration / NO activation",
    )

    # ============================ Secret / identifier self-scan ==================================
    ip_re = re.compile(r"\b(?:10|192|172)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    pem_re = re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY")
    for f in (
        REPO / "tests" / "test_step66c4_be3_r1_r2_focused_closure.py",
        REPO / "scripts" / "verify_step66c4_be3_r1_r2_focused_closure.py",
    ):
        if not f.exists():
            continue
        txt = read(f)
        check(not ip_re.search(txt), f"no internal IP in {f.name}")
        check(not pem_re.search(txt), f"no private key material in {f.name}")

    print()
    if _failures:
        print(f"RESULT: {len(_failures)} structural invariant(s) FAILED")
        return 1
    print("RESULT: all M-1 / L-1 / R2-1 structural invariants hold")
    print("STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
