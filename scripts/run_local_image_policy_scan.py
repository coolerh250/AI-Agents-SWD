#!/usr/bin/env python3
"""Step 54.3 -- local image policy scan (local-only, no registry, no pull/push).

Reads the committed container image inventory + Dockerfile security inventory and
emits normalized POLICY findings (digest missing, latest/floating tag, Dockerfile
no USER, base image not digest-pinned, job image missing pg client, registry
credential absent for future private use). It performs NO CVE lookup, NO registry
login, NO image pull/push. Output redacted, written to a runtime path (NEVER
committed).

Exit: 0 = completed (policy findings recorded, non-gating); 2 = config error.

Usage: python scripts/run_local_image_policy_scan.py [--json-report PATH] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from shared.sdk.security_findings import (  # noqa: E402
    FindingsSummary,
    SecurityFinding,
    make_finding_id,
    redact_report,
)

SCANNER = "custom_image_inventory_policy_check"
DEFAULT_REPORT = ROOT / ".runtime" / "security" / "images" / "image-policy-report.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(name: str) -> dict:
    p = ROOT / "infra" / "security" / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {}


def _finding(rule: str, sev: str, title: str, ref: str, rem: str) -> SecurityFinding:
    return SecurityFinding(
        finding_id=make_finding_id(SCANNER, "dependency", rule, ref, None),
        scanner=SCANNER,
        category="dependency",
        severity=sev,  # type: ignore[arg-type]
        title=title,
        description=rule,
        file_path=None,
        rule_id=rule,
        evidence_redacted=ref,
        remediation=rem,
        production_blocker=False,
        requires_approval=sev in ("high", "medium"),
    )


def run() -> dict:
    inv = _load("container-image-inventory.yaml")
    registry = _load("registry-credential-boundary.yaml").get("registryCredentialBoundary", {})
    images = inv.get("images", [])
    if not images:
        return {
            "scanner": SCANNER,
            "status": "config_error",
            "limitations": ["container-image-inventory missing"],
            "productionReady": False,
        }

    findings: list[SecurityFinding] = []
    for img in images:
        ref = img.get("image", img.get("repository", "?"))
        if not img.get("digestPinned"):
            findings.append(
                _finding(
                    "IMG-NO-DIGEST",
                    "medium",
                    "image not digest-pinned",
                    ref,
                    "pin the image by @sha256 digest before cluster smoke",
                )
            )
        if img.get("latestTag"):
            findings.append(
                _finding(
                    "IMG-LATEST-TAG",
                    "high",
                    "image uses latest tag",
                    ref,
                    "replace latest with a digest-pinned semantic tag",
                )
            )
        if img.get("firstParty") and "dockerfile_no_nonroot_user" in (img.get("blockers") or []):
            findings.append(
                _finding(
                    "IMG-DOCKERFILE-ROOT",
                    "medium",
                    "first-party image runs as root (no USER)",
                    ref,
                    "add a non-root USER to the Dockerfile",
                )
            )
        if "pg_dump_psql_not_installed_runtime_smoke_required" in (img.get("blockers") or []):
            findings.append(
                _finding(
                    "IMG-JOB-NO-PGCLIENT",
                    "medium",
                    "job image lacks pg_dump/psql; runtime smoke required",
                    ref,
                    "install postgresql-client or use a dedicated job image",
                )
            )

    if not registry.get("credentialViaSecretStoreOnly"):
        findings.append(
            _finding(
                "IMG-REGISTRY-CRED-UNBOUNDED",
                "low",
                "registry credential boundary not modeled",
                "registry",
                "reference registry credentials via the Step 53 secret store",
            )
        )

    limitations = [
        "policy_only_no_cve_lookup",
        "no_image_pull_no_registry_login",
        "digest_resolution_requires_registry_query_not_performed",
    ]
    status = "completed_with_policy_findings" if findings else "completed_no_findings"
    report = {
        "schemaVersion": "1",
        "scanner": SCANNER,
        "imageRef": "all_inventory_images",
        "digest": "",
        "networkUsed": False,
        "registryLoginUsed": False,
        "status": status,
        "vulnerabilities": [],
        "policyFindings": [f.model_dump() for f in findings],
        "findingsSummary": FindingsSummary.from_findings(findings).model_dump(),
        "limitations": limitations,
        "generatedAt": _now(),
        "productionReady": False,
    }
    return redact_report(report)  # type: ignore[return-value]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-report", default=str(DEFAULT_REPORT))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    report = run()
    p = Path(args.json_report)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not args.quiet:
        s = report.get("findingsSummary", {})
        print(
            f"image policy status={report.get('status')} "
            f"high={s.get('high', 0)} medium={s.get('medium', 0)} low={s.get('low', 0)} "
            f"report={args.json_report}"
        )
    return 2 if report.get("status") == "config_error" else 0


if __name__ == "__main__":
    sys.exit(main())
