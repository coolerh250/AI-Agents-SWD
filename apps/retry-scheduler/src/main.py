import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException

from scheduler import RetryScheduler
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    setup_tracing,
)

setup_tracing("retry-scheduler")
instrument_asyncpg()
instrument_redis()
instrument_httpx()
_scheduler = RetryScheduler()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    consumer = asyncio.create_task(_scheduler.run(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _scheduler.close()


app = FastAPI(title="retry-scheduler", lifespan=lifespan)
instrument_fastapi(app, "retry-scheduler")
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "retry-scheduler", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _scheduler.status()


@app.get("/deadletter")
async def list_deadletter(count: int = 20) -> dict:
    try:
        entries = await _scheduler.list_dead_letters(count=count)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
    return {"count": len(entries), "entries": entries}


@app.post("/deadletter/replay/{message_id}")
async def replay_deadletter(message_id: str) -> dict:
    try:
        return await _scheduler.replay(message_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"deadletter message {message_id} not found"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
