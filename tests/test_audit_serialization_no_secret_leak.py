"""Stage 44 -- serialization surfaces never leak secrets."""

from __future__ import annotations

import re
from pathlib import Path

SECRET_KEYS = ["AUDIT_HMAC_KEY", "DISCORD_BOT_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"]
SECRET_TOKEN_RE = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}"
)

SCRIPTS = [
    Path("scripts/lib/audit_verification_lock.sh"),
    Path("scripts/detect_audit_tamper_residue.sh"),
    Path("scripts/simulate_audit_tamper_detection.sh"),
    Path("scripts/verify_audit_touching_serialization.sh"),
]


def test_scripts_do_not_echo_secret_env():
    for p in SCRIPTS:
        if not p.is_file():
            continue
        content = p.read_text(encoding="utf-8")
        for key in SECRET_KEYS:
            assert f"echo ${key}" not in content, f"{p} echoes {key}"
            assert f'echo "${key}' not in content, f"{p} echoes {key}"


def test_scripts_have_no_hardcoded_tokens():
    for p in SCRIPTS:
        if not p.is_file():
            continue
        assert not SECRET_TOKEN_RE.search(p.read_text(encoding="utf-8")), f"token-like in {p}"


def test_lock_report_shape_has_no_secret_fields():
    # The lock metadata writer only emits these keys.
    content = Path("scripts/lib/audit_verification_lock.sh").read_text(encoding="utf-8")
    block = content.split("record_lock_metadata()", 1)[1].split("\n}", 1)[0]
    for key in SECRET_KEYS:
        assert key not in block


def test_detector_report_redacts_payload():
    content = Path("scripts/detect_audit_tamper_residue.sh").read_text(encoding="utf-8")
    # The detector selects only safe columns -- never the summary text.
    assert "al.summary" not in content
    assert "SELECT id, decision_type, task_id, created_at" in content
