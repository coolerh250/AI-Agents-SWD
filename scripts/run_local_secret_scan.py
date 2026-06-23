#!/usr/bin/env python3
"""Step 54.2 -- local secret scan runner (local-only, no network, no token).

Scans allowlisted targets (from scan-target-catalog.yaml) for committed inline
secret/token shapes using the Step 53 detector. Matches in reviewed intentional
fixtures (scan-exclusion-policy.yaml `secretFixtureClassification`) are reported
as `informational`; matches anywhere else are confirmed `critical`. Output is
redacted and written to a runtime path (NEVER committed).

Exit: 0 = no confirmed finding; 1 = confirmed finding / policy violation;
      2 = scanner unavailable / config error.

Usage: python scripts/run_local_secret_scan.py [--json-report PATH] [--quiet]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from shared.sdk.secrets_foundation.secret_redaction import find_committed_secret  # noqa: E402
from shared.sdk.security_findings import (  # noqa: E402
    FindingsSummary,
    ScanResult,
    ScanStatus,
    SecurityFinding,
    make_finding_id,
    redact_report,
)

SCANNER = "custom_repo_secret_scan"
DEFAULT_REPORT = ROOT / ".runtime" / "security" / "secret-scan-report.json"

# High-confidence credential shapes -> confirmed critical (outside reviewed
# fixtures). Keyword/format heuristics (guid, secret_literal, bearer_token,
# webhook_url, email, real_idp_issuer) are surfaced as low-confidence review items
# only -- a bare GUID or a `secret`-named variable is not a confirmed leak. Strict
# committed-secret prevention remains enforced by Step 53 SECRET_NO_INLINE_VALUES.
HIGH_CONFIDENCE = {
    "github_token",
    "openai_key",
    "aws_key",
    "jwt",
    "private_key",
    "kubeconfig",
    "db_url_with_password",
    "service_account_token",
}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".sh",
    ".env",
    ".cfg",
    ".ini",
    ".toml",
    ".txt",
    ".sql",
    ".html",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(name: str) -> dict:
    p = ROOT / "infra" / "security" / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {}


def _fixture_globs() -> list[str]:
    pol = _load_yaml("scan-exclusion-policy.yaml").get("exclusionPolicy", {})
    return pol.get("secretFixtureClassification", {}).get("globs", [])


def _is_fixture(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def _iter_files(include: list[str], exclude: list[str]):
    for inc in include:
        base = ROOT / inc
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(f"/{ex}/" in f"/{rel}/" or rel.startswith(f"{ex}/") for ex in exclude):
                continue
            yield p, rel


def run() -> ScanResult:
    targets = _load_yaml("scan-target-catalog.yaml").get("targets", {}).get("secretScan", {})
    include = targets.get("include", [])
    exclude = targets.get("exclude", [])
    if not include:
        return ScanResult(
            scan_type="secret",
            scanner=SCANNER,
            status="config_error",
            limitations=["scan-target-catalog secretScan.include missing"],
        )
    globs = _fixture_globs()
    findings: list[SecurityFinding] = []
    for p, rel in _iter_files(include, exclude):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ln_no, line in enumerate(text.splitlines(), start=1):
            reasons = find_committed_secret(line)
            if not reasons:
                continue
            label = reasons[0].split(":")[0]
            if _is_fixture(rel, globs):
                sev, blocker, title, rem = (
                    "informational",
                    False,
                    "intentional secret-shaped fixture/detector pattern (not a real secret)",
                    "verify no real secret; allowlisted as intentional fixture",
                )
            elif label in HIGH_CONFIDENCE:
                sev, blocker, title, rem = (
                    "critical",
                    True,
                    "committed secret-shaped value detected",
                    "remove the secret and rotate it; use a SecretRef",
                )
            else:
                sev, blocker, title, rem = (
                    "low",
                    False,
                    "low-confidence secret heuristic match (review)",
                    "review; keyword/format heuristic, not a confirmed credential",
                )
            findings.append(
                SecurityFinding(
                    finding_id=make_finding_id(SCANNER, "secret", label, rel, ln_no),
                    scanner=SCANNER,
                    category="secret",
                    severity=sev,  # type: ignore[arg-type]
                    title=title,
                    description=label,
                    file_path=rel,
                    line=ln_no,
                    rule_id=label,
                    evidence_redacted=line,
                    remediation=rem,
                    production_blocker=blocker,
                    requires_approval=False,
                )
            )
    confirmed = [f for f in findings if f.production_blocker]
    status: ScanStatus = "completed_with_findings" if findings else "passed"
    limitations = ["custom_baseline_only_not_a_full_secret_scanner"]
    if confirmed:
        limitations.append("confirmed_secret_findings_present")
    return ScanResult(
        scan_type="secret",
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
        report = {
            "scan_type": "secret",
            "scanner": SCANNER,
            "status": "config_error",
            "error": exc.__class__.__name__,
            "production_ready": False,
        }
        _write(args.json_report, report)
        print("LOCAL_SECRET_SCAN: config_error")
        return 2

    payload = redact_report(result.model_dump())
    _write(args.json_report, payload)
    confirmed = result.findings_summary.critical + result.findings_summary.high
    if not args.quiet:
        print(
            f"secret scan status={result.status} "
            f"critical={result.findings_summary.critical} high={result.findings_summary.high} "
            f"informational={result.findings_summary.informational} report={args.json_report}"
        )
    if result.status in ("tool_unavailable", "config_error"):
        return 2
    return 1 if confirmed else 0


def _write(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
