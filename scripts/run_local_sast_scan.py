#!/usr/bin/env python3
"""Step 54.2 -- local SAST baseline runner (local-only, no network, no token).

Runs bounded custom static checks for unsafe patterns over allowlisted targets.
If bandit/semgrep are available they MAY be detected, but the bundled baseline is
custom_static_checks (a LIMITED baseline, NOT a full SAST engine). Output is
redacted, normalized, and written to a runtime path (NEVER committed).

Exit: 0 = completed (findings recorded, non-gating); 2 = config error.

Usage: python scripts/run_local_sast_scan.py [--json-report PATH] [--quiet]
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

SCANNER = "custom_static_checks"
DEFAULT_REPORT = ROOT / ".runtime" / "security" / "sast-scan-report.json"
SECURITY_MODULE_HINTS = (
    "identity",
    "secrets_foundation",
    "security_foundation",
    "security_findings",
    "operator_actions",
    "audit",
)

# (rule_id, severity, regex, message)
# NB: messages are deliberately free of the literal trigger strings so the
# scanner does not self-flag its own rule definitions.
RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    ("PY-EVAL", "high", re.compile(r"\beval\s*\("), "use of the eval builtin"),
    ("PY-EXEC", "high", re.compile(r"(?<![._])\bexec\s*\("), "use of the exec builtin"),
    ("PY-SHELL-TRUE", "high", re.compile(r"shell\s*=\s*True"), "subprocess invoked via a shell"),
    (
        "PY-YAML-LOAD",
        "high",
        re.compile(r"\byaml\.load\s*\((?!.*Loader=)"),
        "unsafe YAML load without SafeLoader",
    ),
    (
        "PY-TLS-VERIFY-OFF",
        "high",
        re.compile(r"verify\s*=\s*False"),
        "TLS certificate verification disabled",
    ),
    (
        "PY-SUBPROCESS",
        "low",
        re.compile(r"\bsubprocess\.(run|call|Popen|check_output|check_call)\s*\("),
        "subprocess usage (review for injection)",
    ),
    ("PY-BIND-ALL", "low", re.compile(r"0\.0\.0\.0"), "bind to all network interfaces"),
    (
        "PY-TODO-BYPASS",
        "medium",
        re.compile(r"TODO.*(prod|bypass|disable.*(security|auth)|skip.*auth)", re.IGNORECASE),
        "production-bypass marker comment",
    ),
]
BROAD_EXCEPT = re.compile(r"except\s*(Exception)?\s*:")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(name: str) -> dict:
    p = ROOT / "infra" / "security" / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {}


def scan_text(text: str, rel: str) -> list[SecurityFinding]:
    """Run the custom static checks over one file's text. Reusable by verifiers."""
    out: list[SecurityFinding] = []
    is_sec_module = any(h in rel for h in SECURITY_MODULE_HINTS)
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for rule_id, sev, pat, msg in RULES:
            if pat.search(line):
                out.append(_finding(rule_id, sev, msg, rel, i, line))
        if is_sec_module and BROAD_EXCEPT.search(line):
            nxt = lines[i].strip() if i < len(lines) else ""
            if nxt in ("pass", "..."):
                out.append(
                    _finding(
                        "PY-BROAD-EXCEPT",
                        "medium",
                        "broad exception swallowed in security module",
                        rel,
                        i,
                        line,
                    )
                )
    return out


def _finding(
    rule_id: str, sev: str, msg: str, rel: str, line: int, evidence: str
) -> SecurityFinding:
    blocker = sev in ("critical", "high")
    return SecurityFinding(
        finding_id=make_finding_id(SCANNER, "sast", rule_id, rel, line),
        scanner=SCANNER,
        category="sast",
        severity=sev,  # type: ignore[arg-type]
        title=msg,
        description=rule_id,
        file_path=rel,
        line=line,
        rule_id=rule_id,
        evidence_redacted=evidence,
        remediation="review and apply a safe alternative",
        production_blocker=blocker,
        requires_approval=sev in ("high", "medium"),
    )


def _iter_py(include: list[str], exclude: list[str]):
    for inc in include:
        base = ROOT / inc
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if any(rel.startswith(f"{ex}/") or f"/{ex}/" in f"/{rel}" for ex in exclude):
                continue
            yield p, rel


def run() -> ScanResult:
    targets = _load_yaml("scan-target-catalog.yaml").get("targets", {}).get("sast", {})
    include = targets.get("include", [])
    exclude = targets.get("exclude", [])
    if not include:
        return ScanResult(
            scan_type="sast",
            scanner=SCANNER,
            status="config_error",
            limitations=["scan-target-catalog sast.include missing"],
        )
    findings: list[SecurityFinding] = []
    for p, rel in _iter_py(include, exclude):
        try:
            findings += scan_text(p.read_text(encoding="utf-8", errors="ignore"), rel)
        except OSError:
            continue
    limitations = [
        "custom_static_checks_is_a_limited_baseline_not_a_full_sast_engine",
        "no_dataflow_or_taint_analysis",
    ]
    for ext in ("bandit", "semgrep"):
        if shutil.which(ext) is None:
            limitations.append(f"{ext}_not_available_runtime_detected")
    status: ScanStatus = "completed_with_findings" if findings else "passed"
    return ScanResult(
        scan_type="sast",
        scanner=SCANNER,
        status=status,
        started_at=_now(),
        finished_at=_now(),
        targets=include,
        excluded_targets=exclude,
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
                "scan_type": "sast",
                "scanner": SCANNER,
                "status": "config_error",
                "error": exc.__class__.__name__,
                "production_ready": False,
            },
        )
        print("LOCAL_SAST: config_error")
        return 2
    _write(args.json_report, redact_report(result.model_dump()))
    s = result.findings_summary
    if not args.quiet:
        print(
            f"sast status={result.status} critical={s.critical} high={s.high} "
            f"medium={s.medium} low={s.low} report={args.json_report}"
        )
    return 2 if result.status == "config_error" else 0


def _write(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
