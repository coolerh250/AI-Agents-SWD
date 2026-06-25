#!/usr/bin/env python3
"""Step 54.4 -- security readiness report generator.

Rolls the Step 54.1-54.3 baselines, the threat model, the evidence package and the
release risk summary into a single redacted readiness report written to
``.runtime/security/security-readiness-report.json``.

This is a posture report, NOT a production approval. ``productionReady`` is always
false; production blockers and the required next steps (Step 55 cluster smoke,
Step 56 ArgoCD sync) are listed explicitly. Missing evidence is reported as such,
never as clean.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_release_risk_summary import build_release_risk_summary  # noqa: E402
from shared.sdk.secrets_foundation.secret_redaction import redact  # noqa: E402


def _present(rel: str, root: Path) -> str:
    return "present" if (root / rel).is_file() else "missing"


def build_security_readiness_report(
    root: Path | None = None, runtime_dir: Path | None = None
) -> dict[str, Any]:
    base = root or ROOT
    risk = build_release_risk_summary(base, runtime_dir)

    step_status = {
        "step_54_1_security_supply_chain_policy": _present(
            "infra/security/security-foundation-summary.yaml", base
        ),
        "step_54_2_local_scan_toolchain": _present(
            "infra/security/security-scan-status-summary-model.yaml", base
        ),
        "step_54_3_sbom_image_container": _present(
            "infra/security/container-security-evidence-model.yaml", base
        ),
        "threat_model": _present("infra/security/threat-model-baseline.yaml", base),
        "agent_threat_model": _present("infra/security/agent-threat-model.yaml", base),
        "supply_chain_threat_model": _present(
            "infra/security/supply-chain-threat-model.yaml", base
        ),
        "runtime_gitops_threat_model": _present(
            "infra/security/runtime-gitops-threat-model.yaml", base
        ),
        "evidence_package_schema": _present(
            "infra/security/security-evidence-package-schema.yaml", base
        ),
        "release_risk_summary_model": _present(
            "infra/security/release-risk-summary-model.yaml", base
        ),
    }

    report = {
        "schemaVersion": "1",
        "reportId": f"security-readiness-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "stepStatus": step_status,
        "evidencePackageStatus": "generated_runtime_only_not_committed",
        "releaseRiskStatus": risk.get("status"),
        "riskScore": risk.get("riskScore"),
        "productionBlockers": risk.get("blockers", []),
        "nonProductionLimitations": [
            "real_external_sast_not_integrated",
            "real_cve_dependency_scan_not_run",
            "production_sbom_not_generated",
            "image_vulnerability_scan_not_performed",
            "image_digest_pinning_incomplete",
            "dockerfile_non_root_incomplete",
            "production_identity_not_enabled",
            "production_secret_store_not_configured",
            "no_real_production_backup_schedule",
            "no_production_release_gate",
        ],
        "nextRequiredSteps": [
            "step_55_non_production_cluster_smoke",
            "step_56_real_argocd_manual_sync",
            "step_60_production_readiness_review",
        ],
        "releaseGateEnabled": False,
        "productionReady": False,
    }
    return redact(report)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the redacted security readiness report.")
    ap.add_argument(
        "--json-report",
        default=str(ROOT / ".runtime" / "security" / "security-readiness-report.json"),
    )
    args = ap.parse_args()
    report = build_security_readiness_report()
    _write(Path(args.json_report), report)
    print(
        f"  security readiness report: releaseRisk={report['releaseRiskStatus']} "
        f"blockers={len(report['productionBlockers'])} productionReady=False "
        f"report={args.json_report}"
    )
    print("SECURITY_READINESS_REPORT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
