import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_redis,
    setup_tracing,
)
from worker import AuditWorker

setup_tracing("audit-worker")
instrument_asyncpg()
instrument_redis()

_worker = AuditWorker()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    consumer = asyncio.create_task(_worker.run(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _worker.close()


app = FastAPI(title="audit-worker", lifespan=lifespan)
instrument_fastapi(app, "audit-worker")
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "audit-worker", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _worker.status()
