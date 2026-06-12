"""Stage 40 -- escalation policy store and dry-run runner.

All escalation is DRY_RUN=true. No real pager / Slack / Discord message
is sent. The runner records a lifecycle event and returns a structured
dry-run result.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_jsonb(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except (ValueError, TypeError):
            return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_jsonb_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, list) else []
        except (ValueError, TypeError):
            return []
    if isinstance(value, list):
        return list(value)
    return []


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "policy_id": str(row["policy_id"]),
        "policy_name": row["policy_name"],
        "severity": row["severity"],
        "enabled": bool(row["enabled"]),
        "dry_run": bool(row["dry_run"]),
        "escalation_targets": _parse_jsonb_list(row["escalation_targets"]),
        "escalation_delay_minutes": int(row["escalation_delay_minutes"]),
        "repeat_interval_minutes": int(row["repeat_interval_minutes"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
        "metadata": _parse_jsonb(row["metadata"]),
    }


class EscalationStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def list_policies(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch("SELECT * FROM incident_escalation_policies ORDER BY severity")
        finally:
            await conn.close()
        return [_row_to_dict(r) for r in rows]

    async def get_policy_for_severity(self, severity: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM incident_escalation_policies WHERE severity = $1 AND enabled = true LIMIT 1",
                severity,
            )
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def run_dry_escalation(
        self,
        *,
        incident_id: str,
        severity: str,
        source: str = "alert_receiver",
    ) -> dict[str, Any]:
        """Simulate escalation without sending any real message.

        Returns a structured dry-run result. Always sets
        ``production_executed=false`` and ``real_escalation_sent=false``.
        """
        policy = await self.get_policy_for_severity(severity)
        if policy is None:
            return {
                "escalated": False,
                "dry_run": True,
                "reason": "no_policy_found",
                "severity": severity,
                "incident_id": incident_id,
                "production_executed": False,
                "real_escalation_sent": False,
                "targets": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        targets: list[str] = list(policy["escalation_targets"])
        return {
            "escalated": True,
            "dry_run": True,
            "policy_id": policy["policy_id"],
            "policy_name": policy["policy_name"],
            "severity": severity,
            "incident_id": incident_id,
            "targets": targets,
            "escalation_delay_minutes": policy["escalation_delay_minutes"],
            "repeat_interval_minutes": policy["repeat_interval_minutes"],
            "production_executed": False,
            "real_escalation_sent": False,
            "source": source,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


__all__ = ["EscalationStore"]
