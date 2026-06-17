#!/usr/bin/env python3
"""Step 51.2C2 -- fixed, shell-free Kubernetes encrypted-backup entrypoint.

Container-native baseline for the backup CronJob. The repo's real encrypted
backup is the host-oriented ``scripts/run_encrypted_backup.sh`` (pg_dump +
openssl + manifest); orchestration/recording lives in
``shared.sdk.backup_dr.cli``. A container-native pg_dump pipeline is NOT yet
ported -- that is a deferred cluster-smoke concern.

This wrapper performs NO backup in this stage. It:
  * reads ONLY fixed env vars (``DATABASE_URL`` + ``BACKUP_ENCRYPTION_KEY`` via
    Secret references) -- no shell, no arbitrary command/args,
  * validates the controlled-only safety invariants + that the encryption key
    is supplied via a Secret reference (never a raw inline value),
  * is GATED behind ``AIAGENTS_BATCH_EXECUTE=true`` (false everywhere in the
    baseline; the CronJob is suspended), so it prints a deterministic plan and
    exits 0 without touching the database or any artifact target.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.sdk.backup.encryption import resolve_encryption_key_source  # noqa: E402
from shared.sdk.backup_dr.safety import backup_dr_enabled  # noqa: E402


def _execution_enabled() -> bool:
    return str(os.environ.get("AIAGENTS_BATCH_EXECUTE", "false")).strip().lower() == "true"


def main(argv: list[str] | None = None) -> int:
    print("encrypted-backup entrypoint (container-native baseline)")
    # Encryption key is referenced, never inlined: resolve only the *source*.
    enc = resolve_encryption_key_source()
    print(f"encryption key source: {enc.key_source}; controlled_only={backup_dr_enabled()}")
    if not _execution_enabled():
        print("AIAGENTS_BATCH_EXECUTE != true -> baseline plan only; no backup performed")
        return 0
    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required (Secret reference)", file=sys.stderr)
        return 2
    # Container-native pg_dump pipeline is deferred (host scripts/run_encrypted_backup.sh).
    print(
        "ERROR: container-native encrypted backup is not yet ported; "
        "deferred to cluster smoke (see scripts/run_encrypted_backup.sh)",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
