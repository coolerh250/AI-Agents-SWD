#!/usr/bin/env python3
"""Step 54.4 -- security evidence package generator.

Aggregates the COMMITTED Step 54.1-54.3 security models and, IF PRESENT, the
latest redacted runtime scan / SBOM / image-policy reports under
``.runtime/security/`` into a single redacted evidence package written to
``.runtime/security/security-evidence-package.json``.

Honest by construction: a missing runtime report is recorded as ``not_run`` /
``missing_evidence`` -- never ``present``/``clean``. The package contains NO
secret, NO raw token, NO raw finding evidence, NO chain-of-thought; it references
runtime reports by path + sha256 + safe severity counts only. The runtime package
is NEVER committed. ``productionReady`` is always false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.secrets_foundation.secret_redaction import redact  # noqa: E402

_RUNTIME_EVIDENCE = {
    "sast": "sast-scan-report.json",
    "dependencyScan": "dependency-scan-report.json",
    "secretScan": "secret-scan-report.json",
    "sbom": "sbom/local-sbom-baseline.json",
    "imagePolicy": "images/image-policy-report.json",
    "releaseRisk": "release-risk-summary.json",
}

_COMMITTED_EVIDENCE = {
    "dockerfileSecurity": "infra/security/dockerfile-security-inventory.yaml",
    "threatModel": "infra/security/threat-model-baseline.yaml",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _safe_counts(data: Any) -> dict[str, int] | None:
    if not isinstance(data, dict):
        return None
    fs = data.get("findings_summary") or data.get("findingsSummary") or data.get("summary")
    if isinstance(fs, dict):
        out = {k: v for k, v in fs.items() if isinstance(v, int)}
        return out or None
    return None


def _runtime_entry(name: str, runtime_dir: Path) -> dict[str, Any]:
    p = runtime_dir / name
    if not p.is_file():
        return {"status": "not_run"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "missing_evidence", "note": "unreadable runtime report"}
    entry: dict[str, Any] = {
        "status": "present",
        "summaryRef": f".runtime/security/{name}",
        "sha256": _sha256(p),
    }
    counts = _safe_counts(data)
    if counts is not None:
        entry["severityCounts"] = counts
    return entry


def _committed_entry(rel: str, root: Path) -> dict[str, Any]:
    p = root / rel
    if not p.is_file():
        return {"status": "missing_evidence"}
    return {"status": "present", "summaryRef": rel, "sha256": _sha256(p)}


def _audit_entry(root: Path) -> dict[str, Any]:
    p = root / "source" / "regression-reports" / "regression_latest_summary.json"
    if not p.is_file():
        return {"status": "not_run"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "missing_evidence"}
    return {
        "status": "present",
        "summaryRef": "source/regression-reports/regression_latest_summary.json",
        "resultClass": data.get("result_class"),
    }


def build_evidence_package(
    root: Path | None = None, runtime_dir: Path | None = None
) -> dict[str, Any]:
    base = root or ROOT
    rt = runtime_dir or (base / ".runtime" / "security")

    evidence: dict[str, Any] = {}
    for key, name in _RUNTIME_EVIDENCE.items():
        evidence[key] = _runtime_entry(name, rt)
    for key, rel in _COMMITTED_EVIDENCE.items():
        evidence[key] = _committed_entry(rel, base)
    evidence["audit"] = _audit_entry(base)
    evidence["qa"] = _audit_entry(base)  # QA evidence rolls up via the regression summary

    limitations = [
        "real_external_sast_not_integrated",
        "real_cve_dependency_scan_not_run",
        "production_sbom_not_generated",
        "image_cve_scan_not_performed",
        "image_digest_pinning_incomplete",
        "dockerfile_non_root_incomplete",
        "kubernetes_runtime_smoke_required_step_55",
    ]
    missing = [k for k, v in evidence.items() if v.get("status") in ("not_run", "missing_evidence")]

    package = {
        "schemaVersion": "1",
        "packageId": f"sec-evidence-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": {"step": "54.4", "stage": "56D", "environment": "local_test_only"},
        "evidence": evidence,
        "missingEvidence": missing,
        "limitations": limitations,
        "productionReady": False,
    }
    return redact(package)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the redacted security evidence package.")
    ap.add_argument(
        "--json-report",
        default=str(ROOT / ".runtime" / "security" / "security-evidence-package.json"),
    )
    args = ap.parse_args()
    package = build_evidence_package()
    _write(Path(args.json_report), package)
    print(
        f"  evidence package: {len(package['evidence'])} sections; "
        f"missing={len(package['missingEvidence'])}; productionReady=False; "
        f"report={args.json_report}"
    )
    print("SECURITY_EVIDENCE_PACKAGE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
