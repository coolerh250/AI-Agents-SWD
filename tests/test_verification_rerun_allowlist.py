"""Stage 52 -- verification rerun allowlist + path containment."""

from __future__ import annotations

import pytest

from shared.sdk.operator_actions.verification_runner import (
    ALLOWLISTED_SCRIPTS,
    VerificationNotAllowed,
    requires_higher_confirmation,
    resolve_script,
)


def test_allowlist_exact_set() -> None:
    assert set(ALLOWLISTED_SCRIPTS) == {
        "delivery_package_acceptance_gate",
        "admin_console_v0",
        "backup_dr_gap_closure",
        "audit_integrity",
        "full_regression",
    }


def test_resolve_allowlisted() -> None:
    assert resolve_script("admin_console_v0").name == "verify_admin_console_v0.sh"


@pytest.mark.parametrize("bad", ["../../etc/passwd", "/bin/sh", "arbitrary", "rm -rf /", ""])
def test_arbitrary_rejected(bad) -> None:
    with pytest.raises(VerificationNotAllowed):
        resolve_script(bad)


def test_full_regression_higher_confirmation() -> None:
    assert requires_higher_confirmation("full_regression") is True
    assert requires_higher_confirmation("admin_console_v0") is False
