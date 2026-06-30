#!/usr/bin/env python3
"""Step 61 -- backup / restore / DR runtime inventory generator.

Scans ONLY allowlisted runtime roots under ``.runtime/`` and classifies each artifact by
its location / extension. Reports redacted metadata only (path / size / mtime /
classification) -- it NEVER reads file contents, NEVER outputs a secret / token /
kubeconfig / DB dump / Redis dump body, and NEVER deletes anything. Arbitrary paths are not
accepted; only the allowlisted roots are walked.

Output: .runtime/backup-dr/backup-dr-runtime-inventory.json   (gitignored; never committed)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime" / "backup-dr" / "backup-dr-runtime-inventory.json"

# Only these roots are walked. Anything outside is never touched.
ALLOWLISTED_ROOTS = (
    ".runtime/backup-dr",
    ".runtime/tracing",
    ".runtime/build-cache",
    ".runtime/gitops",
    ".runtime/regression",
)


def classify(path: Path) -> str:
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    if "tracing" in parts or name.endswith((".trace", ".otlp")):
        return "temporary_trace"
    if "build-cache" in parts or name.endswith((".cache", ".tsbuildinfo")):
        return "temporary_build_cache"
    if "regression" in parts or "regression" in name:
        return "regression_report"
    if name.endswith((".sql", ".dump", ".pgdump")):
        return "database_dump"
    if name.endswith(".rdb"):
        return "redis_snapshot"
    if "readiness" in name or "dr-report" in name or name.startswith("backup_dr"):
        return "scheduled_dr_report"
    if name.endswith(".json"):
        return "runtime_evidence"
    return "runtime_evidence"


def main() -> int:
    items: list[dict] = []
    total = 0
    for rel in ALLOWLISTED_ROOTS:
        base = ROOT / rel
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            # The output file itself + its sibling reviews are skipped.
            if f.name.startswith(
                (
                    "backup-dr-runtime-inventory",
                    "controlled-cleanup-review",
                    "nonproduction-restore-validation",
                )
            ):
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            size = int(st.st_size)
            total += size
            items.append(
                {
                    "path": f.relative_to(ROOT).as_posix(),
                    "classification": classify(f),
                    "size_bytes": size,
                    "age_days": round((time.time() - st.st_mtime) / 86400, 2),
                }
            )

    inventory = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "allowlisted_roots": list(ALLOWLISTED_ROOTS),
        "item_count": len(items),
        "total_size_bytes": total,
        "items": items,
        "contains_secret": False,
        "contains_raw_dump_body": False,
        "production_executed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"  [OK] backup/restore/DR runtime inventory: {len(items)} items, {total} bytes")
    print(f"  -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
