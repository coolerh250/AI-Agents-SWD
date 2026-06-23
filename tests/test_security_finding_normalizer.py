"""Step 54.2 -- finding normalizer rollup + not-clean semantics."""

from __future__ import annotations

from shared.sdk.security_findings import (
    FindingsSummary,
    ScanResult,
    SecurityFinding,
    make_finding_id,
    normalize,
)


def _result(status: str, findings: list[SecurityFinding] | None = None) -> ScanResult:
    fs = findings or []
    return ScanResult(
        scan_type="secret",
        scanner="x",
        status=status,
        findings=fs,
        findings_summary=FindingsSummary.from_findings(fs),
    )


def test_missing_scan_is_not_clean() -> None:
    out = normalize({"secret": None, "sast": None, "dependency": None})
    assert out["per_type"]["secret"]["status"] == "not_run"
    assert "secret_not_run" in out["not_ready_reasons"]
    assert out["production_ready"] is False


def test_tool_unavailable_preserved() -> None:
    r = ScanResult(scan_type="sast", scanner="bandit", status="tool_unavailable")
    out = normalize({"secret": None, "sast": r, "dependency": None})
    assert out["per_type"]["sast"]["status"] == "tool_unavailable"


def test_critical_rolls_up_and_blocks() -> None:
    crit = SecurityFinding(
        finding_id=make_finding_id("x", "secret", "r", "p", 1),
        scanner="x",
        category="secret",
        severity="critical",
        title="t",
        production_blocker=True,
    )
    out = normalize(
        {"secret": _result("completed_with_findings", [crit]), "sast": None, "dependency": None}
    )
    assert out["totals"]["critical"] == 1
    assert out["production_blocker"] is True
    assert "critical_findings_present" in out["not_ready_reasons"]


def test_standing_non_production_reasons() -> None:
    out = normalize(
        {"secret": _result("passed"), "sast": _result("passed"), "dependency": _result("passed")}
    )
    assert out["production_ready"] is False
    assert "sbom_not_generated_deferred_step_54_3" in out["not_ready_reasons"]
    assert "production_security_gate_not_enabled" in out["not_ready_reasons"]
