"""Stage 32 -- ensure the real-integration counters are registered."""

from __future__ import annotations

from shared.sdk.observability import metrics as m

REAL_INTEGRATION_COUNTERS = (
    "REAL_DISCORD_TESTS_TOTAL",
    "REAL_DISCORD_TASKS_TOTAL",
    "REAL_DISCORD_GUARD_BLOCKS_TOTAL",
    "REAL_GITHUB_SANDBOX_PRS_TOTAL",
    "REAL_GITHUB_GUARD_BLOCKS_TOTAL",
    "REAL_INTEGRATION_FAILURES_TOTAL",
)


def test_all_stage32_counters_exist():
    for name in REAL_INTEGRATION_COUNTERS:
        counter = getattr(m, name)
        assert counter is not None, f"{name} missing from metrics module"


def test_counters_have_expected_labels():
    assert "result" in m.REAL_DISCORD_TESTS_TOTAL._labelnames
    assert "result" in m.REAL_DISCORD_TASKS_TOTAL._labelnames
    assert "reason" in m.REAL_DISCORD_GUARD_BLOCKS_TOTAL._labelnames
    assert "result" in m.REAL_GITHUB_SANDBOX_PRS_TOTAL._labelnames
    assert "reason" in m.REAL_GITHUB_GUARD_BLOCKS_TOTAL._labelnames
    assert set(["provider", "reason"]).issubset(set(m.REAL_INTEGRATION_FAILURES_TOTAL._labelnames))


def test_counters_exposed_via_metrics_response():
    body, ctype = m.metrics_response()
    assert "text/plain" in ctype
    rendered = body.decode("utf-8")
    for metric_name in (
        "real_discord_tests_total",
        "real_discord_tasks_total",
        "real_discord_guard_blocks_total",
        "real_github_sandbox_prs_total",
        "real_github_guard_blocks_total",
        "real_integration_failures_total",
    ):
        assert metric_name in rendered, f"{metric_name} not exposed via /metrics"
