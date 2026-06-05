"""Real-integration operator-input snapshot.

Returns booleans + lengths only — never a token value. Used by the
operator-input verify script (``scripts/check_real_integration_inputs.sh``),
the ``/operations/safety`` endpoint's real-integration block, and the
unit tests in ``tests/test_real_integration_inputs.py``.

The function reads a caller-supplied dict (so tests can inject a fake
environment) and falls back to ``os.environ``.
"""

from __future__ import annotations

import os
from typing import Any

DISCORD_INPUTS = (
    "DISCORD_BOT_TOKEN",
    "DISCORD_TEST_GUILD_ID",
    "DISCORD_TEST_CHANNEL_ID",
    "DISCORD_ALLOWED_ROLE_ID",
    "RUN_REAL_DISCORD_TEST",
)
GITHUB_INPUTS = (
    "GITHUB_TOKEN",
    "GITHUB_TEST_REPO",
    "RUN_REAL_GITHUB_TEST",
)


def _snapshot(
    env: dict[str, str], name: str, *, required: bool, opt_in_flag: bool
) -> dict[str, Any]:
    raw = env.get(name, "")
    value = (raw or "").strip()
    present = bool(value)
    info: dict[str, Any] = {
        "name": name,
        "required": required,
        "present": present,
        "length": len(value),
    }
    if opt_in_flag:
        info["opt_in_active"] = value.lower() == "true"
    return info


def collect_real_integration_inputs(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Return a structured snapshot of every real-integration env var.

    The returned dict carries:

    * ``discord`` / ``github`` -- per-variable snapshots
    * ``discord_ready`` / ``github_ready`` -- whether all required +
      opt-in flags are simultaneously true
    * ``no_token_leak`` -- always ``True``; we never copy the value
      into the result. The field is kept as a public assertion.

    The ``DISCORD_ALLOWED_ROLE_ID`` slot is treated as optional (its
    absence does not flip ``discord_ready`` to false) because some test
    guilds rely on per-channel ACLs instead of a role.
    """
    source = env if env is not None else os.environ
    flat = {k: str(v) for k, v in source.items()}

    discord_entries = []
    for name in DISCORD_INPUTS:
        required = name != "DISCORD_ALLOWED_ROLE_ID"
        opt_in = name == "RUN_REAL_DISCORD_TEST"
        discord_entries.append(_snapshot(flat, name, required=required, opt_in_flag=opt_in))
    discord_required_present = all(e["present"] for e in discord_entries if e["required"])
    discord_opt_in = any(e.get("opt_in_active") for e in discord_entries)
    discord_ready = discord_required_present and discord_opt_in

    github_entries = []
    for name in GITHUB_INPUTS:
        opt_in = name == "RUN_REAL_GITHUB_TEST"
        github_entries.append(_snapshot(flat, name, required=True, opt_in_flag=opt_in))
    github_required_present = all(e["present"] for e in github_entries)
    github_opt_in = any(e.get("opt_in_active") for e in github_entries)
    github_ready = github_required_present and github_opt_in

    return {
        "discord": discord_entries,
        "github": github_entries,
        "discord_required_present": discord_required_present,
        "discord_opt_in_active": discord_opt_in,
        "discord_ready": discord_ready,
        "github_required_present": github_required_present,
        "github_opt_in_active": github_opt_in,
        "github_ready": github_ready,
        "no_token_leak": True,
    }
