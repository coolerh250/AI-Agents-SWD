"""Step 66C.4-BE2 -- clarification lifecycle poller entrypoint (NOT activated by BE2).

This entrypoint is deliberately NOT referenced by any compose file, Kubernetes/Helm workload,
systemd/cron unit, or the orchestrator startup. Importing it constructs the FastAPI app and the
poller object but starts NO background task; the poll loop runs only inside the ASGI lifespan when
this app is explicitly served. BE2 does not serve it in any shared runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.tasks.lifecycle_poller import ClarificationLifecyclePoller

_poller = ClarificationLifecyclePoller()
_stop_event = asyncio.Event()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    loop_task = asyncio.create_task(_poller.run(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(loop_task, timeout=_poller.shutdown_timeout_seconds)
        loop_task.cancel()
        await asyncio.gather(loop_task, return_exceptions=True)


app = FastAPI(title="clarification-lifecycle-poller", lifespan=lifespan)
install_metrics_endpoint(app)


@app.get("/health")
def health() -> dict:
    return {"service": "clarification-lifecycle-poller", "status": "ok"}


@app.get("/status")
def status() -> dict:
    return _poller.status()
