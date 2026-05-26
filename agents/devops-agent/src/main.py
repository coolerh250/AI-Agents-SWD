import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from agent import DevOpsAgent
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)

setup_tracing("devops-agent")
instrument_asyncpg()
instrument_redis()
instrument_httpx()
_agent = DevOpsAgent()
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


app = FastAPI(title="devops-agent", lifespan=lifespan)
instrument_fastapi(app, "devops-agent")
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "devops-agent", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _agent.status()
