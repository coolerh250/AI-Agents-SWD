import os

import httpx

DEFAULT_AUDIT_SERVICE_URL = "http://localhost:8003"


class AuditHttpClient:
    """HTTP client for the audit-service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        resolved = base_url or os.environ.get("AUDIT_SERVICE_URL", DEFAULT_AUDIT_SERVICE_URL)
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout

    async def record_event(
        self,
        task_id: str,
        agent: str,
        decision_type: str,
        summary: str,
        result: str,
        artifact_refs: dict | None = None,
    ) -> dict:
        payload = {
            "task_id": task_id,
            "agent": agent,
            "decision_type": decision_type,
            "summary": summary,
            "result": result,
            "artifact_refs": artifact_refs or {},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/audit/events", json=payload)
            response.raise_for_status()
            return response.json()

    async def get_events(self, task_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/audit/events/{task_id}")
            response.raise_for_status()
            return response.json()
