"""Step 51.2C1 -- no fake ReadWriteMany availability."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

ENV_FILES = [
    "values.yaml",
    "values-dev.yaml",
    "values-test.yaml",
    "values-staging-placeholder.yaml",
    "values-prod-placeholder.yaml",
]


def _v(name: str) -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8")) or {}


def test_no_rwx_claim_actually_provisioned() -> None:
    for f in ENV_FILES:
        st = _v(f).get("storage", {})
        for key, s in st.items():
            if isinstance(s, dict) and s.get("accessMode") == "ReadWriteMany":
                # RWX must remain inert: never a generated PVC, never persistence-enabled
                assert s.get("strategy") != "generatedPVC", (f, key)
                assert s.get("persistenceEnabled") is False, (f, key)


def test_no_existing_claim_name_filled_in() -> None:
    for f in ENV_FILES:
        st = _v(f).get("storage", {})
        for key, s in st.items():
            if isinstance(s, dict) and "existingClaim" in s:
                assert s["existingClaim"] == "", (f, key)


def test_workspace_rwx_is_documented_placeholder() -> None:
    cat = yaml.safe_load(
        (ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml").read_text("utf-8")
    )
    ws = cat["stores"]["workspace-scratch"]
    assert ws["sharedFilesystem"] is False
    assert "placeholder" in ws["futureTarget"].lower()
