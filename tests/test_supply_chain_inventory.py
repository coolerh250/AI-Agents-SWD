"""Step 54.1 -- supply chain inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "supply-chain-inventory.yaml"


def _sc() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["supplyChain"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _sc()


def test_source_control_write_and_pr_false() -> None:
    src = _sc()["sourceControl"]
    assert src["writeEnabled"] is False
    assert src["prCreationEnabled"] is False


def test_package_files_discovered() -> None:
    deps = _sc()["dependencies"]
    assert deps["python"]["packageFiles"]
    assert deps["node"]["packageFiles"]


def test_dockerfiles_and_images_discovered() -> None:
    c = _sc()["containers"]
    assert c["dockerfiles"]
    assert c["composeImages"]
    assert c["helmImages"]
    assert c["imageDigestPinned"] is False
    assert c["latestTagAllowed"] is False


def test_scanners_and_push_login_upload_false() -> None:
    sc = _sc()
    s = sc["scanners"]
    for k in (
        "sastConfigured",
        "dependencyScanConfigured",
        "secretScanConfigured",
        "imageScanConfigured",
    ):
        assert s[k] is False
    assert sc["imagePush"]["enabled"] is False
    assert sc["registryLogin"]["enabled"] is False
    assert sc["externalScannerUpload"]["enabled"] is False


def test_python_lockfile_gap_recorded() -> None:
    py = _sc()["dependencies"]["python"]
    assert py["lockFiles"] == []
    assert py["lockStatus"] == "unpinned_no_lockfile"
