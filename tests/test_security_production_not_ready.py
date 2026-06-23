"""Step 54.1 -- security foundation is never production-ready; baselines preserved.

Also an anti-drift guard: the committed summary must match the collector output.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.security_foundation import (
    build_security_foundation_summary,
    collect_security_posture,
    load_security_foundation_summary,
    readiness_view,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "security" / "security-foundation-summary.yaml"


def test_summary_anti_drift() -> None:
    committed = load_security_foundation_summary(SUMMARY)
    assert committed is not None
    fresh = build_security_foundation_summary(ROOT)
    assert committed["securityFoundation"] == fresh["securityFoundation"]


def test_status_modeled_not_enforced_and_not_ready() -> None:
    p = collect_security_posture(ROOT)
    assert p["status"] == "modeled_not_enforced"
    assert p["productionReady"] is False
    assert p["productionGateEnabled"] is False


def test_readiness_view_not_ready() -> None:
    r = readiness_view(load_security_foundation_summary(SUMMARY))
    assert r["productionReady"] is False
    assert r["blockers"]


def test_no_unsafe_supply_chain_flags() -> None:
    p = collect_security_posture(ROOT)
    for k in (
        "githubWriteEnabled",
        "prCreationEnabled",
        "imagePushEnabled",
        "registryLoginEnabled",
        "externalScannerUploadEnabled",
        "committedSecretDetected",
    ):
        assert p[k] is False, k


def test_prior_stage_baselines_preserved_not_ready() -> None:
    # Step 51 runtime + Step 52 identity + Step 53 secret summaries remain present
    # and never claim production readiness.
    runtime = yaml.safe_load(
        (ROOT / "infra" / "kubernetes" / "runtime-baseline-summary.yaml").read_text("utf-8")
    )
    identity = yaml.safe_load(
        (ROOT / "infra" / "identity" / "identity-posture-summary.yaml").read_text("utf-8")
    )
    secret = yaml.safe_load(
        (ROOT / "infra" / "secrets" / "secret-foundation-summary.yaml").read_text("utf-8")
    )
    assert runtime and identity and secret
    assert secret["secretFoundation"]["productionReady"] is False
