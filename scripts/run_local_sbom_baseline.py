#!/usr/bin/env python3
"""Step 54.3 -- local SBOM baseline runner (local-only, no network, no registry).

Builds an internal manifest-based SBOM baseline from local manifests
(requirements.txt, package.json/package-lock.json) + container image refs
(Dockerfile base images, container-image-inventory). It does NOT pull images, log
into a registry, resolve transitive trees, or upload anything. The custom baseline
is LIMITED -- it is NOT a production SBOM. Output written to a runtime path
(NEVER committed).

Exit: 0 = generated; 2 = config error.

Usage: python scripts/run_local_sbom_baseline.py [--json-report PATH] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

GENERATOR = "custom_manifest_sbom"
DEFAULT_REPORT = ROOT / ".runtime" / "security" / "sbom" / "local-sbom-baseline.json"
_REQ = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _python_components() -> tuple[list[dict], list[str], bool]:
    comps: list[dict] = []
    files: list[str] = []
    for rf in sorted(ROOT.rglob("requirements.txt")):
        if ".venv" in rf.parts or "node_modules" in rf.parts:
            continue
        rel = rf.relative_to(ROOT).as_posix()
        files.append(rel)
        for line in rf.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            m = _REQ.match(s)
            if m:
                pinned = bool(re.search(r"(==|>=|<=|~=)", s))
                comps.append(
                    {"type": "python", "name": m.group(1), "version_pinned": pinned, "source": rel}
                )
    py_lock = any((ROOT / f).exists() for f in ("requirements.lock", "poetry.lock", "Pipfile.lock"))
    return comps, files, py_lock


def _node_components() -> tuple[list[dict], list[str], bool]:
    comps: list[dict] = []
    files: list[str] = []
    pkg = ROOT / "apps" / "admin-console" / "package.json"
    lock = ROOT / "apps" / "admin-console" / "package-lock.json"
    if pkg.is_file():
        files.append(pkg.relative_to(ROOT).as_posix())
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        for sect in ("dependencies", "devDependencies"):
            for name, ver in (data.get(sect) or {}).items():
                comps.append(
                    {
                        "type": "node",
                        "name": name,
                        "version": ver,
                        "dev": sect == "devDependencies",
                        "source": "package.json",
                    }
                )
    if lock.is_file():
        files.append(lock.relative_to(ROOT).as_posix())
    return comps, files, lock.is_file()


def _image_components() -> tuple[list[dict], list[str], bool]:
    inv = ROOT / "infra" / "security" / "container-image-inventory.yaml"
    comps: list[dict] = []
    refs: list[str] = []
    any_digest = False
    if inv.is_file():
        data = yaml.safe_load(inv.read_text(encoding="utf-8")) or {}
        for img in data.get("images", []):
            refs.append(img.get("image", ""))
            any_digest = any_digest or bool(img.get("digestPinned"))
            comps.append(
                {
                    "type": "container_image",
                    "name": img.get("repository"),
                    "tag": img.get("tag"),
                    "digest_pinned": bool(img.get("digestPinned")),
                    "first_party": bool(img.get("firstParty")),
                }
            )
    return comps, refs, any_digest


def run() -> dict:
    try:
        py_comps, py_files, py_lock = _python_components()
        node_comps, node_files, node_lock = _node_components()
        img_comps, img_refs, any_digest = _image_components()
    except Exception as exc:  # noqa: BLE001
        return {
            "sbomType": "aggregate",
            "generator": GENERATOR,
            "status": "config_error",
            "error": exc.__class__.__name__,
            "productionReady": False,
        }

    components = py_comps + node_comps + img_comps
    limitations = [
        "custom_manifest_baseline_not_a_production_sbom",
        "no_transitive_dependency_resolution",
        "no_image_layer_introspection_no_pull",
    ]
    if not py_lock:
        limitations.append("python_lockfile_missing")
    limitations.append("node_lockfile_present" if node_lock else "node_lockfile_missing")
    if not any_digest:
        limitations.append("container_images_not_digest_pinned")

    return {
        "schemaVersion": "1",
        "sbomType": "aggregate",
        "format": "internal-manifest-baseline",
        "scope": ["python_manifest", "node_manifest", "container_image_inventory"],
        "generator": GENERATOR,
        "localOnly": True,
        "networkUsed": False,
        "sourceUploaded": False,
        "registryLoginUsed": False,
        "generatedAt": _now(),
        "componentCount": len(components),
        "components": components,
        "metadata": {"packageFiles": py_files + node_files, "imageRefs": img_refs},
        "limitations": limitations,
        "productionReady": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-report", default=str(DEFAULT_REPORT))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    report = run()
    p = Path(args.json_report)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not args.quiet:
        print(
            f"sbom status={report.get('status', 'generated')} "
            f"components={report.get('componentCount', 0)} report={args.json_report}"
        )
    return 2 if report.get("status") == "config_error" else 0


if __name__ == "__main__":
    sys.exit(main())
