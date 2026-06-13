"""Stage 41 -- regression JSON report format validation."""

import json
import re



REQUIRED_REPORT_KEYS = {
    "report_id",
    "started_at",
    "completed_at",
    "mode",
    "result_class",
    "environment_ready",
    "host_dependency_caveat_closed",
    "scripts",
    "summary",
    "dependency_failures",
    "known_gaps",
    "caveats",
}

REQUIRED_SUMMARY_KEYS = {
    "total",
    "pass",
    "skipped_pass",
    "pass_with_gaps",
    "fail",
    "environment_failure",
    "safety_failure",
    "regression_failure",
}

REQUIRED_SCRIPT_KEYS = {
    "script",
    "result_class",
    "started_at",
    "completed_at",
    "duration_seconds",
    "exit_code",
    "key_marker",
    "allowed_gap",
    "failure_reason",
}

SECRET_PATTERNS = [
    r"DISCORD_BOT_TOKEN",
    r"GITHUB_TOKEN\s*=\s*[^\s]",
    r"OPENAI_API_KEY",
    r"ANTHROPIC_API_KEY",
    r"BACKUP_ENCRYPTION_KEY\s*=\s*[^\s]",
    r"AUDIT_HMAC_KEY\s*=\s*[^\s]",
    r"sk-[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{20,}",
]

SAMPLE_REPORT = {
    "report_id": "regression_20260613_120000",
    "started_at": "2026-06-13T12:00:00Z",
    "completed_at": "2026-06-13T12:05:00Z",
    "mode": "full",
    "result_class": "pass",
    "environment_ready": True,
    "host_dependency_caveat_closed": True,
    "scripts": [
        {
            "script": "scripts/verify_incident_response.sh",
            "result_class": "pass",
            "started_at": "2026-06-13T12:00:01Z",
            "completed_at": "2026-06-13T12:00:11Z",
            "duration_seconds": 10,
            "exit_code": 0,
            "key_marker": "INCIDENT_RESPONSE_VERIFY: PASS",
            "allowed_gap": False,
            "failure_reason": "",
        }
    ],
    "summary": {
        "total": 1,
        "pass": 1,
        "skipped_pass": 0,
        "pass_with_gaps": 0,
        "fail": 0,
        "environment_failure": 0,
        "safety_failure": 0,
        "regression_failure": 0,
    },
    "dependency_failures": [],
    "known_gaps": ["encryption_no_key", "storage_not_off_host"],
    "caveats": [],
}


def test_sample_report_has_required_keys():
    assert REQUIRED_REPORT_KEYS <= set(SAMPLE_REPORT.keys())


def test_sample_report_summary_has_required_keys():
    assert REQUIRED_SUMMARY_KEYS <= set(SAMPLE_REPORT["summary"].keys())


def test_sample_report_script_entry_has_required_keys():
    assert SAMPLE_REPORT["scripts"]
    entry = SAMPLE_REPORT["scripts"][0]
    assert REQUIRED_SCRIPT_KEYS <= set(entry.keys())


def test_sample_report_no_secrets():
    text = json.dumps(SAMPLE_REPORT)
    for pattern in SECRET_PATTERNS:
        assert not re.search(pattern, text), f"secret pattern found: {pattern}"


def test_report_serializable_to_json():
    text = json.dumps(SAMPLE_REPORT)
    loaded = json.loads(text)
    assert loaded["result_class"] == "pass"


def test_report_environment_ready_boolean():
    assert isinstance(SAMPLE_REPORT["environment_ready"], bool)
    assert isinstance(SAMPLE_REPORT["host_dependency_caveat_closed"], bool)


def test_known_gaps_are_strings():
    for gap in SAMPLE_REPORT["known_gaps"]:
        assert isinstance(gap, str)


def test_scripts_list_non_empty():
    assert len(SAMPLE_REPORT["scripts"]) >= 1


def test_summary_totals_consistent():
    s = SAMPLE_REPORT["summary"]
    total_parts = (
        s["pass"]
        + s["skipped_pass"]
        + s["pass_with_gaps"]
        + s["fail"]
        + s["environment_failure"]
        + s["safety_failure"]
        + s["regression_failure"]
    )
    assert total_parts == s["total"]


SAMPLE_SUMMARY = {
    "completed_at": "2026-06-13T12:05:00Z",
    "result_class": "pass",
    "environment_ready": True,
    "host_dependency_caveat_closed": True,
    "report_path": "source/regression-reports/regression_20260613_120000.json",
    "dependency_failures": [],
    "known_gaps": [],
    "caveats": [],
    "summary": {"total": 1, "pass": 1, "fail": 0},
}


def test_summary_file_has_required_keys():
    required = {
        "completed_at",
        "result_class",
        "environment_ready",
        "host_dependency_caveat_closed",
        "report_path",
        "dependency_failures",
        "known_gaps",
        "caveats",
        "summary",
    }
    assert required <= set(SAMPLE_SUMMARY.keys())


def test_summary_no_secrets():
    text = json.dumps(SAMPLE_SUMMARY)
    for pattern in SECRET_PATTERNS:
        assert not re.search(pattern, text), f"secret pattern found: {pattern}"
