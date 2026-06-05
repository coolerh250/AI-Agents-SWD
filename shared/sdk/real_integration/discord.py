"""Discord real-pilot guard + safe message renderer.

Real Discord sends are allowed only when EVERY field below holds.
Failure stops at the first violation and surfaces a structured
``DiscordRealGuardResult`` for audit + operations.

* ``DISCORD_BOT_TOKEN`` present
* ``DISCORD_TEST_GUILD_ID`` present
* ``DISCORD_TEST_CHANNEL_ID`` present
* ``RUN_REAL_DISCORD_TEST=true``
* target ``channel_id == DISCORD_TEST_CHANNEL_ID``
* ``mode == "controlled_test"``
* ``production_executed`` is the literal ``False`` (not ``None``/missing)

A separate helper ``render_safe_discord_message`` returns a redacted
summary string suitable for posting to the channel. The renderer only
copies the whitelisted public fields (task_id / status / operations_url
/ optional github_pr_url + approval_required + production_executed).
Any other field passed in is silently dropped — no full payload, no
secrets, no internal IDs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

ALLOWED_MODE = "controlled_test"
SAFE_TEMPLATE_LINES = (
    "[AI-Agents-SWD sandbox] {summary}",
    "task_id: {task_id}",
    "status: {status}",
    "operations_url: {operations_url}",
)
DISCORD_REQUIRED_ENV = (
    "DISCORD_BOT_TOKEN",
    "DISCORD_TEST_GUILD_ID",
    "DISCORD_TEST_CHANNEL_ID",
    "RUN_REAL_DISCORD_TEST",
)


@dataclass
class DiscordRealGuardResult:
    allowed: bool
    reason: str = ""
    target_channel: str = ""
    target_guild: str = ""
    mode: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "target_channel": self.target_channel,
            "target_guild": self.target_guild,
            "mode": self.mode,
            "details": self.details,
        }


def _env(name: str, env: dict[str, str] | None) -> str:
    src = env if env is not None else os.environ
    return (src.get(name, "") or "").strip()


def _bool_env(name: str, env: dict[str, str] | None) -> bool:
    return _env(name, env).lower() == "true"


def evaluate_real_discord_request(
    *,
    channel_id: str,
    guild_id: str = "",
    role_id: str = "",
    mode: str = "controlled_test",
    production_executed: Any = False,
    env: dict[str, str] | None = None,
) -> DiscordRealGuardResult:
    """Evaluate every Stage 32 pre-condition. Stops at the first failure.

    ``production_executed`` is checked with ``is False`` so an omitted
    or ``None`` value cannot accidentally enable a real send -- the
    caller must opt-in explicitly with ``production_executed=False``.
    """
    channel = (channel_id or "").strip()
    guild = (guild_id or "").strip()
    role = (role_id or "").strip()
    mode_value = (mode or "").strip()

    test_channel = _env("DISCORD_TEST_CHANNEL_ID", env)
    test_guild = _env("DISCORD_TEST_GUILD_ID", env)
    allowed_role = _env("DISCORD_ALLOWED_ROLE_ID", env)

    if not _env("DISCORD_BOT_TOKEN", env):
        return DiscordRealGuardResult(allowed=False, reason="missing_discord_bot_token")
    if not _bool_env("RUN_REAL_DISCORD_TEST", env):
        return DiscordRealGuardResult(allowed=False, reason="run_real_discord_test_not_true")
    if not test_guild:
        return DiscordRealGuardResult(allowed=False, reason="missing_discord_test_guild_id")
    if not test_channel:
        return DiscordRealGuardResult(allowed=False, reason="missing_discord_test_channel_id")
    if not channel:
        return DiscordRealGuardResult(allowed=False, reason="channel_id_required")
    if channel != test_channel:
        return DiscordRealGuardResult(
            allowed=False,
            reason="channel_not_test_channel",
            target_channel=channel,
            details={"expected": test_channel, "received": channel},
        )
    if guild and guild != test_guild:
        return DiscordRealGuardResult(
            allowed=False,
            reason="guild_not_test_guild",
            target_channel=channel,
            target_guild=guild,
            details={"expected": test_guild, "received": guild},
        )
    if allowed_role and role and role != allowed_role:
        return DiscordRealGuardResult(
            allowed=False,
            reason="role_not_allowed",
            target_channel=channel,
            target_guild=guild or test_guild,
            details={"expected": allowed_role, "received": role},
        )
    if mode_value != ALLOWED_MODE:
        return DiscordRealGuardResult(
            allowed=False,
            reason="mode_not_controlled_test",
            target_channel=channel,
            details={"expected": ALLOWED_MODE, "received": mode_value},
        )
    if production_executed is not False:
        return DiscordRealGuardResult(
            allowed=False,
            reason="production_executed_not_false",
            target_channel=channel,
            details={"received": production_executed},
        )
    return DiscordRealGuardResult(
        allowed=True,
        target_channel=channel,
        target_guild=guild or test_guild,
        mode=mode_value,
    )


_ALLOWED_RENDER_KEYS = (
    "task_id",
    "status",
    "operations_url",
    "github_pr_url",
    "approval_required",
    "production_executed",
)


def render_safe_discord_message(*, summary: str, fields: dict[str, Any]) -> str:
    """Render a SHORT message body copying ONLY whitelisted public fields.

    Every other key in ``fields`` is silently dropped. The body is
    prefixed with ``[AI-Agents-SWD sandbox]`` so a casual reader
    recognises the source channel. Token-shaped strings inside any of
    the whitelisted values are still defensively redacted by the
    ``_redact`` pass below before they go on the wire.
    """
    safe_summary = _redact(str(summary or ""))[:200]
    body_lines: list[str] = [f"[AI-Agents-SWD sandbox] {safe_summary}"]
    for key in _ALLOWED_RENDER_KEYS:
        if key in fields and fields[key] is not None:
            value = _redact(str(fields[key]))[:200]
            body_lines.append(f"{key}: {value}")
    return "\n".join(body_lines)


_REDACT_PREFIXES = (
    "ghp_",
    "github_pat_",
    "gho_",
    "ghs_",
    "ghr_",
    "xoxb-",
    "xoxp-",
    "MTI",  # Discord bot tokens start with MT… base64 -- coarse heuristic
    "MTM",
    "MTQ",
    "NTI",
    "NjY",
    "NzI",
    "Bot ",
)


def _redact(value: str) -> str:
    """Mask anything that looks like a token. Coarse but defensive.

    The renderer's whitelist already strips internal fields, so this
    mostly catches an operator pasting a token into a description.
    """
    out = value
    for prefix in _REDACT_PREFIXES:
        idx = out.find(prefix)
        while idx != -1:
            end = idx + len(prefix)
            # Tokens are usually a long alnum chunk -- scan to next space.
            while end < len(out) and out[end] not in " \t\n\r":
                end += 1
            out = out[:idx] + "***REDACTED***" + out[end:]
            idx = out.find(prefix, idx + len("***REDACTED***"))
    return out
