"""Step 52.4 -- identity posture collector (reads sources; fail-closed)."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.identity_posture import (
    build_identity_posture_summary,
    collect_identity_posture,
    load_identity_posture_summary,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "identity" / "identity-posture-summary.yaml"


def test_collector_modeled_fail_closed() -> None:
    p = collect_identity_posture()
    assert p["status"] == "modeled_fail_closed_not_enabled"
    assert p["productionIdentityReady"] is False
    assert p["productionAuthEnabled"] is False
    assert p["oidc"]["enabled"] is False
    assert p["session"]["rawTokenPersisted"] is False
    assert p["roleMapping"]["unknownUserBehavior"] == "deny"
    assert p["roleMapping"]["defaultRole"] == "none"
    assert p["breakGlass"]["enabled"] is False


def test_committed_summary_anti_drift() -> None:
    committed = load_identity_posture_summary(SUMMARY)
    rebuilt = build_identity_posture_summary()
    assert committed == rebuilt


def test_missing_source_yields_unknown_not_fake_pass(tmp_path: Path) -> None:
    # Copy only a partial identity dir -> collector must report unknown.
    (tmp_path / "infra" / "identity").mkdir(parents=True)
    (tmp_path / "infra" / "identity" / "authentication-inventory.yaml").write_text(
        "meta: {productionAuthEnabled: false}\n", encoding="utf-8"
    )
    p = collect_identity_posture(tmp_path)
    assert p["status"] == "unknown"
    assert p["productionIdentityReady"] is False
    assert "missingSources" in p


def test_summary_has_no_sensitive_values() -> None:
    from shared.sdk.identity_posture import find_sensitive

    assert find_sensitive(yaml.safe_load(SUMMARY.read_text(encoding="utf-8"))) == []
