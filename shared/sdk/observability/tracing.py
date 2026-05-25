import os
import uuid

_initialized: set[str] = set()


def setup_tracing(service_name: str) -> None:
    """Configure OpenTelemetry for this service when the SDK is available.

    Best-effort: missing OpenTelemetry packages are silently ignored so a
    service can still start without a tracing backend. When the SDK is
    installed a TracerProvider is registered with the service name; if
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set we also attach a BatchSpanProcessor
    that pushes to that OTLP collector. No real cloud observability SaaS is
    contacted unless the operator explicitly sets the endpoint.
    """
    if service_name in _initialized:
        return
    _initialized.add(service_name)
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except Exception:
        return
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        except Exception:
            pass
    trace.set_tracer_provider(provider)


def _current_otel_ids() -> tuple[str, str]:
    """Return (trace_id, span_id) hex strings from the current OTel span, if any."""
    try:
        from opentelemetry import trace as otel_trace
    except Exception:
        return "", ""
    span = otel_trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.is_valid:
        return "", ""
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def generate_trace_id() -> str:
    """Generate a fresh 128-bit trace id (32 hex chars, OTel-compatible)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a fresh 64-bit span id (16 hex chars, OTel-compatible)."""
    return uuid.uuid4().hex[:16]


def inject_trace_context(carrier: dict, parent_trace_id: str | None = None) -> dict:
    """Add trace_id / span_id to a carrier dict (Redis event, log record, etc.).

    The trace_id is preserved across an entire workflow — if the caller passes a
    parent trace_id (e.g. from the upstream message) we reuse it; otherwise we
    pick up the active OpenTelemetry span's trace_id, or fall back to a fresh
    UUID-derived id. A fresh span_id is generated for every injection so the
    receiver sees one span per pipeline stage.
    """
    current_trace, current_span = _current_otel_ids()
    trace_id = (
        parent_trace_id
        or (carrier.get("trace_id") if isinstance(carrier, dict) else None)
        or current_trace
        or generate_trace_id()
    )
    span_id = current_span or generate_span_id()
    if isinstance(carrier, dict):
        carrier["trace_id"] = trace_id
        carrier["span_id"] = span_id
        return carrier
    return {"trace_id": trace_id, "span_id": span_id}


def extract_trace_context(carrier: dict) -> dict:
    """Read trace_id / span_id from a carrier (empty strings if absent)."""
    if not isinstance(carrier, dict):
        return {"trace_id": "", "span_id": ""}
    return {
        "trace_id": str(carrier.get("trace_id") or ""),
        "span_id": str(carrier.get("span_id") or ""),
    }
