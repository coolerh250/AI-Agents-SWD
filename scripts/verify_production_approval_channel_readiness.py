#!/usr/bin/env python3
"""Step 63A -- production approval channel readiness verifier.

Marker: PRODUCTION_APPROVAL_CHANNEL_READINESS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "PRODUCTION_APPROVAL_CHANNEL_READINESS_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    a = loaders.load("approval_channel")
    if a.get("sends_external_notification") is not False:
        bad("must not send external notification")
    if a.get("approval_granted") is not False:
        bad("must not treat as approval granted")
    missing = loaders.missing_approval_items()
    if not missing:
        bad("expected approval channel items to be missing")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] approval channel readiness: {len(missing)} items missing; no send/approval")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
