#!/usr/bin/env python3
"""Step 54.3 -- container image inventory verifier.

Marker: CONTAINER_IMAGE_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-image-inventory.yaml"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not F.is_file():
        bad(f"missing {F}")
        print("CONTAINER_IMAGE_INVENTORY_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    images = data.get("images", [])
    if not images:
        bad("no images inventoried")
        print("CONTAINER_IMAGE_INVENTORY_VERIFY: FAIL")
        return 1
    ok(f"container image inventory present with {len(images)} images")

    sources = {s for img in images for s in (img.get("usedIn") or [])}
    if not {"compose", "helm", "job"} <= sources:
        bad(f"compose/helm/job images not all covered: {sources}")
    else:
        ok("compose / Helm / job images covered")

    for img in images:
        for field in ("digest", "digestPinned", "tag", "latestTag", "firstParty"):
            if field not in img:
                bad(f"image {img.get('key')} missing field {field}")
    if not [f for f in failures if "missing field" in f]:
        ok("digest + tag + first-party status recorded per image")

    if not any(i.get("firstParty") for i in images) or not any(
        not i.get("firstParty") for i in images
    ):
        bad("first-party / third-party not both classified")
    else:
        ok("first-party + third-party images classified")

    if not any(i.get("blockers") for i in images):
        bad("no blockers recorded (expected digest gaps)")
    else:
        ok("blockers recorded (digest / placeholder / root gaps)")

    # honesty: with empty digests, none may claim digestPinned
    if any(i.get("digestPinned") and not i.get("digest") for i in images):
        bad("an image claims digestPinned with empty digest")
    else:
        ok("no image falsely claims digest pinned")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("CONTAINER_IMAGE_INVENTORY_VERIFY: FAIL")
        return 1
    print("CONTAINER_IMAGE_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
