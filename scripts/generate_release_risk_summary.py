#!/usr/bin/env python3
"""Step 54.4 -- release risk summary generator.

Aggregates the security evidence package + release-risk scoring policy + the
documented Step 51/52/53/54.1-54.3 readiness facts into a redacted release risk
summary written to ``.runtime/security/release-risk-summary.json``.

A summary is NEVER a production approval or a deployment approval. The status enum
excludes ``production_ready`` / ``production_approved``. Missing required evidence
or production identity/secret/runtime not ready -> ``not_ready``. A confirmed
secret leak or a critical finding -> ``blocked``. ``productionReady`` is always
false; the production gate is never enabled here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_security_evidence_package import build_evidence_package  # noqa: E402
from shared.sdk.secrets_foundation.secret_redaction import redact  # noqa: E402

_ALLOWED_STATUS = {
    "not_ready",
    "ready_for_non_production_review",
    "ready_for_operator_review",
    "blocked",
}


def _load_yaml(rel: str, root: Path) -> dict[str, Any]:
    p = root / rel
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _counts(entry: dict[str, Any]) -> dict[str, int]:
    return entry.get("severityCounts", {}) if isinstance(entry, dict) else {}


def build_release_risk_summary(
    root: Path | None = None, runtime_dir: Path | None = None
) -> dict[str, Any]:
    base = root or ROOT
    rt = runtime_dir or (base / ".runtime" / "security")

    pkg_path = rt / "security-evidence-package.json"
    if pkg_path.is_file():
        try:
            package = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            package = build_evidence_package(base, rt)
    else:
        package = build_evidence_package(base, rt)

    scoring = _load_yaml("infra/security/release-risk-scoring-policy.yaml", base).get(
        "riskScoring", {}
    )
    weights = scoring.get("severityWeights", {"critical": 100, "high": 40, "medium": 15, "low": 5})
    evidence = package.get("evidence", {})

    # Aggregate severity counts from any present scan/policy evidence.
    agg = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for key in ("secretScan", "sast", "dependencyScan", "imagePolicy"):
        for sev, n in _counts(evidence.get(key, {})).items():
            if sev in agg and isinstance(n, int):
                agg[sev] += n

    secret_counts = _counts(evidence.get("secretScan", {}))
    confirmed_secret_leak = int(secret_counts.get("critical", 0)) > 0
    critical_finding = agg["critical"] > 0

    score = min(
        100,
        agg["critical"] * int(weights.get("critical", 100))
        + agg["high"] * int(weights.get("high", 40))
        + agg["medium"] * int(weights.get("medium", 15))
        + agg["low"] * int(weights.get("low", 5)),
    )

    # Documented (modeled) readiness facts -- none is production-ready yet.
    readiness = {
        "identityReadiness": "not_ready_production_auth_disabled",
        "secretReadiness": "not_ready_production_store_disabled",
        "runtimeReadiness": "not_validated_cluster_smoke_required_step_55",
        "backupReadiness": "non_production_baseline_only",
        "rollbackReadiness": "modeled_not_validated",
    }

    blockers: list[str] = []
    if confirmed_secret_leak:
        blockers.append("confirmed_secret_leak")
    if critical_finding:
        blockers.append("critical_finding")
    if evidence.get("sbom", {}).get("status") != "present":
        blockers.append("sbom_evidence_missing")
    if evidence.get("threatModel", {}).get("status") != "present":
        blockers.append("threat_model_missing")
    # Image digest pinning is incomplete by Step 54.3 baseline.
    blockers.append("image_digest_pinning_incomplete")
    blockers.append("production_identity_not_ready")
    blockers.append("production_secret_store_not_ready")
    blockers.append("runtime_not_validated")

    missing_evidence = list(package.get("missingEvidence", []))

    if confirmed_secret_leak or critical_finding:
        status = "blocked"
    else:
        # Required production evidence is incomplete this stage -> not_ready.
        status = "not_ready"

    summary = {
        "schemaVersion": "1",
        "summaryId": f"release-risk-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "riskScore": score,
        "scoreIsNotApproval": True,
        "severityTotals": agg,
        "missingEvidence": missing_evidence,
        "criticalBlockers": [
            b for b in blockers if b in ("confirmed_secret_leak", "critical_finding")
        ],
        "blockers": blockers,
        "readiness": readiness,
        "evidencePackageRef": ".runtime/security/security-evidence-package.json",
        "productionApproval": False,
        "deploymentApproval": False,
        "productionReady": False,
    }
    assert summary["status"] in _ALLOWED_STATUS
    return redact(summary)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the redacted release risk summary.")
    ap.add_argument(
        "--json-report",
        default=str(ROOT / ".runtime" / "security" / "release-risk-summary.json"),
    )
    args = ap.parse_args()
    summary = build_release_risk_summary()
    _write(Path(args.json_report), summary)
    print(
        f"  release risk summary: status={summary['status']} score={summary['riskScore']} "
        f"blockers={len(summary['blockers'])} productionReady=False report={args.json_report}"
    )
    print("RELEASE_RISK_SUMMARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
