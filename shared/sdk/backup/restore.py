"""Stage 36 -- restore-drill name/db helpers.

The actual ``pg_restore`` happens in shell (``scripts/run_restore_drill.sh``)
because:

  * The drill must be runnable from operator workstations with no
    Python deps.
  * ``docker compose exec ... pg_restore`` is the canonical contract,
    and shimming it through Python would just add a layer.

This module exposes the *naming convention* + ``isolated_restore_db_name()``
so the restore-drill script and the operations endpoints agree on the
name shape.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

DEFAULT_RESTORE_DB_PREFIX = "aiagents_restore_drill_"

_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
_FORBIDDEN_TARGETS = frozenset({"aiagents", "postgres", "template0", "template1"})


def isolated_restore_db_name(timestamp: str | None = None) -> str:
    """Return a deterministic isolated restore DB name.

    The drill MUST NOT restore into ``aiagents`` (or any other primary
    catalog). If a caller passes a name that violates the prefix
    contract we raise ``ValueError`` so a misconfigured drill cannot
    silently overwrite the live DB.
    """

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{DEFAULT_RESTORE_DB_PREFIX}{timestamp.lower()}"
    assert_isolated_restore_db(name)
    return name


def assert_isolated_restore_db(name: str) -> None:
    if not name:
        raise ValueError("restore DB name cannot be empty")
    if name in _FORBIDDEN_TARGETS:
        raise ValueError(
            f"restore DB name '{name}' is forbidden -- drill must not target the primary catalog"
        )
    if not name.startswith(DEFAULT_RESTORE_DB_PREFIX):
        raise ValueError(
            f"restore DB name '{name}' must start with prefix '{DEFAULT_RESTORE_DB_PREFIX}'"
        )
    if not _SAFE_NAME.match(name):
        raise ValueError(f"restore DB name '{name}' does not match safe identifier pattern")
