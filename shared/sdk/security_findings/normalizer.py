"""Step 54.2 -- security scan result normalization.

Merges secret / SAST / dependency ScanResults into one redacted summary with a
unified severity rollup and production-readiness verdict. A missing or
tool_unavailable scan is NEVER treated as clean; production readiness is never
true at this stage.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.security_findings.models import FindingsSummary, ScanResult

SCAN_TYPES = ("secret", "sast", "dependency")


def _status_for(result: ScanResult | None) -> str:
    if result is None:
        return "not_run"
    if result.status == "passed":
        return "completed_no_findings"
    if result.status == "completed_with_findings":
        return "completed_with_findings"
    if result.status == "tool_unavailable":
        return "tool_unavailable"
    if result.status == "config_error":
        return "failed"
    return "failed"


def normalize(results: dict[str, ScanResult | None]) -> dict[str, Any]:
    """Build a unified, redacted summary across scan types."""
    per_type: dict[str, Any] = {}
    totals = FindingsSummary()
    limitations: list[str] = []
    production_blocker = False
    requires_approval = False
    not_ready_reasons: list[str] = []

    for st in SCAN_TYPES:
        r = results.get(st)
        status = _status_for(r)
        per_type[st] = {
            "status": status,
            "scanner": r.scanner if r else "",
            "findings_summary": (
                r.findings_summary.model_dump() if r else FindingsSummary().model_dump()
            ),
            "limitations": list(r.limitations) if r else ["scan_not_run"],
        }
        if r is None or status in ("tool_unavailable", "not_run", "failed"):
            not_ready_reasons.append(f"{st}_{status}")
        if r is not None:
            for sev in ("critical", "high", "medium", "low", "informational"):
                setattr(totals, sev, getattr(totals, sev) + getattr(r.findings_summary, sev))
            limitations += r.limitations
            for f in r.findings:
                production_blocker = production_blocker or f.production_blocker
                requires_approval = requires_approval or f.requires_approval

    if totals.critical > 0:
        not_ready_reasons.append("critical_findings_present")
    if totals.high > 0:
        not_ready_reasons.append("high_findings_present")

    # Standing non-production reasons: this is a LOCAL baseline. Even when every
    # local scan completes cleanly, production readiness still requires an
    # external CVE scan, an SBOM (Step 54.3), and a production gate (Step 54.4).
    not_ready_reasons.append("local_baseline_external_cve_scan_not_performed")
    not_ready_reasons.append("sbom_not_generated_deferred_step_54_3")
    not_ready_reasons.append("production_security_gate_not_enabled")
    for lim in limitations:
        if "lockfile_missing" in lim or "no_cve_lookup" in lim:
            not_ready_reasons.append(lim)

    return {
        "schema_version": "1",
        "scan_types": list(SCAN_TYPES),
        "per_type": per_type,
        "totals": totals.model_dump(),
        "production_blocker": production_blocker,
        "requires_approval": requires_approval,
        "production_ready": False,
        "not_ready_reasons": sorted(set(not_ready_reasons)),
        "limitations": sorted(set(limitations)),
    }


__all__ = ["normalize", "SCAN_TYPES"]
