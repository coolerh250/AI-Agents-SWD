import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from agent import MiniDeliveryPilotAgent
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)

setup_tracing("mini-delivery-pilot-agent")
instrument_asyncpg()
instrument_redis()
instrument_httpx()
_agent = MiniDeliveryPilotAgent()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    consumer = asyncio.create_task(_agent.run_consumer(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _agent.close()


app = FastAPI(title="mini-delivery-pilot-agent", lifespan=lifespan)
instrument_fastapi(app, "mini-delivery-pilot-agent")
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "mini-delivery-pilot-agent", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _agent.status()
