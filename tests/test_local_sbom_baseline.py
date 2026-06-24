"""Step 54.3 -- local SBOM baseline runner."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = re.compile(r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)")


def _runner():
    spec = importlib.util.spec_from_file_location(
        "_sbom_runner", ROOT / "scripts" / "run_local_sbom_baseline.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_generates_aggregate_sbom() -> None:
    report = _runner().run()
    assert report["sbomType"] == "aggregate"
    assert set(report["scope"]) >= {"python_manifest", "node_manifest", "container_image_inventory"}
    assert report["componentCount"] > 0
    assert report["productionReady"] is False


def test_records_lockfile_and_digest_limitations() -> None:
    report = _runner().run()
    lims = " ".join(report["limitations"])
    assert "python_lockfile_missing" in lims
    assert "not_digest_pinned" in lims


def test_no_raw_credential_no_network() -> None:
    report = _runner().run()
    assert report["networkUsed"] is False
    assert report["sourceUploaded"] is False
    assert not RAW.search(json.dumps(report, default=str))
