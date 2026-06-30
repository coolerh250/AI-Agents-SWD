#!/usr/bin/env python3
"""Step 61 -- backup / restore / DR runtime verifier.

Verifies the host runtime artifacts produced by the generators (inventory / cleanup review
/ restore validation) are well-formed and SAFE: no secret, no raw dump body, no executed
cleanup, no executed restore, no active runtime overwrite / sync / mutation. The artifacts
live under .runtime/ and are never committed.

Marker: BACKUP_RESTORE_DR_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".runtime" / "backup-dr"
INVENTORY = BASE / "backup-dr-runtime-inventory.json"
CLEANUP = BASE / "controlled-cleanup-review.json"
VALIDATION = BASE / "nonproduction-restore-validation-result.json"

MARKER = "BACKUP_RESTORE_DR_RUNTIME_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load(path: Path) -> dict | None:
    if not path.is_file():
        bad(f"missing runtime artifact: {path.relative_to(ROOT).as_posix()}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        bad(f"invalid JSON in {path.name}: {exc}")
        return None


def main() -> int:
    inv = _load(INVENTORY)
    if inv is not None:
        if inv.get("contains_secret") is not False:
            bad("inventory contains_secret must be false")
        if inv.get("contains_raw_dump_body") is not False:
            bad("inventory contains_raw_dump_body must be false")
        if inv.get("production_executed") is not False:
            bad("inventory production_executed must be false")

    cln = _load(CLEANUP)
    if cln is not None and cln.get("cleanup_executed") is not False:
        bad("cleanup review reports cleanup_executed=true")

    val = _load(VALIDATION)
    if val is not None:
        for k in (
            "active_database_overwritten",
            "active_redis_overwritten",
            "argocd_sync_performed",
            "kind_cluster_mutated",
            "production_executed",
        ):
            if val.get(k) is not False:
                bad(f"restore validation {k}=true")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] runtime artifacts: no secret/raw dump; no cleanup/restore execution; no mutation")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
