"""Step 52.1 -- identity-to-audit mapping + live audit refs."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.operator_actions.audit_events import safe_operator_action_refs

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-audit-mapping.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_recorded_fields() -> None:
    rec = _d()["recordedFields"]
    for k in ("actorIdentity", "role", "action", "productionExecutedFlag", "controlledOnly"):
        assert k in rec


def test_never_recorded() -> None:
    never = _d()["neverRecorded"]
    for k in ("raw_session_token", "csrf_token", "confirmation_nonce_raw", "chain_of_thought"):
        assert k in never


def test_live_refs_safe() -> None:
    refs = safe_operator_action_refs(
        action_type="delivery_package.accept", identity_key="operator-test", role="operator"
    )
    assert refs["production_executed"] is False
    assert refs["controlled_only"] is True
    assert refs["identity_key"] == "operator-test"
    blob = repr(refs).lower()
    for bad in ("token", "secret", "nonce", "password", "chain_of_thought"):
        assert bad not in blob


def test_traceability() -> None:
    t = _d()["traceability"]
    assert t["humanAcceptanceTraceable"] is True
    assert t["verificationRerunTraceable"] is True
    assert t["futureOidcSubjectMapping"]["configured"] is False
