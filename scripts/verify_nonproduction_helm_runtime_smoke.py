#!/usr/bin/env python3
"""Step 55 -- non-production Helm runtime smoke verifier.

Statically verifies the smoke runner + smoke values guardrails (always), then
gates the real render/install on a safe cluster. With no safe cluster it reports
BLOCKED_NO_SAFE_CLUSTER (never a faked install).

Marker: NONPROD_HELM_RUNTIME_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import section_status  # noqa: E402

MARKER = "NONPROD_HELM_RUNTIME_SMOKE_VERIFY"
RUNNER = ROOT / "scripts" / "run_nonproduction_helm_smoke.sh"
VALUES = (
    ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values-nonprod-smoke.yaml"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not RUNNER.is_file():
        bad("missing run_nonproduction_helm_smoke.sh")
    else:
        src = RUNNER.read_text(encoding="utf-8")
        for needle in ("--dry-run-only", "--namespace", "BLOCKED_NO_SAFE_CLUSTER"):
            if needle not in src:
                bad(f"runner missing {needle}")
        for guard in ("forbidden namespace", "production substring", "Ingress", "LoadBalancer"):
            if guard not in src:
                bad(f"runner missing guardrail: {guard}")
        if "argocd" not in src.lower():
            bad("runner does not reference argocd guardrail")
        if not failures:
            print("  [OK] runner has dry-run, namespace + production guardrails, no ingress/LB")

    if not VALUES.is_file():
        bad("missing values-nonprod-smoke.yaml")
    else:
        v = yaml.safe_load(VALUES.read_text(encoding="utf-8")) or {}
        g = v.get("global", {})
        integ = v.get("platform", {}).get("integrations", {})
        ac = v.get("platform", {}).get("adminConsole", {})
        if g.get("production") is not False or g.get("realDeployEnabled") is not False:
            bad("smoke values must set production=false, realDeployEnabled=false")
        if ac.get("productionAuthEnabled") is not False or ac.get("oidcEnabled") is not False:
            bad("smoke values must disable production auth + OIDC")
        if any(
            integ.get(k)
            for k in ("githubWrite", "prCreation", "deployment", "realLlm", "externalDelivery")
        ):
            bad("smoke values must disable github/pr/deploy/realLlm/externalDelivery")
        if not [f for f in failures if "smoke values" in f]:
            print("  [OK] smoke values disable production / auth / integrations")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] guardrails valid but no safe cluster to render/install ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe cluster present: PASS requires evidence of a REAL successful install --
    # the live smoke report with pods Running (produced by run_nonproduction_runtime_smoke.py).
    pods = section_status("podStatus")
    if pods is None:
        print("  [BLOCKED] safe cluster but no install evidence (run the bootstrap + helm smoke)")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    if pods == "pass":
        print("  [OK] non-production release installed; pods Running per the live smoke report")
        print(f"{MARKER}: PASS")
        return 0
    print(f"  [FAIL] release installed but pods not healthy (podStatus={pods})")
    print(f"{MARKER}: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
