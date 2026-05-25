from shared.sdk.observability.tracing import (
    extract_trace_context,
    generate_span_id,
    generate_trace_id,
    inject_trace_context,
)

CORRELATION_FIELDS = ("task_id", "workflow_id", "trace_id", "span_id")


def correlation_payload(
    payload: dict, default_task_id: str = "unknown", inject_new_span: bool = True
) -> dict:
    """Build the standard task / workflow / trace correlation block.

    Each Redis event in the AI Agents SWD pipeline carries the same shape:
    ``{task_id, workflow_id, trace_id, span_id}``. ``inject_new_span`` controls
    whether a fresh span_id is generated for the outgoing message (default) or
    the inbound span_id is carried forward unchanged.
    """
    block: dict = {
        "task_id": str(payload.get("task_id", default_task_id)),
        "workflow_id": str(payload.get("workflow_id", "")),
    }
    if inject_new_span:
        return inject_trace_context(block, parent_trace_id=str(payload.get("trace_id") or ""))
    extracted = extract_trace_context(payload)
    block["trace_id"] = extracted["trace_id"]
    block["span_id"] = extracted["span_id"]
    return block


__all__ = [
    "CORRELATION_FIELDS",
    "correlation_payload",
    "extract_trace_context",
    "generate_span_id",
    "generate_trace_id",
    "inject_trace_context",
]
