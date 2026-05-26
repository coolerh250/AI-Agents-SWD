import contextlib
import logging
import os
import uuid
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger("aiagents.tracing")

_initialized: set[str] = set()
_instrumented_fastapi_apps: set[int] = set()
_global_instruments_done: set[str] = set()
_TRACER_PROVIDER: Any = None


def setup_tracing(service_name: str) -> None:
    """Configure OpenTelemetry for this service.

    Best-effort: missing OpenTelemetry packages are silently ignored so a
    service can still start without a tracing backend. When the SDK is
    installed a TracerProvider is registered with the service name; if
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set we attach a BatchSpanProcessor that
    pushes to that OTLP collector. Idempotent: calling it twice for the same
    ``service_name`` is a no-op.
    """
    global _TRACER_PROVIDER
    if service_name in _initialized:
        return
    _initialized.add(service_name)
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except Exception as exc:
        logger.warning("setup_tracing(%s): OTel SDK unavailable (%s)", service_name, exc)
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
        except Exception as exc:
            logger.warning("setup_tracing(%s): OTLP exporter unavailable (%s)", service_name, exc)
    trace.set_tracer_provider(provider)
    _TRACER_PROVIDER = provider


def get_tracer(name: str) -> Any:
    """Return a tracer for a given component name (best-effort).

    Falls back to a stub whose spans are no-ops when the OTel SDK is not
    installed — the calling code stays the same.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:
        return _NoopTracer()


@contextlib.contextmanager
def start_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Context manager that opens a span on the default tracer.

    Attribute values are coerced to OTel-friendly primitives. Errors raised
    inside the block are recorded on the span and re-raised. Falls back to a
    no-op span when the OTel SDK is unavailable so call sites stay safe.
    """
    tracer = get_tracer("aiagents")
    try:
        cm = tracer.start_as_current_span(name)
    except Exception:
        yield _NoopSpan()
        return
    with cm as span:
        for key, value in attributes.items():
            if value is None or value == "":
                continue
            with contextlib.suppress(Exception):
                span.set_attribute(key, _coerce(value))
        try:
            yield span
        except Exception as exc:
            with contextlib.suppress(Exception):
                span.record_exception(exc)
            raise


def _coerce(value: Any) -> Any:
    """Coerce attribute values to OTel-friendly primitives."""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def instrument_fastapi(app: Any, service_name: str = "") -> None:
    """Instrument a FastAPI app for HTTP spans. Idempotent and best-effort."""
    app_id = id(app)
    if app_id in _instrumented_fastapi_apps:
        return
    _instrumented_fastapi_apps.add(app_id)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument_app(app)
    except Exception as exc:
        logger.warning(
            "instrument_fastapi(%s): FastAPI instrumentation unavailable (%s)",
            service_name,
            exc,
        )


def instrument_httpx() -> None:
    """Instrument httpx for client spans. Idempotent and best-effort."""
    if "httpx" in _global_instruments_done:
        return
    _global_instruments_done.add("httpx")
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.warning("instrument_httpx: unavailable (%s)", exc)


def instrument_redis() -> None:
    """Instrument redis-py for command spans. Idempotent and best-effort."""
    if "redis" in _global_instruments_done:
        return
    _global_instruments_done.add("redis")
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.warning("instrument_redis: unavailable (%s)", exc)


def instrument_asyncpg() -> None:
    """Instrument asyncpg for SQL spans. Idempotent and best-effort."""
    if "asyncpg" in _global_instruments_done:
        return
    _global_instruments_done.add("asyncpg")
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
    except Exception as exc:
        logger.warning("instrument_asyncpg: unavailable (%s)", exc)


def instrument_all_clients() -> None:
    """Convenience wrapper: instrument httpx + redis + asyncpg at once."""
    instrument_httpx()
    instrument_redis()
    instrument_asyncpg()


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


class _NoopSpan:
    """Fallback span used when the OTel SDK is unavailable."""

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def record_exception(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None


class _NoopTracer:
    """Fallback tracer used when the OTel SDK is unavailable."""

    @contextlib.contextmanager
    def start_as_current_span(self, _name: str) -> Iterator[_NoopSpan]:
        yield _NoopSpan()
