#!/usr/bin/env python3
"""Step 61 -- controlled cleanup review generator.

Reads the runtime inventory and builds a cleanup review via the SDK. It marks each
candidate allowed / requires_approval / blocked by classification + path allowlist. It
NEVER deletes anything (cleanup_executed is always false), NEVER tears down kind / ArgoCD,
and NEVER touches an active DB / Redis. If disk pressure is detected it only RECOMMENDS an
operator action.

Output: .runtime/backup-dr/controlled-cleanup-review.json   (gitignored; never committed)
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import build_cleanup_review  # noqa: E402

INVENTORY = ROOT / ".runtime" / "backup-dr" / "backup-dr-runtime-inventory.json"
OUT = ROOT / ".runtime" / "backup-dr" / "controlled-cleanup-review.json"


def main() -> int:
    if not INVENTORY.is_file():
        print(
            f"  [FAIL] runtime inventory missing: {INVENTORY.as_posix()} (run the generator first)"
        )
        return 1
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    candidates = [
        {
            "path": it.get("path", ""),
            "classification": it.get("classification", ""),
            "size_bytes": it.get("size_bytes", 0),
        }
        for it in inv.get("items", [])
    ]

    review = build_cleanup_review(scope="runtime_artifacts", candidates=candidates)
    out = review.to_dict()

    # Disk-pressure RECOMMENDATION only -- never an automatic execution.
    usage = shutil.disk_usage(str(ROOT))
    pct_used = round(usage.used / usage.total * 100, 1)
    out["disk_percent_used"] = pct_used
    out["recommend_operator_cleanup"] = pct_used >= 85.0
    out["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out["cleanup_executed"] = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"  [OK] cleanup review: allowed={out['allowed_count']} "
        f"requires_approval={out['requires_approval_count']} blocked={out['blocked_count']} "
        f"risk={out['risk_level']} disk_used={pct_used}% (cleanup NOT executed)"
    )
    print(f"  -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
