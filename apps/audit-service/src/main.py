import json
import os

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
AUDIT_STREAM = "stream.audit"

app = FastAPI(title="audit-service")


class AuditEventIn(BaseModel):
    task_id: str | None = None
    agent: str
    decision_type: str
    summary: str
    result: str
    artifact_refs: dict = Field(default_factory=dict)


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


def _row_to_audit(row: asyncpg.Record) -> dict:
    refs = row["artifact_refs"]
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except (ValueError, TypeError):
            refs = {}
    return {
        "audit_id": str(row["id"]),
        "task_id": row["task_id"],
        "agent": row["agent"],
        "decision_type": row["decision_type"],
        "summary": row["summary"],
        "result": row["result"],
        "artifact_refs": refs,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


_RETURNING = "id, task_id, agent, decision_type, summary, result, artifact_refs, created_at"


@app.get("/health")
def health() -> dict:
    return {"service": "audit-service", "status": "ok"}


@app.post("/audit/events")
async def create_event(payload: AuditEventIn) -> dict:
    conn = await _db_conn()
    try:
        row = await conn.fetchrow(
            "INSERT INTO audit_logs "
            "(task_id, agent, decision_type, summary, result, artifact_refs) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb) "
            f"RETURNING {_RETURNING}",
            payload.task_id,
            payload.agent,
            payload.decision_type,
            payload.summary,
            payload.result,
            json.dumps(payload.artifact_refs),
        )
    finally:
        await conn.close()
    result = _row_to_audit(row)
    await _publish(AUDIT_STREAM, {"event": "audit.recorded", **result})
    return result


@app.get("/audit/events/{task_id}")
async def get_events(task_id: str) -> dict:
    conn = await _db_conn()
    try:
        rows = await conn.fetch(
            f"SELECT {_RETURNING} FROM audit_logs WHERE task_id = $1 ORDER BY created_at",
            task_id,
        )
    finally:
        await conn.close()
    return {
        "task_id": task_id,
        "count": len(rows),
        "events": [_row_to_audit(row) for row in rows],
    }
