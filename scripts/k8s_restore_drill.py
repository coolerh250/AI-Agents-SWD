#!/usr/bin/env python3
"""Step 51.2C2 -- fixed, shell-free Kubernetes restore-drill entrypoint.

Restore is a CRITICAL operation. This wrapper is a controlled, disabled
scaffold: it NEVER restores into a production or source database and performs
NO restore in this stage. The repo's real isolated restore drill is the
host-oriented ``scripts/run_restore_drill.sh`` (restores into
``aiagents_restore_drill_<ts>``); container-native restore is deferred.

Safety:
  * Reuses the repo's tested isolation guard
    (shared.sdk.backup.restore.assert_isolated_restore_db) -- the target DB name
    MUST start with ``aiagents_restore_drill_`` and may never be the primary
    catalog. Source and target must differ.
  * Reads ONLY fixed env vars (separate source/target Secret references) -- no
    shell, no arbitrary command/args, no service-traffic switch.
  * GATED behind ``AIAGENTS_BATCH_EXECUTE=true`` (false everywhere in the
    baseline; restore is never rendered in standard environments). Prints a
    deterministic plan and exits 0 without any database mutation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.sdk.backup.restore import (  # noqa: E402
    DEFAULT_RESTORE_DB_PREFIX,
    assert_isolated_restore_db,
)

SOURCE_DB_ENV = "RESTORE_SOURCE_DATABASE"
TARGET_DB_ENV = "RESTORE_TARGET_DATABASE"


def _execution_enabled() -> bool:
    return str(os.environ.get("AIAGENTS_BATCH_EXECUTE", "false")).strip().lower() == "true"


def main(argv: list[str] | None = None) -> int:
    target = os.environ.get(TARGET_DB_ENV, f"{DEFAULT_RESTORE_DB_PREFIX}scaffold")
    source = os.environ.get(SOURCE_DB_ENV, "aiagents")
    print("isolated-restore-drill entrypoint (controlled disabled scaffold)")
    print(f"required target prefix: {DEFAULT_RESTORE_DB_PREFIX}")
    # Tested isolation guard: forbids aiagents/postgres/templates, requires prefix.
    assert_isolated_restore_db(target)
    if source == target:
        print("ERROR: restore source and target must differ", file=sys.stderr)
        return 2
    if not _execution_enabled():
        print("AIAGENTS_BATCH_EXECUTE != true -> baseline scaffold only; no restore performed")
        return 0
    # Container-native restore pipeline is deferred (host scripts/run_restore_drill.sh).
    print(
        "ERROR: container-native isolated restore is not yet ported; "
        "deferred to cluster smoke (see scripts/run_restore_drill.sh)",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
