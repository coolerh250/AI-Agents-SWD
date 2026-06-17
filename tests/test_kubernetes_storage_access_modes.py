"""Step 51.2C1 -- access mode safety (RWO generated, RWX only existingClaim)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
SCHEMA = CHART / "values.schema.json"


def _v(name: str = "values.yaml") -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def test_generated_pvc_datastores_are_rwo() -> None:
    st = _v()["storage"]
    for key in ("postgres", "redis"):
        if st[key]["strategy"] == "generatedPVC":
            assert st[key]["accessMode"] == "ReadWriteOnce", key


def test_no_rwx_on_active_generated_pvc() -> None:
    st = _v()["storage"]
    for key in ("postgres", "redis", "workspace", "artifacts"):
        s = st[key]
        if s.get("accessMode") == "ReadWriteMany":
            # RWX is only allowed as an inert placeholder, never a generated PVC
            assert s["strategy"] != "generatedPVC", key
            assert s["persistenceEnabled"] is False, key


def test_schema_enforces_generated_pvc_rwo() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    ds = schema["definitions"]["datastoreStorage"]
    cond = ds["allOf"][0]
    assert cond["if"]["properties"]["strategy"]["const"] == "generatedPVC"
    assert cond["then"]["properties"]["accessMode"]["const"] == "ReadWriteOnce"


def test_no_readwriteoncepod_used() -> None:
    raw = (CHART / "values.yaml").read_text(encoding="utf-8")
    assert "ReadWriteOncePod" not in raw
