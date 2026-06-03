import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from agent import CodeAutoFixAgent, DevelopmentAgent
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)

setup_tracing("development-agent")
instrument_asyncpg()
instrument_redis()
instrument_httpx()
_agent = DevelopmentAgent()
_autofix_agent = CodeAutoFixAgent()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    consumer = asyncio.create_task(_agent.run_consumer(_stop_event))
    autofix_consumer = asyncio.create_task(_autofix_agent.run_consumer(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        consumer.cancel()
        autofix_consumer.cancel()
        await asyncio.gather(consumer, autofix_consumer, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _agent.close()
        with contextlib.suppress(Exception):
            await _autofix_agent.close()


app = FastAPI(title="development-agent", lifespan=lifespan)
instrument_fastapi(app, "development-agent")
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "development-agent", "status": "ok"}


@app.get("/status")
def status() -> dict:
    body = dict(_agent.status())
    body["autofix"] = _autofix_agent.status()
    return body
