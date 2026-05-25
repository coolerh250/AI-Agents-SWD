import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from agent import QAAgent
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import setup_tracing

setup_tracing("qa-agent")
_agent = QAAgent()
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


app = FastAPI(title="qa-agent", lifespan=lifespan)
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "qa-agent", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _agent.status()
