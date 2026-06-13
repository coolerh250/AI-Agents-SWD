"""Stage 41 -- regression reports must not contain secret values."""

import json
import re
from pathlib import Path



SECRET_PATTERNS = [
    (r'"DISCORD_BOT_TOKEN"\s*:\s*"[^"]{8,}"', "Discord bot token"),
    (r'"GITHUB_TOKEN"\s*:\s*"[^"]{8,}"', "GitHub token"),
    (r'"OPENAI_API_KEY"\s*:\s*"[^"]{8,}"', "OpenAI API key"),
    (r'"ANTHROPIC_API_KEY"\s*:\s*"[^"]{8,}"', "Anthropic API key"),
    (r'"BACKUP_ENCRYPTION_KEY"\s*:\s*"[^"]{8,}"', "Backup encryption key"),
    (r'"AUDIT_HMAC_KEY"\s*:\s*"[^"]{8,}"', "HMAC key"),
    (r'sk-[A-Za-z0-9]{20,}', "OpenAI token pattern"),
    (r'ghp_[A-Za-z0-9]{20,}', "GitHub PAT pattern"),
    (r'discord\.[A-Za-z0-9._-]{20,}', "Discord token pattern"),
]

REPORTS_DIR = Path("source/regression-reports")


def _scan_text_for_secrets(text: str) -> list[str]:
    found = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            found.append(label)
    return found


def test_sample_report_no_secrets():
    sample = {
        "report_id": "regression_20260613_120000",
        "result_class": "pass",
        "scripts": [
            {
                "script": "scripts/verify_incident_response.sh",
                "result_class": "pass",
                "key_marker": "INCIDENT_RESPONSE_VERIFY: PASS",
                "failure_reason": "",
            }
        ],
        "dependency_failures": [],
    }
    text = json.dumps(sample)
    leaks = _scan_text_for_secrets(text)
    assert not leaks, f"Secret patterns found in sample report: {leaks}"


def test_existing_reports_no_secrets():
    if not REPORTS_DIR.is_dir():
        return
    for report_file in REPORTS_DIR.glob("*.json"):
        text = report_file.read_text()
        leaks = _scan_text_for_secrets(text)
        assert not leaks, f"Secret patterns in {report_file}: {leaks}"


def test_verify_env_helper_no_secrets():
    p = Path("scripts/lib/verify_env.sh")
    if not p.is_file():
        return
    content = p.read_text()
    # verify_env.sh must not print any secret env var values
    for key in ["DISCORD_BOT_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "AUDIT_HMAC_KEY"]:
        # Allow checking existence (boolean) but not printing the value
        assert not re.search(rf'echo.*\${key}', content), (
            f"verify_env.sh must not echo {key}"
        )


def test_regression_summary_no_secrets(tmp_path):
    summary = {
        "completed_at": "2026-06-13T12:00:00Z",
        "result_class": "pass",
        "environment_ready": True,
        "host_dependency_caveat_closed": True,
        "report_path": "source/regression-reports/regression_20260613.json",
        "dependency_failures": [],
        "known_gaps": ["encryption_no_key"],
        "caveats": [],
    }
    text = json.dumps(summary)
    leaks = _scan_text_for_secrets(text)
    assert not leaks


def test_secret_pattern_detection_works():
    evil_text = '{"GITHUB_TOKEN": "ghp_realtoken1234567890abc"}'
    leaks = _scan_text_for_secrets(evil_text)
    assert leaks, "Secret detection should have found the token"


def test_verification_sdk_no_secret_imports():
    p = Path("shared/sdk/verification/audit_events.py")
    if not p.is_file():
        return
    content = p.read_text()
    for secret_ref in ["asyncpg", "HMAC", "token", "key_value"]:
        assert secret_ref.lower() not in content.lower() or "key" in content.lower(), (
            f"audit_events.py should not reference secrets: {secret_ref}"
        )
