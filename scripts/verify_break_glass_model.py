#!/usr/bin/env python3
"""Step 52.3 -- break-glass model verifier (NO network).

Validates break-glass is disabled with no login route / admin button / automatic
platform_admin access, and that all production requirements (approval, time-
bound, audit, post-incident review) are recorded as required.

Marker: BREAK_GLASS_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    f = IDENT / "break-glass-model.yaml"
    if not f.is_file():
        bad("missing break-glass-model.yaml")
        print("BREAK_GLASS_MODEL_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    bg = data["breakGlass"]

    if bg["enabled"] is not False:
        bad("break-glass must be disabled")
    if bg["loginRouteExists"] is not False:
        bad("no break-glass login route allowed")
    if bg["adminButtonExists"] is not False:
        bad("no break-glass admin button allowed")
    if bg["platformAdminAutomaticAccess"] is not False:
        bad("platform_admin must not get automatic break-glass access")
    if not failures:
        ok("break-glass disabled; no login route; no admin button; no platform_admin auto-access")

    req = bg["requirements"]
    for k in (
        "productionIdentityRequired",
        "separateApprovalRequired",
        "timeBoundSessionRequired",
        "reasonRequired",
        "auditRequired",
        "postIncidentReviewRequired",
    ):
        if req[k] is not True:
            bad(f"requirement {k} must be true")
    if not [x for x in failures if "requirement" in x]:
        ok(
            "requires production identity + approval + time-bound + reason + audit + post-incident review"
        )

    pro = bg["prohibitions"]
    for k in (
        "canBeTestLocal",
        "canBypassAudit",
        "autoGrantsKubernetes",
        "autoGrantsArgoCD",
        "autoGrantsGitHub",
        "autoGrantsProductionDeploy",
    ):
        if pro[k] is not False:
            bad(f"prohibition {k} must be false")
    if not [x for x in failures if "prohibition" in x]:
        ok("cannot be test-local; cannot bypass audit; no auto K8s/ArgoCD/GitHub/prod-deploy grant")

    if data.get("dependencies", {}).get("productionApprovalModel") != "60":
        bad("must depend on the future production approval model (Step 60)")
    else:
        ok("depends on future production approval model (Step 60)")

    # No break-glass route/button anywhere in the app source.
    hits: list[str] = []
    for base in (ROOT / "apps", ROOT / "shared" / "sdk"):
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                low = line.lower()
                if (
                    "break" in low
                    and "glass" in low
                    and ("route" in low or "@router" in low or "@app." in low)
                ):
                    hits.append(f"{p.relative_to(ROOT)}: {line.strip()[:70]}")
    if hits:
        for h in hits:
            bad(f"possible break-glass route: {h}")
    else:
        ok("no break-glass route/endpoint in app or SDK source")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("BREAK_GLASS_MODEL_VERIFY: FAIL")
        return 1
    print("BREAK_GLASS_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
