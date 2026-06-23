#!/usr/bin/env python3
"""Step 54.2 -- local dependency scan baseline (local-only, no network).

Inspects local manifests / lockfiles ONLY. It does NOT query an external CVE
database. pip-audit / npm-audit / osv-scanner are network-dependent and reported
as tool_unavailable / network_required when absent -- a missing CVE lookup is
NEVER reported as clean. Produces manifest-policy findings (missing lockfile,
unpinned deps). Output redacted, written to a runtime path (NEVER committed).

Exit: 0 = completed (findings recorded, non-gating); 2 = config error.

Usage: python scripts/run_local_dependency_scan.py [--json-report PATH] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from shared.sdk.security_findings import (  # noqa: E402
    FindingsSummary,
    ScanResult,
    ScanStatus,
    SecurityFinding,
    make_finding_id,
    redact_report,
)

SCANNER = "custom_dependency_inventory_check"
DEFAULT_REPORT = ROOT / ".runtime" / "security" / "dependency-scan-report.json"
_PIN = re.compile(r"(==|>=|<=|~=|@|;)")  # a line that pins / constrains a version


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(name: str) -> dict:
    p = ROOT / "infra" / "security" / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {}


def _finding(rule_id: str, sev: str, title: str, path: str | None, rem: str) -> SecurityFinding:
    return SecurityFinding(
        finding_id=make_finding_id(SCANNER, "dependency", rule_id, path, None),
        scanner=SCANNER,
        category="dependency",
        severity=sev,  # type: ignore[arg-type]
        title=title,
        description=rule_id,
        file_path=path,
        rule_id=rule_id,
        remediation=rem,
        production_blocker=False,
        requires_approval=sev in ("high", "medium"),
    )


def run() -> ScanResult:
    pkg = _load_yaml("scan-target-catalog.yaml").get("targets", {}).get("dependencyScan", {})
    package_files = pkg.get("packageFiles", [])
    if not package_files:
        return ScanResult(
            scan_type="dependency",
            scanner=SCANNER,
            status="config_error",
            limitations=["scan-target-catalog dependencyScan.packageFiles missing"],
        )

    findings: list[SecurityFinding] = []
    # Python: requirements.txt files + lockfile presence
    req_files = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("requirements.txt")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    )
    py_lock = any((ROOT / f).exists() for f in ("requirements.lock", "poetry.lock", "Pipfile.lock"))
    unpinned = []
    for rf in req_files:
        text = (ROOT / rf).read_text(encoding="utf-8", errors="ignore")
        has_pin = any(
            _PIN.search(ln)
            for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
        if not has_pin:
            unpinned.append(rf)
    if req_files and not py_lock:
        findings.append(
            _finding(
                "DEP-PY-NO-LOCKFILE",
                "medium",
                f"no Python lockfile across {len(req_files)} requirements files",
                "requirements.txt",
                "add a hash-pinned lockfile (pip-compile/poetry)",
            )
        )
    for rf in unpinned:
        findings.append(
            _finding(
                "DEP-PY-UNPINNED",
                "low",
                "unpinned Python dependencies",
                rf,
                "pin versions or add a lockfile",
            )
        )

    # Node: package-lock.json presence
    node_pkg = (ROOT / "apps" / "admin-console" / "package.json").exists()
    node_lock = (ROOT / "apps" / "admin-console" / "package-lock.json").exists()
    if node_pkg and not node_lock:
        findings.append(
            _finding(
                "DEP-NODE-NO-LOCKFILE",
                "medium",
                "node package-lock.json missing",
                "apps/admin-console/package.json",
                "commit package-lock.json",
            )
        )

    limitations = ["no_cve_lookup_performed_manifest_policy_only"]
    for tool, label in (
        ("pip-audit", "pip_audit"),
        ("osv-scanner", "osv_scanner"),
        ("npm", "npm_audit"),
    ):
        if shutil.which(tool) is None:
            limitations.append(f"{label}_unavailable")
        else:
            limitations.append(f"{label}_present_but_network_required_not_run")
    if not py_lock:
        limitations.append("python_lockfile_missing")
    limitations.append("node_lockfile_present" if node_lock else "node_lockfile_missing")

    status: ScanStatus = "completed_with_findings" if findings else "passed"
    return ScanResult(
        scan_type="dependency",
        scanner=SCANNER,
        status=status,
        started_at=_now(),
        finished_at=_now(),
        targets=package_files,
        findings_summary=FindingsSummary.from_findings(findings),
        findings=findings,
        limitations=limitations,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-report", default=str(DEFAULT_REPORT))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        result = run()
    except Exception as exc:  # noqa: BLE001
        _write(
            args.json_report,
            {
                "scan_type": "dependency",
                "scanner": SCANNER,
                "status": "config_error",
                "error": exc.__class__.__name__,
                "production_ready": False,
            },
        )
        print("LOCAL_DEPENDENCY_SCAN: config_error")
        return 2
    _write(args.json_report, redact_report(result.model_dump()))
    s = result.findings_summary
    if not args.quiet:
        print(
            f"dependency status={result.status} medium={s.medium} low={s.low} "
            f"report={args.json_report}"
        )
    return 2 if result.status == "config_error" else 0


def _write(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
