"""Step 52.3 -- unknown user policy + engine denial."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.identity import IdentityClaims, load_rules, load_safe_fixture, map_identity_to_role

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "unknown-user-policy.yaml"


def _u() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["unknownUser"]


def test_deny_rules() -> None:
    d = _u()["denyRules"]
    for k in (
        "missingSubject",
        "missingEmail",
        "emailNotVerified",
        "missingGroups",
        "noGroupMatch",
    ):
        assert d[k] == "deny"


def test_no_default_no_auto_provision() -> None:
    u = _u()
    assert u["defaultRole"] == "none"
    assert u["autoViewer"] is False
    assert u["selfRegistration"] is False
    assert u["justInTimeProvisioning"] is False
    assert u["platformAdminFallback"] is False


def test_audit_denied_without_raw() -> None:
    a = yaml.safe_load(F.read_text(encoding="utf-8"))["audit"]
    assert a["deniedAttemptRecorded"] is True
    assert a["rawTokenRecorded"] is False
    assert a["rawEmailRecorded"] is False
    assert a["rawGroupsRecorded"] is False


def test_engine_denies_unknown_user_end_to_end() -> None:
    rules = load_rules(load_safe_fixture())
    d = map_identity_to_role(
        IdentityClaims(
            subject="s",
            email="a@example.com",
            email_verified=True,
            groups=["unmapped-group"],
            provider_key="p",
        ),
        rules,
    )
    assert d.allowed is False and d.role is None and d.unknown_user is True
