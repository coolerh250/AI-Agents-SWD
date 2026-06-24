"""Step 54.3 -- local image policy runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location(
        "_img_runner", ROOT / "scripts" / "run_local_image_policy_scan.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_detects_digest_and_root_gaps() -> None:
    report = _runner().run()
    rules = {f["rule_id"] for f in report["policyFindings"]}
    assert "IMG-NO-DIGEST" in rules
    assert "IMG-DOCKERFILE-ROOT" in rules
    assert report["status"] == "completed_with_policy_findings"


def test_no_network_no_registry_no_cve() -> None:
    report = _runner().run()
    assert report["networkUsed"] is False
    assert report["registryLoginUsed"] is False
    assert report["vulnerabilities"] == []
    assert any("no_cve_lookup" in lim for lim in report["limitations"])
    assert report["productionReady"] is False
