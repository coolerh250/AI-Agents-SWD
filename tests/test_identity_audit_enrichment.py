"""Step 52.3 -- identity audit enrichment (planned, redacted)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-audit-mapping.yaml"


def _enr() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["futureOidcEnrichment"]


def test_planned_but_disabled() -> None:
    enr = _enr()
    assert enr["enabled"] is False
    assert enr["step"] == "52.3"


def test_planned_fields_use_hashes_not_raw() -> None:
    f = _enr()["plannedFields"]
    assert f["subjectHash"] == "subject_hash"
    assert f["emailHash"] == "email_hash"
    assert f["groupMappingRuleId"] == "group_mapping_rule_id"
    for k in (
        "providerKey",
        "roleMappingDecision",
        "unknownUserDenied",
        "sessionKeyId",
        "sessionRevoked",
        "forcedLogoutReason",
    ):
        assert k in f


def test_redaction_rules_forbid_raw() -> None:
    red = _enr()["redactionRules"]
    for k in (
        "rawEmailListPersisted",
        "rawGroupIdsPersisted",
        "rawTokenPersisted",
        "rawOidcClaimsPersisted",
        "csrfPersisted",
        "noncePersisted",
        "chainOfThoughtPersisted",
    ):
        assert red[k] is False


def test_step_52_1_invariants_retained() -> None:
    data = yaml.safe_load(F.read_text(encoding="utf-8"))
    never = set(data["neverRecorded"])
    assert {"raw_session_token", "csrf_token", "chain_of_thought"} <= never
