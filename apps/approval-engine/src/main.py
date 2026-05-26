import os

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.observability.metrics import install_metrics_endpoint
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_redis,
    setup_tracing,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
APPROVALS_STREAM = "stream.approvals"

setup_tracing("approval-engine")
instrument_asyncpg()
instrument_redis()
app = FastAPI(title="approval-engine")
instrument_fastapi(app, "approval-engine")
install_metrics_endpoint(app)


class ApprovalRequestIn(BaseModel):
    task_id: str
    action: str
    risk_level: str = "unknown"
    reason: str = ""
    requested_by: str = "orchestrator"


class ApprovalDecisionIn(BaseModel):
    request_id: str
    decided_by: str = "operator"


async def _db_conn() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(dsn=DATABASE_URL, timeout=5)
    except Exception as exc:  # surfaced as a 503 to the caller
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


async def _publish(stream: str, event: dict) -> None:
    bus = RedisStreamEventBus()
    try:
        await bus.publish_event(stream, event)
    except Exception:  # stream publish is best-effort
        pass
    finally:
        try:
            await bus.close()
        except Exception:
            pass


def _row_to_approval(row: asyncpg.Record) -> dict:
    return {
        "request_id": str(row["id"]),
        "task_id": row["task_id"],
        "requested_by": row["requested_by"],
        "decided_by": row["decided_by"],
        "action": row["action"],
        "risk_level": row["risk_level"],
        "reason": row["reason"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


_RETURNING = "id, task_id, status, requested_by, decided_by, action, risk_level, reason, created_at"


@app.get("/health")
def health() -> dict:
    return {"service": "approval-engine", "status": "ok"}


@app.post("/approval/request")
async def create_request(payload: ApprovalRequestIn) -> dict:
    conn = await _db_conn()
    try:
        row = await conn.fetchrow(
            "INSERT INTO approval_requests "
            "(task_id, status, requested_by, action, risk_level, reason) "
            "VALUES ($1, 'pending', $2, $3, $4, $5) "
            f"RETURNING {_RETURNING}",
            payload.task_id,
            payload.requested_by,
            payload.action,
            payload.risk_level,
            payload.reason,
        )
    finally:
        await conn.close()
    result = _row_to_approval(row)
    await _publish(APPROVALS_STREAM, {"event": "approval.requested", **result})
    return result


@app.post("/approval/approve")
async def approve(payload: ApprovalDecisionIn) -> dict:
    return await _decide(payload, "approved", "approval.approved")


@app.post("/approval/reject")
async def reject(payload: ApprovalDecisionIn) -> dict:
    return await _decide(payload, "rejected", "approval.rejected")


async def _decide(payload: ApprovalDecisionIn, status: str, event_name: str) -> dict:
    conn = await _db_conn()
    try:
        row = await conn.fetchrow(
            "UPDATE approval_requests "
            "SET status = $2, decided_by = $3, decided_at = now(), updated_at = now() "
            "WHERE id = $1::uuid "
            f"RETURNING {_RETURNING}",
            payload.request_id,
            status,
            payload.decided_by,
        )
    except (asyncpg.PostgresError, ValueError):
        row = None
    finally:
        await conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    result = _row_to_approval(row)
    await _publish(APPROVALS_STREAM, {"event": event_name, **result})
    return result


@app.get("/approval/{request_id}")
async def get_request(request_id: str) -> dict:
    conn = await _db_conn()
    try:
        row = await conn.fetchrow(
            f"SELECT {_RETURNING} FROM approval_requests WHERE id = $1::uuid",
            request_id,
        )
    except (asyncpg.PostgresError, ValueError):
        row = None
    finally:
        await conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return _row_to_approval(row)
