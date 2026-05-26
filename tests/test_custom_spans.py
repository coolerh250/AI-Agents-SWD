from shared.sdk.observability.tracing import (
    extract_trace_context,
    generate_span_id,
    generate_trace_id,
    inject_trace_context,
    setup_tracing,
    start_span,
)

# These tests run without a Tempo backend — they verify that the span helper is
# correctly shaped (context-manager, accepts arbitrary attributes, never raises
# when OTel is best-effort) so the wrapping calls in workflow / agent / retry
# code paths are safe.


def test_start_span_is_a_context_manager():
    setup_tracing("custom-spans-test")
    with start_span("aiagents.test", task_id="t-1", workflow_id="wf-1") as span:
        # the span object exposes set_attribute (real or no-op fallback)
        span.set_attribute("custom.attribute", "value")


def test_start_span_swallows_attribute_errors():
    """Set_attribute on weird values must not crash the span context."""
    with start_span("aiagents.test", task_id="t-2", workflow_id="wf-2") as span:
        span.set_attribute("none_attr", None)  # OTel rejects None, helper coerces
        span.set_attribute("dict_attr", {"a": 1})  # coerced to str


def test_start_span_does_not_break_exceptions():
    """Exceptions inside the span must propagate (the span only records them)."""
    try:
        with start_span("aiagents.test.error"):
            raise RuntimeError("from inside the span")
    except RuntimeError as exc:
        assert "from inside the span" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_trace_id_propagates_through_correlation_payload():
    """Downstream agents must keep the upstream trace_id."""
    upstream = inject_trace_context({"task_id": "t-1"}, parent_trace_id="a" * 32)
    downstream = inject_trace_context({"task_id": "t-1", "trace_id": upstream["trace_id"]})
    assert downstream["trace_id"] == upstream["trace_id"]
    # but the span_id should be fresh — receivers see one span per stage
    assert downstream["span_id"] != upstream["span_id"]


def test_extract_trace_context_carries_ids():
    event = inject_trace_context({"task_id": "t-3"})
    extracted = extract_trace_context(event)
    assert extracted["trace_id"] == event["trace_id"]
    assert extracted["span_id"] == event["span_id"]


def test_generate_trace_and_span_ids_are_otel_shaped():
    trace_id = generate_trace_id()
    span_id = generate_span_id()
    assert len(trace_id) == 32
    assert len(span_id) == 16
    int(trace_id, 16)
    int(span_id, 16)


def test_workflow_custom_span_names_present_in_workflow_module():
    """Sanity-check that the orchestrator workflow opens every required span.

    We grep the source rather than execute the whole workflow because the
    workflow nodes hit external services. The string check ensures Step 15.2
    instrumentation does not silently regress.
    """
    from pathlib import Path

    workflow_src = (
        Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src" / "workflow.py"
    ).read_text(encoding="utf-8")
    for name in (
        "workflow.policy_check",
        "workflow.approval_request",
        "workflow.audit",
        "workflow.dispatch",
        "workflow.run",
    ):
        assert name in workflow_src, f"workflow.py missing custom span {name}"

    events_src = (
        Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src" / "workflow_events.py"
    ).read_text(encoding="utf-8")
    for name in ("workflow.event_update", "workflow.completed"):
        assert name in events_src, f"workflow_events.py missing custom span {name}"

    main_src = (
        Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src" / "main.py"
    ).read_text(encoding="utf-8")
    assert "workflow.failed" in main_src


def test_agent_custom_span_names_present_in_stream_agent():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "shared" / "sdk" / "base_agent" / "stream_agent.py"
    ).read_text(encoding="utf-8")
    for name in (
        "agent.receive",
        "agent.analyze",
        "agent.execute",
        "agent.publish_next",
        "agent.write_audit",
        "agent.publish_notification",
    ):
        assert name in src, f"stream_agent.py missing custom span {name}"


def test_retry_custom_span_names_present_in_scheduler():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "apps" / "retry-scheduler" / "src" / "scheduler.py"
    ).read_text(encoding="utf-8")
    for name in (
        "retry.consume_deadletter",
        "retry.requeue",
        "retry.terminal_failure",
        "retry.manual_replay",
    ):
        assert name in src, f"scheduler.py missing custom span {name}"
