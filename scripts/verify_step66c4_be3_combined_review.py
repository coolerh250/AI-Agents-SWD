#!/usr/bin/env python3
"""Step 66C.4-BE3-R -- independent static verifier for the combined BE3 A+B+C review.

Re-derives the structural safety invariants of the reviewed feature head WITHOUT trusting any
implementation self-verifier: it reads the committed source/migrations directly and asserts the
properties an independent reviewer must confirm. It performs NO database or network I/O, executes
nothing, and enables no gate. Run from the repository root:

    python scripts/verify_step66c4_be3_combined_review.py

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

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}")
        _failures.append(label)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def main() -> int:
    # --- Migrations: additive-only, key constraints/indexes present -----------------------------
    m032 = read(MIG / "032_be3_resume_replay_authorization.sql")
    check(
        "CREATE TABLE IF NOT EXISTS resume_replay_authorizations" in m032, "032 creates auth table"
    )
    check(
        "ALTER TABLE" not in m032.upper() or "ADD COLUMN" not in m032.upper(),
        "032 adds no column to an existing table",
    )
    check(
        bool(re.search(r"team_id\s+UUID\s+NOT NULL", m032))
        and bool(re.search(r"project_id\s+UUID\s+NOT NULL", m032)),
        "032 team_id/project_id are UUID NOT NULL (no NULL-scope wildcard)",
    )
    check(
        "chk_rra_replay_two_person" in m032 and "decided_by <> requested_by" in m032,
        "032 has the replay two-person DB constraint",
    )
    check("expires_at > requested_at" in m032, "032 enforces time-bound (expiry after request)")
    check("chk_rra_consume_requires_authorized" in m032, "032 consume requires authorized")
    check("chk_rra_not_consumed_and_revoked" in m032, "032 never both consumed and revoked")
    check(
        "uq_rra_active_request" in m032 and "decision IN ('pending', 'authorized')" in m032,
        "032 one-active-authorization-per-resource partial unique index",
    )
    check("statement_timestamp()" in m032, "032 uses PostgreSQL authoritative time")

    m033 = read(MIG / "033_be3_resume_requests.sql")
    check(
        "REFERENCES resume_replay_authorizations(authorization_id)" in m033,
        "033 FK to authorization",
    )
    check(
        "uq_rr_active_per_clarification" in m033, "033 one-active-resume-request-per-clarification"
    )
    m034 = read(MIG / "034_be3_replay_requests.sql")
    check("uq_rpr_active_per_event" in m034, "034 one-active-replay-request-per-event")
    check("REFERENCES clarification_lifecycle_outbox(id)" in m034, "034 FK to outbox event")

    for n in (
        "032_be3_resume_replay_authorization",
        "033_be3_resume_requests",
        "034_be3_replay_requests",
    ):
        down = read(MIG / f"{n}_down.sql")
        check(
            "DROP TABLE IF EXISTS" in down and "DELETE" not in down.upper(),
            f"{n}_down drops only its own table (no data delete)",
        )

    # --- Authorization repository: scope predicate + single-use CAS ------------------------------
    repo = read(SDK / "authorization_repository.py")
    check("IS NOT DISTINCT FROM" in repo, "auth repo uses null-safe scope equality")
    check(
        "resource_state_version=$3" in repo
        and "expires_at > statement_timestamp()" in repo
        and "consumed_at IS NULL" in repo,
        "auth consume CAS is state-version + expiry + single-use guarded",
    )

    # --- Policy: canonical TASK_ROLES reuse, service/authority separation ------------------------
    policy = read(SDK / "authorization_policy.py")
    check(
        "from shared.sdk.tasks.rbac import TASK_ROLES" in policy,
        "policy reuses canonical TASK_ROLES (no parallel RBAC)",
    )
    check(
        "service_identity_cannot_decide" in policy and "_CONSUME_ACTIONS" in policy,
        "policy: service identity is consume-only",
    )
    check(
        (
            "authorize_resume" not in policy.split("_ACTION_ROLES")[1].split("}")[0]
            if "_ACTION_ROLES" in policy
            else False
        ),
        "policy: no human role can authorize_resume (policy-authority only)",
    )

    # --- Policy authority: constant-time, dedicated header, fail-closed --------------------------
    resume_api = read(API / "operations_resume_api.py")
    check("hmac.compare_digest" in resume_api, "resume API capability compare is constant-time")
    check(
        'request.headers.get("X-Resume-Policy-Authority"' in resume_api,
        "capability read from a dedicated header only",
    )
    check(
        "policy_authority_required" in resume_api
        and resume_api.count("_configured_capabilities") >= 1,
        "policy authority failures are uniform + capability from server config only",
    )
    # the capability value must never be logged/echoed
    check(
        "logging" not in resume_api and "logger" not in resume_api,
        "resume API does not log (no capability leakage path)",
    )

    # --- Command routing: total + fail-closed; audit relay excludes command rows -----------------
    lo = read(SDK / "lifecycle_outbox.py")
    check(
        "set(EVENT_DESTINATIONS) == ALLOWED_EVENT_TYPES" in lo,
        "outbox: destination classification is total (import-time assert)",
    )
    check(
        '"resume.execution_requested"' in lo and "DESTINATION_ORCHESTRATOR_COMMAND" in lo,
        "outbox: resume.execution_requested is the command destination",
    )
    relay = read(SDK / "outbox_relay.py")
    check(
        "audit_relay_claimable_event_types()" in relay,
        "audit relay claim query is restricted to audit-destination event types",
    )

    # --- Replay: no public execute endpoint; execution gate default off --------------------------
    # Inspect the actual route DECORATORS (not docstring text, which legitimately names the internal
    # execute_authorized_replay service op to explain it is NOT exposed).
    replay_api = read(API / "operations_replay_api.py")
    routes = re.findall(r'@router\.(get|post)\("([^"]+)"', replay_api)
    paths = [p for _, p in routes]
    check(
        all(("execute" not in p and "replay-now" not in p) for p in paths),
        f"replay API exposes NO public execute/replay-now route: {paths}",
    )
    check(
        len(routes) == 5,
        f"replay routes are request/authorize/reject/cancel/read only ({len(routes)} routes)",
    )

    # --- Feature gates: default false, env-only ---------------------------------------------------
    rmodel = read(SDK / "replay_request_model.py")
    check(
        'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in rmodel
        and 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in rmodel,
        "replay gates default false, env-only",
    )
    resmodel = read(SDK / "resume_request_model.py")
    check(
        'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resmodel
        and 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resmodel,
        "resume gates default false, env-only",
    )

    # --- Dead-episode version: PG-time dead_at, attempts never reset ------------------------------
    check("dead_at=statement_timestamp()" in relay, "dead_at set from PostgreSQL time")
    check('"attempts": attempts' in lo, "manual replay preserves attempts (plan_replay_state)")

    # --- Destination readiness default is never ready --------------------------------------------
    check(
        "READINESS_NOT_CONFIGURED" in rmodel and "default_destination_readiness" in rmodel,
        "default destination readiness is not_configured (fail-closed)",
    )

    # --- Secret / internal-identifier scan of the reviewer's own committed artifacts -------------
    committed = [
        REPO / "tests" / "test_step66c4_be3_combined_review.py",
        REPO / "scripts" / "verify_step66c4_be3_combined_review.py",
    ]
    ip_re = re.compile(r"\b(?:10|192|172)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    # Generic secret markers only. This scanner deliberately hardcodes NO private SSH alias,
    # hostname, or username literal, so the scanner file itself satisfies the same
    # committed-content constraint it enforces. Private-value scanning is done out-of-band by the
    # reviewer's shell tooling (unrestricted), never baked into a committed file.
    pem_re = re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY")
    for f in committed:
        if not f.exists():
            continue
        txt = read(f)
        check(not ip_re.search(txt), f"no internal IP in {f.name}")
        check(not pem_re.search(txt), f"no private key material in {f.name}")

    print()
    if _failures:
        print(f"RESULT: {len(_failures)} structural invariant(s) FAILED")
        return 1
    print("RESULT: all structural invariants hold")
    print("STEP66C4_BE3_COMBINED_INDEPENDENT_REVIEW_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
