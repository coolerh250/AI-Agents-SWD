"""Step AT-M3.3 -- asyncpg store for bounded team discussion.

Persistence only, following the existing store convention (connect per call, ``DATABASE_URL`` from
the environment, plain dict rows) set by ``shared/sdk/agent_team/store.py`` and reused by
``agent_reasoning`` and ``agent_planning``.

Everything that decides WHO SPEAKS NEXT is a database fact, never process memory:

* **The next slot is claimed, not chosen.** ``claim_turn`` is an
  ``INSERT ... ON CONFLICT (discussion_id, round_index, seat_index) DO NOTHING``. Of N workers
  racing the same next turn, exactly one gets a row back; every other learns it lost from
  PostgreSQL rather than from a prior SELECT that could already be stale. This is the same
  execution-ownership shape AT-M3.1 uses for ``correlation_id``, applied one level up.
* **Round advancement and closure are conditional writes.** ``advance_round`` moves the cursor only
  from the round the caller observed, and ``close_session`` closes only a still-open discussion, so
  a duplicated request is a no-op instead of a second effect.
* **A resumed process reconstructs everything by reading.** ``current_round``, the turn ledger and
  the three budget counters are columns. Nothing here caches a cursor.

Messages and threads are NOT owned by this store -- they are ``TeamStore``'s, and the service uses
it for them. The one exception is the thread INSERT inside ``create_session``, which lives here so
the thread and the discussion are created in ONE transaction: a duplicate start that loses the
idempotency race must not leave an orphan thread behind.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_deliberation.models import STATE_FOR_STOP_REASON

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

#: ``deadline_expired`` is computed by PostgreSQL on every read rather than stored, and rather than
#: left for the caller to work out. Two reasons it belongs here and not in the service: the
#: database clock is the only one every worker shares, and a discussion whose expiry depended on
#: whichever host happened to read it would expire at a different instant for each worker -- which
#: is exactly the race a deadline exists to remove.
_SESSION_COLUMNS = """
    discussion_id, project_id, goal_id, plan_revision_id, thread_id, opened_by, topic,
    required_capabilities, max_rounds, max_messages, max_invocations, max_turns_per_participant,
    deadline_at, (now() >= deadline_at) AS deadline_expired,
    current_round, turns_taken, messages_posted, invocations_started, state, stop_reason,
    result_message_id, idempotency_key, audit_ref, created_at, closed_at
"""

_PARTICIPANT_COLUMNS = """
    participant_id, discussion_id, principal_id, agent_key, functional_role,
    matched_capabilities, selection_reason, seat_index, turns_taken, created_at
"""

_TURN_COLUMNS = """
    turn_id, discussion_id, round_index, seat_index, speaker_principal_id,
    addressed_principal_id, addressed_team, intent, reasoning_verb, reasoning_invocation_id,
    message_id, correlation_id, status, concern_count, created_at, completed_at
