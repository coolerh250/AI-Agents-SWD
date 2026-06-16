"""Stage 52 -- verification rerun uses shell=False, fixed argv, redaction."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.operator_actions import verification_runner as vr


def test_source_uses_shell_false() -> None:
    src = Path(vr.__file__).read_text(encoding="utf-8")
    assert "shell=False" in src
    # no shell=True anywhere
    assert "shell=True" not in src


def test_redaction_strips_secrets() -> None:
    text = "token=ghp_ABCDEFGHIJKLMNOPQRSTUV\nDISCORD secret: sk-abcdefghij1234567890\nok"
    red = vr.redact(text)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUV" not in red
    assert "***REDACTED***" in red


def test_run_rejects_arbitrary_key() -> None:
    import pytest

    with pytest.raises(vr.VerificationNotAllowed):
        vr.run_verification("arbitrary_key")


def test_argv_has_no_user_args() -> None:
    # The allowlist values carry only fixed args; none accept user input.
    for _key, (_path, extra, _lock, _hi) in vr.ALLOWLISTED_SCRIPTS.items():
        for a in extra:
            assert a.startswith("--")
