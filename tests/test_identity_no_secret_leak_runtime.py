"""Step 52.4 -- no secret / raw email / group ID in the posture surface."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.identity_posture import (
    build_identity_posture_summary,
    find_sensitive,
    full_report,
)

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "shared" / "sdk" / "identity_posture"
API = ROOT / "apps" / "orchestrator" / "src" / "identity_posture_api.py"


def test_summary_has_no_sensitive_values() -> None:
    assert find_sensitive(build_identity_posture_summary()) == []


def test_full_report_has_no_sensitive_values() -> None:
    assert find_sensitive(full_report(build_identity_posture_summary())) == []


def test_sdk_modules_have_no_secret_like_value() -> None:
    for p in SDK.glob("*.py"):
        # redaction.py legitimately holds the GUID detector pattern fragment
        if p.name == "redaction.py":
            continue
        assert find_sensitive(p.read_text(encoding="utf-8")) == [], p.name


def test_detector_positive_control() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert find_sensitive({"token": jwt}) != []
    assert find_sensitive({"tenant": "12345678-1234-1234-1234-123456789abc"}) != []
