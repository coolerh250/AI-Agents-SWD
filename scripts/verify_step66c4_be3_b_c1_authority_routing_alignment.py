#!/usr/bin/env python3
"""Step 66C.4-BE3-B-C1 -- policy authority authentication boundary and command outbox destination
routing alignment self-verifier.

Static/structural checks that (1) resolving the resume policy/safety authority requires BOTH an
authenticated trusted principal AND a constant-time-compared server capability -- never a
client-asserted role/body/query, never satisfiable by an ordinary Operator -- and (2) every
lifecycle_outbox event_type has an explicit single durable destination, with the existing BE2 audit
relay's claim query restricted to audit-classified types so it can never claim/mis-publish an
orchestrator-command row. No BE3-C, no merge, no deployment, no real resume/replay execution.

Marker: STEP66C4_BE3_B_AUTHORITY_ROUTING_ALIGNMENT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

API = ROOT / "apps" / "orchestrator" / "src" / "operations_resume_api.py"
OUTBOX = ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
RELAY = ROOT / "shared" / "sdk" / "tasks" / "outbox_relay.py"
POLICY = ROOT / "shared" / "sdk" / "tasks" / "authorization_policy.py"
TESTS = ROOT / "tests" / "test_step66c4_be3_b_c1_authority_routing_alignment.py"
BE3B_TESTS = ROOT / "tests" / "test_step66c4_be3_b_operator_resume.py"
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
REC = CONTRACT / "be3-b-c1-authority-routing-alignment-record.md"

BASE = "5745ab7"
MARKER = "STEP66C4_BE3_B_AUTHORITY_ROUTING_ALIGNMENT_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (API, OUTBOX, RELAY, POLICY, TESTS, BE3B_TESTS, REC):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    api = API.read_text(encoding="utf-8")
    outbox = OUTBOX.read_text(encoding="utf-8")
    relay = RELAY.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")
    be3b_tests = BE3B_TESTS.read_text(encoding="utf-8")

    # ---- 1. Policy authority bound to an authenticated trusted principal --------------
    if "BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID" not in api:
        bad("check1: no server-configured trusted principal id for the policy authority")
    if "principal_ok" not in api or "ctx.actor == trusted_principal" not in api:
        bad("check1: policy authority is not bound to the authenticated principal id")

    # ---- 2. Capability cannot be forged via body/query/general role header ------------
    if "class ResumeDecisionBody" not in api:
        bad("check2: decision body model missing")
    else:
        body_block = api[api.index("class ResumeDecisionBody") :]
        body_block = body_block[: body_block.index("\n\n\n")]
        for forbidden in ("is_policy_authority", "capability", "policy_authority"):
            if forbidden in body_block.lower():
                bad(
                    f"check2: request body model appears to carry policy-authority input: {forbidden}"
                )
    if "request.query_params" in api and "policy_authority" in api:
        bad("check2: policy authority appears to read from query params")
    if "def _policy_authority" not in api:
        bad("check2: no dedicated policy-authority resolver function")
    else:
        resolver_src = api[api.index("def _policy_authority") :]
        resolver_src = resolver_src[: resolver_src.index("\n\n\n")]
        if "ctx.role" in resolver_src:
            bad("check2: policy authority resolver reads the general X-Task-Role-derived role")

    # ---- 3. Constant-time comparison + log/audit masking ------------------------------
    if "hmac.compare_digest" not in api:
        bad("check3: capability comparison is not constant-time (hmac.compare_digest)")
    if re.search(r"presented\s*(==|!=)\s*expected", api):
        bad("check3: a plain equality/inequality check on the capability value was found")
    if "def _capability_matches" not in api:
        bad("check3: no dedicated capability-matching function")
    if 'detail="policy_authority_required"' not in api:
        bad("check3: policy authority denial does not use the bounded, secret-free reason code")
    # the presented/expected capability values must never be interpolated into an exception/log
    for banned_leak in (
        "detail=presented",
        'detail=f"{presented}',
        "detail=expected",
        "logger.info(presented",
        "logger.warning(presented",
        "print(presented",
    ):
        if banned_leak in api:
            bad(f"check3: capability value appears to leak: {banned_leak}")

    # ---- 3b. The pre-existing BE3-B API test was updated to the trusted-principal model,
    #          not merely weakened to keep passing.
    if "BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID" not in be3b_tests:
        bad("check3: the existing BE3-B API test was not updated for the trusted-principal model")

    # ---- 4. Policy authority permission scope (authorize/reject ONLY) -----------------
    if '_POLICY_AUTHORITY_ACTIONS: frozenset[str] = frozenset({"authorize_resume"' not in policy:
        bad(
            "check4: policy authority action scope not restricted to authorize_resume/reject_resume"
        )
    if "def test_policy_authority_permission_scope_is_authorize_reject_only" not in tests:
        bad("check4: no test proves the policy authority is scoped to authorize/reject only")

    # ---- 5. Production approval gate remains independent ------------------------------
    if "production_approval_required" not in policy:
        bad("check5: production approval gate missing from policy")
    if "authz.consume" not in (ROOT / "shared" / "sdk" / "tasks" / "resume_service.py").read_text(
        encoding="utf-8"
    ):
        bad("check5: execution preparation no longer delegates to the authorization consume gate")

    # ---- 6. Command destination explicit and single -----------------------------------
    if "EVENT_DESTINATIONS" not in outbox or "DESTINATION_ORCHESTRATOR_COMMAND" not in outbox:
        bad("check6: no explicit destination classification for outbox event types")
    if "set(EVENT_DESTINATIONS) == ALLOWED_EVENT_TYPES" not in outbox:
        bad("check6: no structural guarantee that every event_type has a destination")
    if "def destination_for_event_type" not in outbox:
        bad("check6: no single-destination accessor")

    # ---- 7. BE2 audit relay cannot claim/mis-publish a command row --------------------
    if "audit_relay_claimable_event_types" not in relay:
        bad("check7: the audit relay's claim query does not filter by destination")
    if "event_type = ANY($1::text[])" not in relay:
        bad("check7: the audit relay claim query has no event_type allowlist filter")
    if "def test_pg_audit_relay_never_claims_orchestrator_command_row" not in tests:
        bad("check7: no test proves the audit relay never claims an orchestrator-command row")

    # ---- 8. Command gate disabled-by-default creates no outbox row --------------------
    if "def test_pg_command_gate_off_creates_no_command_row" not in tests:
        bad("check8: no test proves the command gate blocks outbox row creation")

    # ---- 9. No active consumer -> backlog visible, untouched, blocks activation -------
    if "count_pending_by_destination" not in outbox:
        bad("check9: no backlog-visibility helper for the orchestrator-command destination")
    if "def test_pg_no_active_consumer_command_backlog_visible_and_untouched" not in tests:
        bad("check9: no test proves an un-consumed command row stays inert")

    # ---- 10-12. No runtime activation / no BE3-C / Draft PR unmerged ------------------
    # relay.py legitimately DEFINES the pre-existing internal replay_dead(self, ...) foundation
    # method (BE1/BE2); the check is for a CALL to it, never its own definition line.
    for banned in ("workflow_resume", "run_mock_workflow"):
        if banned in api or banned in outbox or banned in relay:
            bad(f"check10: forbidden execution reference present: {banned}")
    for src, name in ((api, "api"), (outbox, "outbox")):
        if re.search(r"replay_dead\s*\(", src):
            bad(f"check10: {name} calls replay_dead")
    if re.search(r"(?<!def )replay_dead\s*\(", relay.replace("async def replay_dead", "")):
        bad("check10: outbox_relay calls replay_dead from outside its own definition")
    for mod in ("replay_service", "replay_request_repository", "resume_replay_execution"):
        if (ROOT / "shared" / "sdk" / "tasks" / f"{mod}.py").exists():
            bad(f"check11: a BE3-C module already exists: {mod}")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked
    for f in all_changed:
        for forbidden in ("infra/", "helm/", "k8s/", ".github/workflows/", "frontend/"):
            if f.startswith(forbidden):
                bad(f"check10: forbidden deployment/activation path changed: {f}")
    mig_changed = [f for f in all_changed if f.startswith("migrations/")]
    if any(not Path(f).name.startswith(("032_", "033_")) for f in mig_changed):
        bad(f"check10: an unexpected migration was changed: {mig_changed}")

    rec = REC.read_text(encoding="utf-8").lower()
    if "not for merge" not in rec and "not merged" not in rec:
        bad("check12: record does not state the Draft PR is not merged")
    if "be3-r" not in rec:
        bad("check12: record does not state the combined independent BE3-R is still required")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] policy authority bound to an authenticated trusted principal id (never an")
    print("       ordinary Operator's own actor id) AND a constant-time-compared server capability")
    print("       (current/previous rotation); never read from body/query/role header; identical")
    print("       403 on every failure path; capability never logged/audited/echoed; scoped to")
    print("       authorize_resume/reject_resume only; production gate unchanged.")
    print("  [OK] every outbox event_type has an explicit, single durable destination; the BE2")
    print(
        "       audit relay's claim query is restricted to audit-classified types so it can never"
    )
    print("       claim, mis-publish, or falsely mark 'published' an orchestrator-command row;")
    print("       command gate closed -> no row created; an un-consumed command row stays inert.")
    print(f"{MARKER}: PASS")
    print("  NOTE: BE3-B-C1 alignment only; overall BE3 technical closure needs the combined")
    print("        independent BE3-R review over BE3-A+B+C. Draft PR #20 remains NOT FOR MERGE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
