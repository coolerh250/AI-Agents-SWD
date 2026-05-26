from fastapi import FastAPI

from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)


def test_setup_tracing_is_idempotent():
    setup_tracing("auto-instrumentation-test")
    setup_tracing("auto-instrumentation-test")  # second call must be a no-op
    setup_tracing("auto-instrumentation-other")


def test_instrument_fastapi_is_idempotent_and_safe():
    app = FastAPI()
    instrument_fastapi(app, "auto-instrumentation-test")
    # second call on the same app must not raise the OTel "already instrumented"
    instrument_fastapi(app, "auto-instrumentation-test")


def test_instrument_clients_are_idempotent_and_safe():
    # all three are global instrumentors — call each twice, neither should raise
    instrument_httpx()
    instrument_httpx()
    instrument_redis()
    instrument_redis()
    instrument_asyncpg()
    instrument_asyncpg()


def test_instrumentation_packages_importable():
    # All four OTel auto-instrumentation packages must be importable in the test
    # environment so the service containers actually have them at runtime.
    import opentelemetry.instrumentation.asyncpg  # noqa: F401
    import opentelemetry.instrumentation.fastapi  # noqa: F401
    import opentelemetry.instrumentation.httpx  # noqa: F401
    import opentelemetry.instrumentation.redis  # noqa: F401


def test_otlp_grpc_exporter_importable():
    # Custom spans only reach Tempo if the OTLP gRPC exporter is installed.
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: F401
        OTLPSpanExporter,
    )
