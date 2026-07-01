"""Step 64E.1 -- staging Admin Console React bundle remediation (docs + Dockerfile)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-admin-console-react-bundle-remediation-report.md"
VALIDATION = STAGING / "staging-admin-console-remediation-validation.md"
REREVIEW = STAGING / "staging-admin-console-operator-rereview-plan.md"
GAPS = STAGING / "staging-admin-console-remediation-known-gaps.md"
DOCKERFILE = ROOT / "apps" / "orchestrator" / "Dockerfile"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, VALIDATION, REREVIEW, GAPS)


def test_remediation_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_react_vite_bundle_remediation_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "vite" in low or "react" in low
    assert "bundle" in low


def test_dockerfile_builds_bundle() -> None:
    df = DOCKERFILE.read_text(encoding="utf-8")
    assert "admin-console-build" in df
    assert "npm run build" in df
    assert "admin_console_static/dist" in df


def test_operator_rereview_required() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "re-review" in low or "rereview" in low or "re review" in low


def test_step64e_not_marked_pass() -> None:
    for p in DOCS:
        for line in p.read_text(encoding="utf-8").splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll:
                assert "failed_operator_validation" in ll or " not " in ll, line


def test_step64f_blocked() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low
    assert "block" in low


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_live_integrations_disabled() -> None:
    for p in DOCS:
        assert "live-integrations=disabled" in p.read_text(encoding="utf-8")


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64e1_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.1" in text
    assert "STAGING_ADMIN_CONSOLE_REACT_BUNDLE_REMEDIATION_VERIFY" in text
