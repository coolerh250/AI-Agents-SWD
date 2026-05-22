import os

import httpx

DEFAULT_APPROVAL_ENGINE_URL = "http://localhost:8002"


class ApprovalHttpClient:
    """HTTP client for the approval-engine service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        resolved = base_url or os.environ.get("APPROVAL_ENGINE_URL", DEFAULT_APPROVAL_ENGINE_URL)
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout

    async def request_approval(
        self,
        task_id: str,
        action: str,
        risk_level: str = "unknown",
        reason: str = "",
        requested_by: str = "orchestrator",
    ) -> dict:
        payload = {
            "task_id": task_id,
            "action": action,
            "risk_level": risk_level,
            "reason": reason,
            "requested_by": requested_by,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/approval/request", json=payload)
            response.raise_for_status()
            return response.json()

    async def approve(self, request_id: str, decided_by: str = "operator") -> dict:
        return await self._decide("approve", request_id, decided_by)

    async def reject(self, request_id: str, decided_by: str = "operator") -> dict:
        return await self._decide("reject", request_id, decided_by)

    async def _decide(self, decision: str, request_id: str, decided_by: str) -> dict:
        payload = {"request_id": request_id, "decided_by": decided_by}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/approval/{decision}", json=payload)
            response.raise_for_status()
            return response.json()

    async def get_approval(self, request_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/approval/{request_id}")
            response.raise_for_status()
            return response.json()
