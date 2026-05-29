"""Opt-in Discord client used only when controlled real delivery is enabled.

Gate is identical to the Stage 21 ``discord-gateway`` client: every real-API
call requires all three of:

* ``DISCORD_BOT_TOKEN`` non-empty,
* ``DISCORD_TEST_CHANNEL_ID`` non-empty,
* ``RUN_REAL_DISCORD_TEST`` == "true".

The token value is read at call time, used only in the ``Authorization``
header, and is never logged, never echoed in any response, never written to
any artifact. The client refuses to send to any channel other than
``DISCORD_TEST_CHANNEL_ID`` so a misconfigured caller can't smuggle a
notification to an unintended audience. The body is always prefixed with
``[AI-Agents-SWD sandbox]``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordDeliverySafetyError(RuntimeError):
    """Raised when a real-delivery pre-condition isn't met."""


class NotificationDiscordClient:
    """Sandbox-by-default Discord client for the notification worker."""

    def __init__(
        self,
        token: str | None = None,
        *,
        test_channel_id: str | None = None,
        real_enabled: bool | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._token = (
            token if token is not None else os.environ.get("DISCORD_BOT_TOKEN", "")
        ).strip()
        self._channel_id = (
            test_channel_id
            if test_channel_id is not None
            else os.environ.get("DISCORD_TEST_CHANNEL_ID", "")
        ).strip()
        if real_enabled is None:
            real_enabled = (
                os.environ.get("RUN_REAL_DISCORD_TEST", "false").strip().lower() == "true"
            )
        self._real_enabled = bool(real_enabled)
        self._timeout = timeout

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    @property
    def has_test_channel(self) -> bool:
        return bool(self._channel_id)

    @property
    def real_enabled(self) -> bool:
        return self._real_enabled

    @property
    def test_channel_id(self) -> str:
        return self._channel_id

    def can_deliver(self) -> bool:
        return self.has_token and self.has_test_channel and self.real_enabled

    async def send_test_message(self, content: str) -> dict[str, Any]:
        """Send ONE sandbox test message to ``DISCORD_TEST_CHANNEL_ID``.

        Raises ``DiscordDeliverySafetyError`` if any of the three opt-in
        pre-conditions is missing.
        """
        if not self.has_token:
            raise DiscordDeliverySafetyError("DISCORD_BOT_TOKEN is not set")
        if not self.has_test_channel:
            raise DiscordDeliverySafetyError("DISCORD_TEST_CHANNEL_ID is not set")
        if not self.real_enabled:
            raise DiscordDeliverySafetyError("RUN_REAL_DISCORD_TEST is not 'true'")
        url = f"{DISCORD_API_BASE}/channels/{self._channel_id}/messages"
        body = {"content": f"[AI-Agents-SWD sandbox] {content}"}
        headers = {"Authorization": f"Bot {self._token}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
        return {
            "message_id": str(data.get("id", "")),
            "channel_id": str(data.get("channel_id", self._channel_id)),
        }
