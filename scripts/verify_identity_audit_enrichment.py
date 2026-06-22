#!/usr/bin/env python3
"""Step 52.3 -- identity audit enrichment verifier (NO network).

Validates the planned identity audit enrichment: future OIDC fields are planned
but disabled, and redaction rules forbid raw email lists, raw group IDs, raw
tokens, raw OIDC claims, CSRF, nonce, and chain-of-thought.

Marker: IDENTITY_AUDIT_ENRICHMENT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
sys.path.insert(0, str(ROOT))  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load((IDENT / "identity-audit-mapping.yaml").read_text(encoding="utf-8"))
    enr = data.get("futureOidcEnrichment")
    if not enr:
        bad("identity-audit-mapping.yaml missing futureOidcEnrichment section")
        print("IDENTITY_AUDIT_ENRICHMENT_VERIFY: FAIL")
        return 1

    if enr["enabled"] is not False:
        bad("audit enrichment must be enabled=false (planned only)")
    fields = enr["plannedFields"]
    for k in (
        "providerKey",
        "subjectHash",
        "emailHash",
        "groupMappingRuleId",
        "roleMappingDecision",
        "unknownUserDenied",
        "sessionKeyId",
        "sessionRevoked",
        "forcedLogoutReason",
    ):
        if k not in fields:
            bad(f"planned audit field missing: {k}")
    if not failures:
        ok("OIDC subject/email/group enrichment planned but disabled; subject_hash/email_hash used")

    red = enr["redactionRules"]
    for k in (
        "rawEmailListPersisted",
        "rawGroupIdsPersisted",
        "rawTokenPersisted",
        "rawOidcClaimsPersisted",
        "csrfPersisted",
        "noncePersisted",
        "chainOfThoughtPersisted",
    ):
        if red[k] is not False:
            bad(f"redaction rule {k} must be false")
    if not [x for x in failures if "redaction" in x]:
        ok("no raw email list / group IDs / token / claims / CSRF / nonce / chain-of-thought")

    # neverRecorded retains the Step 52.1 invariants
    never = set(data.get("neverRecorded", []))
    if not {"raw_session_token", "csrf_token", "chain_of_thought"} <= never:
        bad("neverRecorded must still include raw_session_token/csrf_token/chain_of_thought")
    else:
        ok("Step 52.1 neverRecorded invariants retained")

    # production_executed flag remains false in recorded fields
    if data["recordedFields"].get("productionExecutedFlag") != "production_executed":
        bad("productionExecutedFlag mapping changed")
    else:
        ok("production_executed flag mapping intact (always false)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_AUDIT_ENRICHMENT_VERIFY: FAIL")
        return 1
    print("IDENTITY_AUDIT_ENRICHMENT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
