#!/usr/bin/env python3
"""Step 60 -- release candidate model verifier (file + SDK).

Marker: RELEASE_CANDIDATE_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / "infra" / "release" / "release-candidate-model.yaml"
MARKER = "RELEASE_CANDIDATE_MODEL_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}
    rc = data.get("releaseCandidate", {}) or {}
    if rc.get("defaultTargetEnvironment") != "nonprod":
        bad("defaultTargetEnvironment must be nonprod")
    if rc.get("productionReady") is not False:
        bad("productionReady must be false")
    for st in ("draft", "ready_for_operator_review", "accepted_nonproduction", "blocked"):
        if st not in (rc.get("statuses") or []):
            bad(f"missing status: {st}")

    from shared.sdk.release_governance import CandidateError, build_candidate

    cand = build_candidate(project_id=None, version_label="v0-test", target_environment="nonprod")
    if cand.target_environment != "nonprod" or cand.production_ready is not False:
        bad("built candidate must be nonprod + production_ready false")
    if cand.to_dict().get("production_ready") is not False:
        bad("candidate dict production_ready must be false")

    # production target must be rejected
    for env in ("production", "prod"):
        try:
            build_candidate(project_id=None, version_label="x", target_environment=env)
            bad(f"production target {env} must be rejected")
        except CandidateError:
            pass

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] release candidate: nonprod default, production rejected, production_ready false")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
