"""Step 64B.2B -- staging runtime bootstrap (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-runtime-bootstrap-report.md"
STATUS = STAGING / "staging-runtime-service-status.md"
ACCESS = STAGING / "staging-admin-console-access-evidence.md"
LIMITS = STAGING / "staging-runtime-known-limitations.md"
STOP = STAGING / "staging-runtime-stop-and-restart-notes.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, STATUS, ACCESS, LIMITS, STOP)


def test_runtime_bootstrap_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_target_host_documented() -> None:
    for p in DOCS:
        assert "10.0.1.32" in p.read_text(encoding="utf-8"), p.name


def test_compose_file_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "docker-compose.staging.yml" in both


def test_admin_console_access_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "/admin" in both
    assert "localhost:18000/admin" in both


def test_ssh_port_forward_instruction_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "-L 18000:127.0.0.1:18000" in both


def test_live_integrations_disabled() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "live-integrations=disabled" in text


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "production-ready=false" in text
        assert "production-action=true" not in text
        assert "production-ready=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64b2b_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64B.2B" in text
    assert "STAGING_RUNTIME_BOOTSTRAP_VERIFY" in text
