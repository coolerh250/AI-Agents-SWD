"""Step 64B.1 -- authenticated staging host preflight (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-host-preflight-report.md"
READINESS = STAGING / "staging-runtime-bootstrap-readiness.md"
PROGRESS = ROOT / "source" / "progress.md"


def test_host_preflight_report_exists() -> None:
    assert REPORT.is_file()


def test_bootstrap_readiness_doc_exists() -> None:
    assert READINESS.is_file()


def test_target_host_documented() -> None:
    assert "10.0.1.32" in REPORT.read_text(encoding="utf-8")
    assert "10.0.1.32" in READINESS.read_text(encoding="utf-8")


def test_credential_handling_is_safe() -> None:
    low = (REPORT.read_text(encoding="utf-8") + READINESS.read_text(encoding="utf-8")).lower()
    assert "key-based" in low or "interactive" in low
    assert "never" in low


def test_no_real_credential_values() -> None:
    for p in (REPORT, READINESS):
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_no_runtime_deployment_claimed() -> None:
    for p in (REPORT, READINESS):
        text = p.read_text(encoding="utf-8")
        assert "runtime-deployment=false" in text
        assert "runtime-deployment=true" not in text


def test_no_production_action_allowed() -> None:
    for p in (REPORT, READINESS):
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "production-ready=false" in text
        assert "production-action=true" not in text
        assert "production-ready=true" not in text


def test_step64b1_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64B.1" in text
    assert "STAGING_HOST_AUTHENTICATED_PREFLIGHT_VERIFY" in text
