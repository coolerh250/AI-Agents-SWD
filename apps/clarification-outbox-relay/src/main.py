"""Step 66C.4-BE2 -- clarification outbox relay entrypoint (NOT activated by BE2).

This entrypoint is deliberately NOT referenced by any compose file, Kubernetes/Helm workload,
systemd/cron unit, or the orchestrator startup. Importing it constructs the FastAPI app and the
relay object but starts NO background task; the relay loop runs only inside the ASGI lifespan when
this app is explicitly served. BE2 does not serve it in any shared runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.tasks.outbox_relay import ClarificationOutboxRelay

_relay = ClarificationOutboxRelay()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    loop_task = asyncio.create_task(_relay.run(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(loop_task, timeout=_relay.shutdown_timeout_seconds)
        loop_task.cancel()
        await asyncio.gather(loop_task, return_exceptions=True)
        with contextlib.suppress(Exception):
            await _relay.close()


app = FastAPI(title="clarification-outbox-relay", lifespan=lifespan)
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "clarification-outbox-relay", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _relay.status()
