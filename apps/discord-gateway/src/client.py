"""Discord API client used only for the opt-in sandbox-real test.

Default behaviour: this client refuses every operation. It only contacts
``discord.com`` when **all** of:

* ``DISCORD_BOT_TOKEN`` is set (non-empty),
* ``RUN_REAL_DISCORD_TEST`` is ``true``,
* a target ``channel_id`` is supplied,

are true. Even then it only POSTs one text message — no message reads,
no slash-command registration, no member lookups, no edits. The token
value is read at call time, used in the ``Authorization`` header, and
otherwise never logged, echoed, or returned.

The rest of the gateway is sandbox-only and uses
``parser.parse_discord_message`` to turn inbound text into intake
payloads without touching this client.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from shared.sdk.secrets import EnvSecretProvider, SecretRef, default_provider

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordSafetyError(RuntimeError):
    """Raised when the opt-in real-Discord pre-conditions are not met."""


class DiscordClient:
    """Thin opt-in client. Default mode is sandbox (`_real_test_enabled` is False).

    Stage 24: the token is held in a :class:`SecretRef` so accidental
    serialisation of the client (vars / repr / logging) renders the
    token as ``***REDACTED***`` instead of leaking the value.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        real_test_enabled: bool | None = None,
        timeout: float = 10.0,
    ) -> None:
        if token is not None:
            # Test path — wrap whatever the caller passed in a SecretRef
            # using a one-shot EnvSecretProvider over a {token: value}
            # dict so placeholder values still register as "not present".
            stripped = token.strip()
            provider = EnvSecretProvider({"DISCORD_BOT_TOKEN": stripped})
            self._token_ref: SecretRef = provider.get_secret("DISCORD_BOT_TOKEN")
        else:
            self._token_ref = default_provider().get_secret("DISCORD_BOT_TOKEN")
        if real_test_enabled is None:
            real_test_enabled = (
                os.environ.get("RUN_REAL_DISCORD_TEST", "false").strip().lower() == "true"
            )
        self._real_test_enabled = bool(real_test_enabled)
        self._timeout = timeout

    @property
    def has_token(self) -> bool:
        return self._token_ref.present

    @property
    def real_test_enabled(self) -> bool:
        return bool(self._real_test_enabled)

    def can_make_real_call(self) -> bool:
        return self.has_token and self.real_test_enabled

    async def post_sandbox_test_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """Send ONE text message to ``channel_id``. Hard-gated by both env vars.

        Returns a dict ``{"message_id": "...", "channel_id": "..."}`` on
        success. The Discord ``content`` is prefixed with
        ``[AI-Agents-SWD sandbox]`` so a casual reader can identify it.
        The token value never appears in the return body.
        """
        if not self.has_token:
            raise DiscordSafetyError("DISCORD_BOT_TOKEN is not set")
        if not self.real_test_enabled:
            raise DiscordSafetyError("RUN_REAL_DISCORD_TEST is not 'true'")
        if not channel_id:
            raise DiscordSafetyError("channel_id is required")
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        body = {"content": f"[AI-Agents-SWD sandbox] {content}"}
        headers = {"Authorization": f"Bot {self._token_ref.reveal()}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
        return {
            "message_id": str(data.get("id", "")),
            "channel_id": str(data.get("channel_id", channel_id)),
        }
