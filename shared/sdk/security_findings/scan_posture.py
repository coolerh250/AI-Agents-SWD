"""Step 54.2 -- read-only scan posture loaders + safety fields.

Reads the COMMITTED infra/security scan models and (optionally) the latest
redacted runtime summary under ``.runtime/security/``. The runtime summary is
NEVER committed and is absent in the orchestrator image, so live views degrade to
``not_run`` -- never a fake clean/PASS. No scanner is run here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SUMMARY = "security-scan-summary.json"

_MODELS = {
    "capabilities": "local-scanner-capability-inventory.yaml",
    "boundary": "scanner-execution-boundary.yaml",
    "targets": "scan-target-catalog.yaml",
    "exclusions": "scan-exclusion-policy.yaml",
    "result_schema": "scan-result-artifact-schema.yaml",
    "status_model": "security-scan-status-summary-model.yaml",
}


def _load_yaml(name: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "security" / name
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def section(name: str, root: Path | None = None) -> dict[str, Any]:
    return redact(_load_yaml(name, root))


def load_status_model(root: Path | None = None) -> dict[str, Any]:
    return _load_yaml(_MODELS["status_model"], root)


def load_runtime_summary(runtime_dir: Path | None = None) -> dict[str, Any] | None:
    base = runtime_dir or (ROOT / ".runtime" / "security")
    p = base / RUNTIME_SUMMARY
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return redact(data) if isinstance(data, dict) else None


def _cfg(v: Any) -> Any:
    return True if v == "configured" else v


def scan_safety_fields(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    model = load_status_model(root)
    bc = model.get("baselineConfiguration", {})
    summary = load_runtime_summary(runtime_dir)
    per = (summary or {}).get("per_type", {})

    def last(scan_type: str) -> str:
        if not summary:
            return "not_run"
        return per.get(scan_type, {}).get("status", "not_run")

    return {
        "security_local_scan_baseline_enabled": bool(bc.get("localScanBaselineEnabled")),
        "security_local_secret_scan_configured": _cfg(
            bc.get("secretScanConfigured", "not_configured")
        ),
        "security_local_sast_configured": _cfg(bc.get("sastConfigured", "not_configured")),
        "security_local_dependency_scan_configured": _cfg(
            bc.get("dependencyScanConfigured", "not_configured")
        ),
        "security_scan_external_upload_enabled": bool(bc.get("externalUploadEnabled")),
        "security_scan_network_enabled": bool(bc.get("networkEnabled")),
        "security_scan_token_required": bool(bc.get("tokenRequired")),
        "security_scan_run_endpoint_enabled": bool(bc.get("runEndpointEnabled")),
        "security_scan_result_normalization_enabled": bool(bc.get("resultNormalizationEnabled")),
        "security_scan_reports_committed": bool(bc.get("reportsCommitted")),
        "security_scan_production_gate_enabled": bool(bc.get("productionGateEnabled")),
        "security_scan_production_ready": False,
        "security_secret_scan_last_status": last("secret"),
        "security_sast_last_status": last("sast"),
        "security_dependency_scan_last_status": last("dependency"),
    }


def status_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    model = load_status_model(root)
    summary = load_runtime_summary(runtime_dir)
    per = (summary or {}).get("per_type", {})
    return {
        "baselineConfiguration": model.get("baselineConfiguration", {}),
        "statusEnum": model.get("statusEnum", []),
        "secret": per.get("secret", {"status": "not_run"}),
        "sast": per.get("sast", {"status": "not_run"}),
        "dependency": per.get("dependency", {"status": "not_run"}),
        "productionReady": False,
    }


def summary_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    summary = load_runtime_summary(runtime_dir)
    if summary is None:
        return {
            "status": "not_run",
            "productionReady": False,
            "scan_types": ["secret", "sast", "dependency"],
        }
    summary["productionReady"] = False
    return summary


def readiness_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    summary = load_runtime_summary(runtime_dir)
    if summary is None:
        return {
            "status": "not_run",
            "productionReady": False,
            "productionGateEnabled": False,
            "blockers": ["scans_not_run_in_this_environment"],
        }
    return {
        "status": "evaluated",
        "productionReady": False,
        "productionGateEnabled": False,
        "blockers": summary.get("not_ready_reasons", []),
    }


def scan_section(scan_type: str, runtime_dir: Path | None = None) -> dict[str, Any]:
    summary = load_runtime_summary(runtime_dir)
    if summary is None:
        return {"status": "not_run", "productionReady": False, "scan_type": scan_type}
    return summary.get("per_type", {}).get(scan_type, {"status": "not_run", "scan_type": scan_type})


__all__ = [
    "section",
    "load_status_model",
    "load_runtime_summary",
    "scan_safety_fields",
    "status_view",
    "summary_view",
    "readiness_view",
    "scan_section",
]
