import os

import httpx

DEFAULT_POLICY_ENGINE_URL = "http://localhost:8001"


class PolicyHttpClient:
    """HTTP client for the policy-engine service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        resolved = base_url or os.environ.get("POLICY_ENGINE_URL", DEFAULT_POLICY_ENGINE_URL)
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout

    async def evaluate(self, action: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/policy/evaluate", json={"action": action}
            )
            response.raise_for_status()
            return response.json()
