from shared.sdk.observability.correlation import correlation_payload
from shared.sdk.observability.tracing import (
    extract_trace_context,
    generate_span_id,
    generate_trace_id,
    inject_trace_context,
    setup_tracing,
)


def test_setup_tracing_is_idempotent_and_safe():
    setup_tracing("test-tracing-1")
    setup_tracing("test-tracing-1")
    setup_tracing("test-tracing-2")  # different service is fine too


def test_generate_trace_id_is_32_hex():
    tid = generate_trace_id()
    assert len(tid) == 32
    int(tid, 16)


def test_generate_span_id_is_16_hex():
    sid = generate_span_id()
    assert len(sid) == 16
    int(sid, 16)


def test_inject_trace_context_creates_ids_when_missing():
    event: dict = {"task_id": "t"}
    inject_trace_context(event)
    assert event["trace_id"]
    assert event["span_id"]


def test_inject_trace_context_carries_parent_trace_id():
    parent = "a" * 32
    event: dict = {"task_id": "t"}
    inject_trace_context(event, parent_trace_id=parent)
    assert event["trace_id"] == parent
    assert event["span_id"]
    # the parent passes through but the span id is fresh
    assert event["span_id"] != parent[:16]


def test_extract_trace_context_returns_empty_when_missing():
    assert extract_trace_context({}) == {"trace_id": "", "span_id": ""}


def test_extract_trace_context_roundtrip():
    event = inject_trace_context({"task_id": "t"})
    extracted = extract_trace_context(event)
    assert extracted["trace_id"] == event["trace_id"]
    assert extracted["span_id"] == event["span_id"]


def test_correlation_payload_propagates_trace_across_stages():
    upstream = correlation_payload({"task_id": "t-1", "workflow_id": "wf-1"})
    downstream = correlation_payload(
        {"task_id": "t-1", "workflow_id": "wf-1", "trace_id": upstream["trace_id"]}
    )
    assert downstream["trace_id"] == upstream["trace_id"]
    # span_id is freshly generated per hop so receivers see one span per stage
    assert downstream["span_id"] != upstream["span_id"]


def test_correlation_payload_keeps_task_and_workflow_ids():
    block = correlation_payload({"task_id": "t-x", "workflow_id": "wf-x"})
    assert block["task_id"] == "t-x"
    assert block["workflow_id"] == "wf-x"
    assert block["trace_id"]
    assert block["span_id"]
