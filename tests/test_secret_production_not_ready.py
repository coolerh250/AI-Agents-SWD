"""Step 53 -- production secret management is never ready; Step 51/52 intact."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.secrets_foundation import (
    build_secret_foundation_summary,
    collect_secret_posture,
    readiness_view,
)

ROOT = Path(__file__).resolve().parents[1]


def test_posture_modeled_fail_closed() -> None:
    p = collect_secret_posture()
    assert p["status"] == "modeled_fail_closed_not_configured"
    assert p["productionReady"] is False
    assert p["productionStoreEnabled"] is False
    assert p["inlineValuesDetected"] is False


def test_readiness_lists_blockers_and_next_steps() -> None:
    r = readiness_view(build_secret_foundation_summary())
    assert r["productionReady"] is False
    assert r["blockers"]
    assert any("secret_store" in s for s in r["nextRequiredSteps"])


def test_committed_summary_anti_drift() -> None:
    from shared.sdk.secrets_foundation import load_secret_foundation_summary

    committed = load_secret_foundation_summary(
        ROOT / "infra" / "secrets" / "secret-foundation-summary.yaml"
    )
    assert committed == build_secret_foundation_summary()


def test_missing_source_yields_unknown(tmp_path: Path) -> None:
    (tmp_path / "infra" / "secrets").mkdir(parents=True)
    (tmp_path / "infra" / "secrets" / "secret-inventory.yaml").write_text(
        "secrets: []\n", encoding="utf-8"
    )
    p = collect_secret_posture(tmp_path)
    assert p["status"] == "unknown"
    assert p["productionReady"] is False


def test_step52_identity_summary_still_present() -> None:
    f = ROOT / "infra" / "identity" / "identity-posture-summary.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8"))["identityPosture"]
    assert d["status"] == "modeled_fail_closed_not_enabled"
