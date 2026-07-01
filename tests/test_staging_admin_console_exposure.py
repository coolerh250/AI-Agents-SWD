"""Step 64C -- staging admin console exposure (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-admin-console-exposure-report.md"
ACCESS = STAGING / "staging-operator-access-validation.md"
INVENTORY = STAGING / "staging-admin-console-page-inventory.md"
LOGIN = STAGING / "staging-operator-first-login-guide.md"
GAPS = STAGING / "staging-admin-console-known-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, ACCESS, INVENTORY, LOGIN, GAPS)

EXPECTED_PAGE_GROUPS = (
    "/safety",
    "/metrics",
    "/production-readiness",
    "/controlled-rollout-review",
    "/release-governance",
    "/backup-dr",
    "/sandbox-github",
)


def test_exposure_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_target_host_documented() -> None:
    for p in DOCS:
        assert "10.0.1.32" in p.read_text(encoding="utf-8"), p.name


def test_operator_url_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "localhost:18000/admin" in both


def test_ssh_port_forward_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "-L 18000:127.0.0.1:18000" in both


def test_page_inventory_includes_expected_groups() -> None:
    inv = INVENTORY.read_text(encoding="utf-8")
    for route in EXPECTED_PAGE_GROUPS:
        assert route in inv, route


def test_no_public_exposure_by_default() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "public-exposure=false" in text
        assert "public-exposure=true" not in text


def test_live_integrations_disabled() -> None:
    for p in DOCS:
        assert "live-integrations=disabled" in p.read_text(encoding="utf-8")


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


def test_step64c_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64C" in text
    assert "STAGING_ADMIN_CONSOLE_EXPOSURE_VERIFY" in text
