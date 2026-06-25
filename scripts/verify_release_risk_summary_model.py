#!/usr/bin/env python3
"""Step 54.4 -- release risk summary model + scoring policy verifier.

Marker: RELEASE_RISK_SUMMARY_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load(name: str) -> dict:
    p = SEC / name
    if not p.is_file():
        bad(f"missing {name}")
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def main() -> int:
    model = _load("release-risk-summary-model.yaml").get("releaseRiskSummaryModel", {})
    scoring = _load("release-risk-scoring-policy.yaml").get("riskScoring", {})

    if model.get("productionReady") is not False:
        bad("releaseRiskSummaryModel.productionReady must be false")
    else:
        ok("model.productionReady=false")

    status_enum = set(model.get("statusEnum", []))
    if "production_ready" in status_enum or "production_approved" in status_enum:
        bad("statusEnum must not contain production_ready/production_approved")
    elif not {"not_ready", "blocked"} <= status_enum:
        bad(f"statusEnum incomplete: {status_enum}")
    else:
        ok("statusEnum excludes production_ready/approved; includes not_ready/blocked")

    forbidden = set(model.get("forbiddenStatuses", []))
    if not {"production_ready", "production_approved"} <= forbidden:
        bad("forbiddenStatuses must list production_ready + production_approved")
    else:
        ok("forbiddenStatuses lists production_ready + production_approved")

    if not model.get("inputs"):
        bad("releaseRiskSummaryModel.inputs empty")
    else:
        ok(f"{len(model['inputs'])} risk inputs enumerated")

    appr = model.get("approval", {})
    if (
        appr.get("producesProductionApproval") is not False
        or appr.get("producesDeploymentApproval") is not False
    ):
        bad("model must not produce production/deployment approval")
    else:
        ok("model produces neither production nor deployment approval")

    # Scoring policy.
    if (
        scoring.get("productionReady") is not False
        or scoring.get("productionGateEnabled") is not False
    ):
        bad("scoring policy must be productionReady=false, gate disabled")
    else:
        ok("scoring policy: productionReady=false, gate disabled")

    interp = scoring.get("interpretation", {})
    for key in (
        "scoreIsNotApproval",
        "lowScoreIsNotProductionReady",
        "missingRequiredEvidenceForcesNotReady",
        "productionGateRemainsDisabled",
    ):
        if interp.get(key) is not True:
            bad(f"scoring interpretation.{key} must be true")
    if not [f for f in failures if "interpretation" in f]:
        ok("scoring: score!=approval, low!=ready, missing-evidence->not_ready, gate disabled")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("RELEASE_RISK_SUMMARY_MODEL_VERIFY: FAIL")
        return 1
    print("RELEASE_RISK_SUMMARY_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
