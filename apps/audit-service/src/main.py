import json
import os

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.audit_integrity import (
    AuditSigner,
    SIGNATURE_STATUS_NOT_CONFIGURED,
    create_integrity_record_in_txn,
)
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.observability.metrics import (
    AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL,
    AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL,
    install_metrics_endpoint,
)
from shared.sdk.observability.tracing import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_redis,
    setup_tracing,
    start_span,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
AUDIT_STREAM = "stream.audit"

setup_tracing("audit-service")
instrument_asyncpg()
instrument_redis()
app = FastAPI(title="audit-service")
instrument_fastapi(app, "audit-service")
install_metrics_endpoint(app)

# A module-level signer is fine -- the signer holds only the keyring
# snapshot built at process start. Key rotation is operational (restart
# the service after rotating the keyring env). We never expose the
# signer or its keyring through the API.
_SIGNER = AuditSigner()


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


@app.get("/audit/keyring/status")
def keyring_status() -> dict:
    """Operational read-only view of which keyring the service loaded.

    Never returns key bytes. Used by smokes and operators to confirm
    that the running service sees the keyring they expect.
    """
    snapshot = _SIGNER.keyring.snapshot().to_safe_dict()
    return {
        "service": "audit-service",
        **snapshot,
        "direct_post_integrity_enabled": True,
    }


@app.post("/audit/events")
async def create_event(payload: AuditEventIn) -> dict:
    """Insert an audit_logs row AND its integrity record atomically.

    Stage 39: direct POST and the stream/worker path now share the
    same integrity writer. On any integrity-write failure the whole
    transaction is rolled back -- the caller must retry. We never
    return 200 with a missing integrity record.
    """
    conn = await _db_conn()
    integrity_status_label = "unknown"
    try:
        async with conn.transaction():
            with start_span(
                "audit_integrity.direct_post_create",
                **{
                    "service.name": "audit-service",
                    "agent": "audit-service",
                },
            ):
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
                result = _row_to_audit(row)
                try:
                    integrity = await create_integrity_record_in_txn(
                        conn,
                        audit_log_row={
                            "audit_log_id": result["audit_id"],
                            "task_id": result["task_id"],
                            "agent": result["agent"],
                            "decision_type": result["decision_type"],
                            "summary": result["summary"],
                            "result": result["result"],
                            "artifact_refs": result["artifact_refs"],
                            "created_at": row["created_at"],
                        },
                        signer=_SIGNER,
                    )
                except Exception as exc:
                    AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL.labels(
                        reason=exc.__class__.__name__
                    ).inc()
                    # Transaction rolls back on the raise -- audit_logs row
                    # is NOT persisted, so no orphan ever lands.
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "audit integrity write failed; transaction "
                            f"rolled back: {exc.__class__.__name__}"
                        ),
                    ) from exc
                if integrity is None:
                    # An earlier write created this row's integrity. Treat
                    # as success for idempotent re-tries.
                    integrity_status_label = "idempotent_replay"
                else:
                    integrity_status_label = (
                        "signing_key_not_configured"
                        if integrity.signature_status == SIGNATURE_STATUS_NOT_CONFIGURED
                        else integrity.signature_status
                    )
    except HTTPException:
        raise
    except Exception as exc:
        AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL.labels(reason=exc.__class__.__name__).inc()
        raise HTTPException(
            status_code=503,
            detail=f"audit write failed: {exc.__class__.__name__}",
        ) from exc
    finally:
        await conn.close()

    AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL.labels(status=integrity_status_label).inc()
    await _publish(AUDIT_STREAM, {"event": "audit.recorded", **result})
    return {
        **result,
        "audit_integrity_status": integrity_status_label,
        "audit_integrity_created": integrity_status_label != "idempotent_replay",
    }


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


@app.get("/audit/events")
async def list_events(
    task_id: str | None = None,
    agent: str | None = None,
    decision_type: str | None = None,
    limit: int = 100,
) -> dict:
    """Query audit_logs by any combination of filters."""
    clauses: list[str] = []
    params: list = []
    if task_id:
        params.append(task_id)
        clauses.append(f"task_id = ${len(params)}")
    if agent:
        params.append(agent)
        clauses.append(f"agent = ${len(params)}")
    if decision_type:
        params.append(decision_type)
        clauses.append(f"decision_type = ${len(params)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(int(limit or 100), 500)))
    sql = (
        f"SELECT {_RETURNING} FROM audit_logs "
        f"{where} ORDER BY created_at DESC LIMIT ${len(params)}"
    )
    conn = await _db_conn()
    try:
        rows = await conn.fetch(sql, *params)
    finally:
        await conn.close()
    return {
        "count": len(rows),
        "events": [_row_to_audit(row) for row in rows],
    }