"""


class _DuplicateStart(Exception):
    """Internal: the idempotency key already exists, so this transaction must roll back."""


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _json_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """asyncpg returns JSONB as text unless a codec is registered; decode the two JSON columns."""
    if row is None:
        return None
    data = dict(row)
    for field in ("required_capabilities", "matched_capabilities"):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = json.loads(value)
    return data


class DeliberationStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- sessions ------------------------------------------------------------------------------

    async def create_session(
        self, data: dict[str, Any], participants: list[dict[str, Any]]
    ) -> tuple[bool, dict[str, Any]]:
        """Open a discussion. Returns ``(created, session)``.

        ``created=False`` means this idempotency key already had a discussion and that one is
        returned unchanged -- a duplicated start request never produces a second deliberation
        talking past the first.

        Thread, session and participants are written in one transaction, so a losing duplicate
        start leaves nothing behind at all.
        """
        conn = await self._connect()
        try:
            try:
                async with conn.transaction():
                    thread_id = await conn.fetchval(
                        """
                        INSERT INTO conversation_threads
                          (project_id, goal_ref, thread_type)
                        VALUES ($1,$2,'planning')
                        RETURNING thread_id
                        """,
                        _uuid_or_none(data["project_id"]),
                        str(data["goal_id"]),
                    )
                    row = await conn.fetchrow(
                        f"""
                        INSERT INTO discussion_sessions
                          (project_id, goal_id, plan_revision_id, thread_id, opened_by, topic,
                           required_capabilities, max_rounds, max_messages, max_invocations,
                           max_turns_per_participant, deadline_at, state, idempotency_key)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,
                                now() + make_interval(secs => $12::double precision),
                                'open',$13)
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING {_SESSION_COLUMNS}
                        """,
                        _uuid_or_none(data["project_id"]),
                        _uuid_or_none(data["goal_id"]),
                        _uuid_or_none(data.get("plan_revision_id")),
                        thread_id,
                        _uuid_or_none(data["opened_by"]),
                        data["topic"],
                        json.dumps(list(data.get("required_capabilities") or [])),
                        data["max_rounds"],
                        data["max_messages"],
                        data["max_invocations"],
                        data["max_turns_per_participant"],
                        float(data["timeout_seconds"]),
                        data["idempotency_key"],
                    )
                    if row is None:
                        raise _DuplicateStart()
                    for participant in participants:
                        await conn.execute(
                            """
                            INSERT INTO discussion_participants
                              (discussion_id, principal_id, agent_key, functional_role,
                               matched_capabilities, selection_reason, seat_index)
                            VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)
                            """,
                            row["discussion_id"],
                            _uuid_or_none(participant["principal_id"]),
                            participant["agent_key"],
                            participant["functional_role"],
                            json.dumps(list(participant.get("matched_capabilities") or [])),
                            participant["selection_reason"],
                            participant["seat_index"],
                        )
            except _DuplicateStart:
                existing = await conn.fetchrow(
                    f"SELECT {_SESSION_COLUMNS} FROM discussion_sessions WHERE idempotency_key=$1",
                    data["idempotency_key"],
                )
                return False, _json_row(existing)  # type: ignore[return-value]
            return True, _json_row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_session(self, discussion_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"SELECT {_SESSION_COLUMNS} FROM discussion_sessions WHERE discussion_id=$1",
                    _uuid_or_none(discussion_id),
                )
            )
        finally:
            await conn.close()

    async def list_sessions_for_goal(self, goal_id: Any, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_SESSION_COLUMNS} FROM discussion_sessions
                WHERE goal_id=$1 ORDER BY created_at LIMIT $2
                """,
                _uuid_or_none(goal_id),
                limit,
            )
            return [_json_row(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def advance_round(self, discussion_id: Any, observed_round: int) -> dict[str, Any] | None:
        """Move the cursor to ``observed_round + 1``, but only from the round the caller saw.

        Conditional so two workers finishing the same round cannot skip one between them.
        Returns ``None`` when someone else already advanced it, which is not an error.
        """
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"""
                    UPDATE discussion_sessions SET current_round=current_round+1, updated_at=now()
                    WHERE discussion_id=$1 AND current_round=$2 AND state='open'
                    RETURNING {_SESSION_COLUMNS}
                    """,
                    _uuid_or_none(discussion_id),
                    observed_round,
                )
            )
        finally:
            await conn.close()

    async def close_session(
        self,
        discussion_id: Any,
        *,
        stop_reason: str,
        result_message_id: Any = None,
        require_open_deadline: bool = False,
    ) -> dict[str, Any] | None:
        """Close an open discussion with a reason. Returns ``None`` if it was already terminal.

        The state is DERIVED from the reason rather than accepted from the caller, so
        ``round_limit_reached`` can never be recorded as ``converged``. Migration 039's
        ``chk_discussion_sessions_reason_matches_state`` enforces the same mapping independently,
        for a caller that bypasses this store.

        Two additional guards, both in the WHERE clause rather than in the caller:

        * ``timeout_reached`` is written only when the DATABASE agrees the deadline has passed. A
          worker that read ``deadline_expired`` a moment ago and a worker whose clock simply runs
          fast are indistinguishable from here, so the claim is re-checked against the same clock
          that produced ``deadline_at``.
        * ``require_open_deadline`` closes only while the deadline has NOT passed, which is what a
          caller wanting to record some other reason needs: once the wall clock is out, the
          discussion's honest reason is the timeout, and no later-arriving verdict may overwrite it.
          Returning ``None`` sends that caller back to re-read and close as a timeout instead.
        """
        state = STATE_FOR_STOP_REASON[stop_reason]
        if stop_reason == "timeout_reached":
            guard = " AND now() >= deadline_at"
        elif require_open_deadline:
            guard = " AND now() < deadline_at"
        else:
            guard = ""
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"""
                    UPDATE discussion_sessions
                       SET state=$2, stop_reason=$3, result_message_id=$4, closed_at=now(),
                           updated_at=now()
                     WHERE discussion_id=$1 AND state='open'{guard}
                    RETURNING {_SESSION_COLUMNS}
                    """,
                    _uuid_or_none(discussion_id),
                    state,
                    stop_reason,
                    _uuid_or_none(result_message_id),
                )
            )
        finally:
            await conn.close()

    async def create_failed_session(
        self, data: dict[str, Any], *, stop_reason: str
    ) -> dict[str, Any]:
        """Open and immediately close a discussion that could never run.

        Used when participant selection fails: the request still produced a durable, queryable
        record saying what was asked for and why nobody could answer it. A start request that
        vanishes because no agent was eligible is exactly the silent failure this avoids.
        """
        state = STATE_FOR_STOP_REASON[stop_reason]
        conn = await self._connect()
        try:
            async with conn.transaction():
                thread_id = await conn.fetchval(
                    """
                    INSERT INTO conversation_threads (project_id, goal_ref, thread_type)
                    VALUES ($1,$2,'planning') RETURNING thread_id
                    """,
                    _uuid_or_none(data["project_id"]),
                    str(data["goal_id"]),
                )
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO discussion_sessions
                      (project_id, goal_id, plan_revision_id, thread_id, opened_by, topic,
                       required_capabilities, max_rounds, max_messages, max_invocations,
                       max_turns_per_participant, deadline_at, state, stop_reason, closed_at,
                       idempotency_key)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,
                            now() + make_interval(secs => $12::double precision),
                            $13,$14,now(),$15)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING {_SESSION_COLUMNS}
                    """,
                    _uuid_or_none(data["project_id"]),
                    _uuid_or_none(data["goal_id"]),
                    _uuid_or_none(data.get("plan_revision_id")),
                    thread_id,
                    _uuid_or_none(data["opened_by"]),
                    data["topic"],
                    json.dumps(list(data.get("required_capabilities") or [])),
                    data["max_rounds"],
                    data["max_messages"],
                    data["max_invocations"],
                    data["max_turns_per_participant"],
                    float(data["timeout_seconds"]),
                    state,
                    stop_reason,
                    data["idempotency_key"],
                )
                if row is None:
                    raise _DuplicateStart()
            return _json_row(row)  # type: ignore[return-value]
        except _DuplicateStart:
            existing = await self.get_session_by_key(data["idempotency_key"])
            return existing  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_session_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"SELECT {_SESSION_COLUMNS} FROM discussion_sessions WHERE idempotency_key=$1",
                    idempotency_key,
                )
            )
        finally:
            await conn.close()

    # --- participants --------------------------------------------------------------------------

    async def list_participants(self, discussion_id: Any) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_PARTICIPANT_COLUMNS} FROM discussion_participants
                WHERE discussion_id=$1 ORDER BY seat_index
                """,
                _uuid_or_none(discussion_id),
            )
            return [_json_row(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    # --- turns ---------------------------------------------------------------------------------

    async def claim_turn(self, data: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        """Atomically claim one turn slot. Returns ``(owned, row)``.

        ``owned=True``: this worker won the slot and MUST proceed to the reasoning call.
        ``owned=False``: someone else holds it; ``row`` is that turn's current state, whatever it
        is. The loser must not invoke a provider -- and could not produce a second canonical reply
        even if it tried, because the turn's correlation id is derived from the same slot and
        AT-M3.1's own UNIQUE constraint would reject it.

        ``ON CONFLICT DO NOTHING`` carries NO arbiter deliberately. Two unique constraints describe
        the same fact here -- the slot, and the correlation id derived from that slot -- so a losing
        racer violates BOTH at once, and which index reports first is not deterministic. Naming
        only the slot index made the loser raise ``uq_discussion_turns_correlation`` instead of
        losing quietly, roughly one race in three. Arbiter-less DO NOTHING covers every unique
        constraint on the table, which is exactly the intent: "somebody already has this turn".
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO discussion_turns
                  (discussion_id, round_index, seat_index, speaker_principal_id,
                   addressed_principal_id, addressed_team, intent, reasoning_verb,
                   correlation_id, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'claimed')
                ON CONFLICT DO NOTHING
                RETURNING {_TURN_COLUMNS}
                """,
                _uuid_or_none(data["discussion_id"]),
                data["round_index"],
                data["seat_index"],
                _uuid_or_none(data["speaker_principal_id"]),
                _uuid_or_none(data.get("addressed_principal_id")),
                bool(data.get("addressed_team", False)),
                data["intent"],
                data["reasoning_verb"],
                _uuid_or_none(data["correlation_id"]),
            )
            if row is not None:
                return True, dict(row)
            existing = await conn.fetchrow(
                f"""
                SELECT {_TURN_COLUMNS} FROM discussion_turns
                WHERE discussion_id=$1 AND round_index=$2 AND seat_index=$3
                """,
                _uuid_or_none(data["discussion_id"]),
                data["round_index"],
                data["seat_index"],
            )
            return False, dict(existing) if existing else None
        finally:
            await conn.close()

    async def complete_turn(
        self,
        turn_id: Any,
        *,
        intent: str,
        concern_count: int,
        message_id: Any,
        reasoning_invocation_id: Any,
        discussion_id: Any,
        seat_index: int,
    ) -> dict[str, Any] | None:
        """Record what a claimed turn produced, and charge it to every budget, atomically.

        The turn row, the session's three counters and the participant's own turn count move
        together or not at all: a crash between them would leave a discussion whose budget says
        it spoke fewer times than its ledger shows.
        """
        conn = await self._connect()
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"""
                    UPDATE discussion_turns
                       SET status='recorded', intent=$2, concern_count=$3, message_id=$4,
                           reasoning_invocation_id=$5, completed_at=now()
                     WHERE turn_id=$1 AND status='claimed'
                    RETURNING {_TURN_COLUMNS}
                    """,
                    _uuid_or_none(turn_id),
                    intent,
                    concern_count,
                    _uuid_or_none(message_id),
                    _uuid_or_none(reasoning_invocation_id),
                )
                if row is None:
                    return None
                await conn.execute(
                    """
                    UPDATE discussion_sessions
                       SET turns_taken=turns_taken+1, messages_posted=messages_posted+1,
                           invocations_started=invocations_started+1, updated_at=now()
                     WHERE discussion_id=$1 AND state='open'
                    """,
                    _uuid_or_none(discussion_id),
                )
                await conn.execute(
                    """
                    UPDATE discussion_participants SET turns_taken=turns_taken+1
                     WHERE discussion_id=$1 AND seat_index=$2
                    """,
                    _uuid_or_none(discussion_id),
                    seat_index,
                )
            return dict(row)
        finally:
            await conn.close()

    async def fail_turn(
        self, turn_id: Any, *, reasoning_invocation_id: Any = None
    ) -> dict[str, Any] | None:
        """Mark a claimed turn failed. Returns ``None`` if it was no longer claimed.

        Guarded by ``status='claimed'`` for the same reason ``complete_turn`` is: a turn that
        already produced a message must never be rewritten into a failure.
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE discussion_turns
                   SET status='failed',
                       reasoning_invocation_id=COALESCE($2, reasoning_invocation_id),
                       completed_at=now()
                 WHERE turn_id=$1 AND status='claimed'
                RETURNING {_TURN_COLUMNS}
                """,
                _uuid_or_none(turn_id),
                _uuid_or_none(reasoning_invocation_id),
            )
            return dict(row) if row is not None else None
        finally:
            await conn.close()

    async def list_turns(
        self, discussion_id: Any, round_index: int | None = None
    ) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            if round_index is None:
                rows = await conn.fetch(
                    f"""
                    SELECT {_TURN_COLUMNS} FROM discussion_turns
                    WHERE discussion_id=$1 ORDER BY round_index, seat_index
                    """,
                    _uuid_or_none(discussion_id),
                )
            else:
                rows = await conn.fetch(
                    f"""
                    SELECT {_TURN_COLUMNS} FROM discussion_turns
                    WHERE discussion_id=$1 AND round_index=$2 ORDER BY seat_index
                    """,
                    _uuid_or_none(discussion_id),
                    round_index,
                )
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def invocation_status(self, correlation_id: Any) -> str | None:
        """The AT-M3.1 invocation status for a turn's derived correlation id, if any exists.

        Read, never written, by this store: ``reasoning_invocations`` belongs to AT-M3.1. It is
        what tells a resumed process whether a claimed turn's provider call never started (safe to
        retry under the same correlation id), is still running (someone else owns it), or already
        reached a terminal outcome whose artifact is gone (unresolvable -- fail closed).
        """
        conn = await self._connect()
        try:
            return await conn.fetchval(
                "SELECT status FROM reasoning_invocations WHERE correlation_id=$1",
                _uuid_or_none(correlation_id),
            )
        finally:
            await conn.close()


__all__ = ["DEFAULT_DATABASE_URL", "DeliberationStore"]
