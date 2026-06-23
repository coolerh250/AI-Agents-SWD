#!/usr/bin/env python3
"""Step 54.1 -- security evidence model verifier.

Asserts the evidence model, threat-model input, release-risk input, and finding
taxonomy exist; required evidence types present; no secret value allowed.

Marker: SECURITY_EVIDENCE_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "security"

REQUIRED_EVIDENCE = {
    "sast_report",
    "dependency_scan_report",
    "secret_scan_report",
    "sbom",
    "image_digest_report",
    "image_vulnerability_report",
    "threat_model",
    "release_risk_summary",
    "qa_report",
    "audit_evidence",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load(name: str) -> dict:
    p = SDIR / name
    if not p.is_file():
        bad(f"missing {name}")
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def main() -> int:
    evidence = _load("security-evidence-model.yaml").get("securityEvidence", {})
    threat = _load("threat-model-input-catalog.yaml").get("threatModel", {})
    release = _load("release-risk-input-catalog.yaml").get("releaseRisk", {})
    taxonomy = _load("security-finding-taxonomy.yaml")

    keys = {e.get("key") for e in evidence.get("evidenceTypes", [])}
    missing = REQUIRED_EVIDENCE - keys
    if missing:
        bad(f"evidence types missing: {sorted(missing)}")
    else:
        ok("evidence model present with all required evidence types")

    if evidence.get("noSecretValueAllowed") is not True:
        bad("evidence model must set noSecretValueAllowed=true")
    else:
        ok("evidence model forbids secret values")

    if not evidence.get("requiredEvidenceFields"):
        bad("evidence model missing requiredEvidenceFields (hash/path/generatedAt/...)")
    else:
        ok("evidence carries hash/path/generatedAt/tool/scope/status fields")

    if not threat.get("assets") or not threat.get("trustBoundaries"):
        bad("threat model inputs not mapped (assets/trustBoundaries)")
    else:
        ok("threat model inputs mapped")

    if not release.get("inputs"):
        bad("release risk inputs not mapped")
    else:
        ok("release risk inputs mapped")

    if not taxonomy.get("severities"):
        bad("finding taxonomy missing severities")
    else:
        ok("finding taxonomy exists")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_EVIDENCE_MODEL_VERIFY: FAIL")
        return 1
    print("SECURITY_EVIDENCE_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
