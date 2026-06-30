#!/usr/bin/env python3
"""Step 62 -- production environment prerequisites verifier.

Marker: PRODUCTION_ENVIRONMENT_PREREQUISITES_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import prerequisites  # noqa: E402

MARKER = "PRODUCTION_ENVIRONMENT_PREREQUISITES_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if prerequisites.production_environment_exists():
        bad("production environment must not be claimed to exist")
    prereqs = prerequisites.load_prerequisites()
    if not prereqs:
        bad("no prerequisites declared")
    missing = prerequisites.missing_prerequisites()
    if not missing:
        bad("expected the production prerequisites to be missing at this stage")
    # kind nonprod / nonprod ArgoCD must never be claimed as production.
    import yaml

    model = yaml.safe_load(
        (ROOT / "infra" / "readiness" / "production-environment-prerequisite-model.yaml").read_text(
            encoding="utf-8"
        )
    )["productionEnvironmentPrerequisites"]
    if model.get("kindNonprodIsProduction") is not False:
        bad("kind nonprod must not be treated as production")
    if model.get("nonprodArgocdIsProductionArgocd") is not False:
        bad("nonprod ArgoCD must not be treated as production ArgoCD")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] production prerequisites: {len(missing)} missing; no production env faked")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
