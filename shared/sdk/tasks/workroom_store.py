"""Step 66C.1 -- asyncpg store for task_messages / operator_clarification_requests.

No production action; no workflow dispatch or resume is ever triggered from
here. Message/question/answer bodies are stored as opaque TEXT -- never parsed,
rendered, or executed.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from shared.sdk.tasks.store import DEFAULT_DATABASE_URL
from shared.sdk.tasks.workroom_models import CLARIFICATION_DUE_HOURS, CLARIFICATION_REMINDER_HOURS


class WorkroomStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_message(
        self,
        *,
        task_id: str,
        sender_type: str,
        sender_id: str,
        sender_role: str | None,
        message_type: str,
        body: str,
        visibility: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO task_messages
                  (task_id, sender_type, sender_id, sender_role, message_type, body, visibility,
                   reply_to_message_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING *
                """,
                uuid.UUID(task_id),
                sender_type,
                sender_id,
                sender_role,
                message_type,
                body,
                visibility,
                uuid.UUID(reply_to_message_id) if reply_to_message_id else None,
            )
            return self._msg_row(row)
        finally:
            await conn.close()

    async def list_messages(self, task_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM task_messages WHERE task_id=$1 ORDER BY created_at ASC",
                uuid.UUID(task_id),
            )
            return [self._msg_row(r) for r in rows]
        finally:
            await conn.close()

    async def create_clarification(
        self,
        *,
        task_id: str,
        question_message_id: str,
        question: str,
        requested_by_type: str,
        requested_by_id: str,
        assigned_to: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        due_at = now + timedelta(hours=CLARIFICATION_DUE_HOURS)
        reminder_at = now + timedelta(hours=CLARIFICATION_REMINDER_HOURS)
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO operator_clarification_requests
                  (task_id, question_message_id, question, requested_by_type, requested_by_id,
                   assigned_to, due_at, reminder_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING *
                """,
                uuid.UUID(task_id),
                uuid.UUID(question_message_id),
                question,
                requested_by_type,
                requested_by_id,
                assigned_to,
                due_at,
                reminder_at,
            )
            return self._clar_row(row)
        finally:
            await conn.close()

    async def list_clarifications(self, task_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM operator_clarification_requests WHERE task_id=$1 ORDER BY created_at ASC",
                uuid.UUID(task_id),
            )
            return [self._clar_row(r) for r in rows]
        finally:
            await conn.close()

    async def get_clarification(self, clarification_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(clarification_id),
            )
            return self._clar_row(row) if row else None
        finally:
            await conn.close()

    async def claim_clarification_answer(self, clarification_id: str) -> dict[str, Any] | None:
        """Step 66C.3 (G5) + Step 66C.4-BE1 -- atomically transition open -> answered,
        with the authoritative expiry deadline enforced by the same CAS.

        The WHERE clause is what makes this race-safe: concurrent answer attempts on the
        same clarification will only ever have exactly one UPDATE match a row (Postgres
        row-level locking serializes the two UPDATEs). The loser gets `None` back and must
        not create an answer message or emit a `clarification_answered` audit event -- see
        `answer_clarification` in workroom_api.py, which calls this BEFORE creating the
        answer message so a lost race never has a message/audit side effect.

        Step 66C.4-BE1 adds the authoritative-deadline predicate, corrected in Step
        66C.4-BE1-R1 to `due_at > statement_timestamp()`: due_at is an EXCLUSIVE upper bound,
        so an answer submitted at or after due_at matches zero rows and returns None, EVEN
        WHEN status is still 'open' (i.e. before the future timeout worker has materialized
        'expired'). Scheduler lag therefore cannot extend the answer window (canonical
        lifecycle-and-time-contract.md 7.3A). This claim writes NO outbox row and triggers NO
        scheduler/event/notification on either success or failure.

        Clock function (BINDING -- do not change back): `statement_timestamp()`, never `now()`
        or `transaction_timestamp()`. The latter two return the TRANSACTION START time and stay
        frozen for the whole transaction, so a transaction that began before due_at could claim
        after due_at and would backdate answered_at to the transaction start. Today this call
        runs in its own single-statement autocommit transaction, where the difference is not
        observable -- but the binding atomicity model (api-and-event-contract.md 11.3) requires
        BE2 to wrap this CAS together with an outbox INSERT in ONE transaction, which is exactly
        the shape that would activate the defect. statement_timestamp() is constant within one
        statement, so the deadline comparison and the answered_at write share one reading; that
        is why it is preferred over clock_timestamp() here.
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE operator_clarification_requests
                SET status='answered',
                    answered_at=statement_timestamp(),
                    updated_at=statement_timestamp()
                WHERE id=$1 AND status='open' AND answered_at IS NULL
                  AND due_at > statement_timestamp()
                RETURNING *
                """,
                uuid.UUID(clarification_id),
            )
            return self._clar_row(row) if row else None
        finally:
            await conn.close()

    async def set_answer_message(
        self, clarification_id: str, *, answer_message_id: str
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE operator_clarification_requests
                SET answer_message_id=$2, updated_at=now()
                WHERE id=$1
                RETURNING *
                """,
                uuid.UUID(clarification_id),
                uuid.UUID(answer_message_id),
            )
            return self._clar_row(row)
        finally:
            await conn.close()

    @staticmethod
    def _msg_row(row: asyncpg.Record) -> dict[str, Any]:
        d = dict(row)
        for key in ("id", "task_id", "correlation_id", "reply_to_message_id"):
            if d.get(key) is not None:
                d[key] = str(d[key])
        for key in ("created_at", "updated_at"):
            if d.get(key) is not None:
                d[key] = d[key].isoformat()
        return d

    @staticmethod
    def _clar_row(row: asyncpg.Record) -> dict[str, Any]:
        d = dict(row)
        for key in ("id", "task_id", "question_message_id", "answer_message_id"):
            if d.get(key) is not None:
                d[key] = str(d[key])
        for key in (
            "due_at",
            "reminder_at",
            "answered_at",
            "created_at",
            "updated_at",
            # Step 66C.4-BE1 additive lifecycle timestamps (nullable; NULL until reached).
            "reminder_sent_at",
            "expired_at",
            "resume_eligible_at",
            "resume_requested_at",
            "resume_authorized_at",
        ):
            if d.get(key) is not None:
                d[key] = d[key].isoformat()
        return d


__all__ = ["WorkroomStore"]
