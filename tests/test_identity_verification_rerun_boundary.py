"""Step 52.1 -- verification rerun identity boundary + live allowlist."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.operator_actions.verification_runner import ALLOWLISTED_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "verification-rerun-identity-boundary.yaml"


def _v() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["verificationRerun"]


def test_allowlist_matches_runner() -> None:
    inv_keys = {s["key"] for s in _v()["allowlistedScripts"]}
    assert inv_keys == set(ALLOWLISTED_SCRIPTS)


def test_no_shell_no_arbitrary() -> None:
    ex = _v()["execution"]
    assert ex["shell"] is False
    assert ex["arbitraryCommandProhibited"] is True
    assert ex["arbitraryArgsProhibited"] is True
    assert ex["userSuppliedPathProhibited"] is True


def test_full_regression_higher_confirmation() -> None:
    fr = next(s for s in _v()["allowlistedScripts"] if s["key"] == "full_regression")
    assert fr["higherConfirmation"] is True


def test_rerun_does_not_mutate_production() -> None:
    rdn = _v()["rerunDoesNot"]
    for forbidden in ("mutate_production", "execute_deploy", "write_github", "sync_argocd"):
        assert forbidden in rdn
