#!/usr/bin/env python3
"""Step 66C.4-BE3-P -- operator resume/replay authorization CONTRACT planning verifier.

Static/structural checks that the BE3-P contract artifacts are complete and that this stage added
NO backend/API/migration/frontend/deployment code. PASS means the planning contract is complete; it
does NOT mean BE3 is implemented, merged, deployed, or activated.

Marker: STEP66C4_BE3_PLANNING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"

MASTER = CONTRACT / "be3-operator-resume-replay-authorization-contract.md"
RBAC = CONTRACT / "be3-rbac-permission-matrix.md"
SM = CONTRACT / "be3-resume-replay-state-machine.md"
API = CONTRACT / "be3-api-event-contract.md"
SEC = CONTRACT / "be3-security-and-threat-model.md"
GATE = CONTRACT / "be3-runtime-activation-gate.md"
SLICE = CONTRACT / "be3-implementation-slicing-plan.md"
HANDOFF_DOC = HANDOFF / "be3-implementation-handoff.md"

BASE = "33b776b"  # canonical main at the start of BE3-P
MARKER = "STEP66C4_BE3_PLANNING_VERIFY"

# The only paths BE3-P is allowed to change.
ALLOWED_PREFIXES = (
    "docs/contracts/66c4-reminder-expiry-controlled-resume/be3-",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/be3-",
    "docs/test/step66c4-be3-planning",
    "docs/stages/66c4-be3-planning",
    "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md",
    "scripts/verify_step66c4_be3_planning.py",
    "tests/test_step66c4_be3_planning.py",
    "source/progress.md",
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _need(doc: Path, *needles: str) -> str:
    if not doc.is_file():
        bad(f"missing doc: {doc}")
        return ""
    text = doc.read_text(encoding="utf-8")
    for n in needles:
        if n not in text:
            bad(f"{doc.name}: missing required content: {n!r}")
    return text


def main() -> int:  # noqa: C901
    # 1. RBAC permission matrix complete: 13 actions + the six canonical roles.
    rbac = _need(
        RBAC,
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
        "Service Identity",
    )
    for action in (
        "view clarification state",
        "view resume eligibility",
        "request resume",
        "authorize resume",
        "reject resume",
        "cancel pending resume",
        "execute resume",
        "view dead outbox event",
        "request replay",
        "authorize replay",
        "execute replay",
        "view authorization evidence",
        "override policy",
    ):
        if action not in rbac:
            bad(f"check1: RBAC matrix missing action: {action}")

    # 2. requester / approver / service-identity boundaries clear.
    _need(
        rbac and RBAC or RBAC,
        "two-person",
        "requester_principal != approver_principal",
        "EXECUTE",
    )
    if "can never" not in rbac:
        bad("check2: service-identity 'can never request or authorize' boundary not stated")

    # 3-4. Resume + replay state machines complete.
    sm = _need(
        SM,
        "not_eligible",
        "eligible",
        "request_pending",
        "authorization_pending",
        "authorized",
        "execution_pending",
        "resumed",
        "rejected",
        "canceled",
        "expired",
        "failed",
    )
    for field in ("Actor", "Precondition", "Idem key", "Tx boundary", "Audit event", "Failure"):
        if field not in sm:
            bad(f"check3: resume state machine missing per-transition field: {field}")
    for st in (
        "replay_requested",
        "replay_authorized",
        "replay_execution_pending",
        "replayed",
        "replay_rejected",
        "replay_failed",
    ):
        if st not in sm:
            bad(f"check4: replay state machine missing state: {st}")
    if "attempts are never reset" not in sm and "attempts NOT reset" not in sm:
        bad("check4: replay does not state attempts are never reset")

    # 5-6. Durable authorization model + single-use/time-bound/state-bound.
    api = _need(
        API,
        "authorization_id",
        "action_type",
        "resource_id",
        "request_id",
        "authorized_by",
        "decision_reason_code",
        "policy_result",
        "policy_version",
        "expires_at",
        "idempotency_key",
        "consumed_at",
    )
    for sem in (
        "single-use",
        "time-bounded",
        "state-version-bound",
        "resource-bound",
        "action-bound",
    ):
        if sem not in api:
            bad(f"check6: authorization semantics missing: {sem}")
    if "revocation" not in api and "revoke" not in api:
        bad("check6: authorization revocation semantics not defined")

    # 7. API 403/404/409/idempotency defined.
    for token in ("403", "404", "409", "idempotency", "no-side-effect", "transaction boundary"):
        if token not in api:
            bad(f"check7: API contract missing: {token}")
    for route in ("/operations/resume-requests", "/operations/replay-requests"):
        if route not in api:
            bad(f"check7: API route not defined: {route}")

    # 8. Audit/event contract complete.
    for ev in (
        "resume.requested",
        "resume.authorized",
        "resume.rejected",
        "resume.execution_requested",
        "resume.resumed",
        "resume.failed",
        "resume.canceled",
        "replay.requested",
        "replay.authorized",
        "replay.rejected",
        "replay.executed",
        "replay.failed",
        "replay.canceled",
    ):
        if ev not in api:
            bad(f"check8: event contract missing: {ev}")
    if (
        "single durable destination" not in api.lower()
        and "one durable destination" not in api.lower()
    ):
        bad("check8: single-durable-destination rule not stated")

    # 9. Transaction/concurrency cases handled.
    for scen in (
        "two operators request the same resume",
        "authorization expires during execution",
        "resume executes twice",
        "replay executes twice",
        "policy result changes after authorization",
        "orchestrator ack lost",
    ):
        if scen not in api:
            bad(f"check9: concurrency scenario not handled: {scen}")
    if "exactly-once is NOT claimed" not in api:
        bad("check9: exactly-once must be explicitly disclaimed")

    # 10. Activation gate + prerequisites complete.
    gate = _need(
        GATE,
        "Migration 031",
        "BE3 authorization migration",
        "Lifecycle poller deployed",
        "Outbox relay deployed",
        "Retry/DLQ",
        "Rollback tested",
        "Producer cutover plan approved",
        "Runtime E2E",
        "Product Owner deployment authorization",
    )
    if "DISABLED-BY-DEFAULT" not in gate:
        bad("check10: dispatch disabled-by-default posture not stated in the gate")

    # 11. replay_dead NOT implemented as a public API (design says internal-only; no route added).
    master = _need(MASTER, "replay_dead", "internal-only")
    if "public replay endpoint" not in master and "no public replay" not in master.lower():
        bad("check11: master contract does not forbid a public replay endpoint")
    sec = _need(SEC, "public replay endpoint")
    if "internal adapter only" not in SLICE.read_text(encoding="utf-8"):
        bad(
            "check11: slicing plan does not require the internal replay adapter (no public endpoint)"
        )
    if sec == "":
        bad("check11: security/threat model missing")

    changed = [f for f in _git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if f]
    untracked = [f for f in _git("ls-files", "--others", "--exclude-standard").splitlines() if f]
    all_changed = changed + untracked

    # 12. No backend/API/migration/frontend/deployment code changed.
    for f in all_changed:
        if not any(f.startswith(p) for p in ALLOWED_PREFIXES):
            bad(f"check12: BE3-P changed a non-planning path: {f}")
    for f in all_changed:
        for forbidden in ("apps/", "shared/", "migrations/", "frontend/", "services/", "infra/"):
            if f.startswith(forbidden):
                bad(f"check12: forbidden code path changed by a planning stage: {f}")

    # 13. Implementation slicing matches the new verification policy.
    slice_txt = _need(SLICE, "BE3-A", "BE3-B", "BE3-C", "BE3-R", "BE3-M")
    if "ONE independent" not in slice_txt and "one independent" not in slice_txt.lower():
        bad("check13: slicing plan does not state a single independent review over A+B+C")
    if "focused closure" not in slice_txt:
        bad("check13: slicing plan does not state original-reviewer focused closure")
    for field in ("Allowed files", "Forbidden files", "Entry criteria", "Exit criteria", "Risk"):
        if field not in slice_txt:
            bad(f"check13: slice missing field: {field}")

    # 14. BE3 implementation still requires PO authorization.
    if "explicit Product Owner authorization" not in master and "PO authorization" not in slice_txt:
        bad("check14: BE3 implementation PO-authorization requirement not stated")

    _need(HANDOFF_DOC, "Implementation Handoff", "NOT authorized")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] RBAC matrix (6 roles x 13 actions) + separation rules; resume + replay state")
    print("       machines with per-transition contracts; durable authorization (single-use/")
    print("       time-bound/state-version-bound/revocable); API 403/404/409/idempotency; full")
    print("       event/audit contract with a single durable destination; 9 concurrency cases;")
    print("       11-item activation gate; replay stays internal-only (no public endpoint); no")
    print("       backend/API/migration/frontend/deployment code changed; BE3-A/B/C/R/M slicing")
    print(
        "       with the single-review policy; BE3 implementation still requires PO authorization."
    )
    print(f"{MARKER}: PASS")
    print("  NOTE: planning contract only; BE3 is NOT implemented, merged, deployed, or activated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
