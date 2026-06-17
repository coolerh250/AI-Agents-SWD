"""Step 51.2C1 -- no hostPath / NFS / CSI / PV / StorageClass in storage layer."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TEMPLATES = CHART / "templates"


def test_no_hostpath_nfs_csi_in_values_or_templates() -> None:
    files = [CHART / "values.yaml"] + list(TEMPLATES.glob("*.yaml"))
    for f in files:
        raw = f.read_text(encoding="utf-8")
        if f.name == "validate-values.yaml":
            continue  # policy logic names the forbidden tokens
        assert "hostPath" not in raw, f.name
        # NFS / CSI raw volume config must not appear as volume keys
        for vol_key in ("\n        nfs:", "\n          nfs:", "\n        csi:", "\n          csi:"):
            assert vol_key not in raw, (f.name, vol_key)


def test_no_pv_or_storageclass_resource_template() -> None:
    for f in TEMPLATES.glob("*.yaml"):
        raw = f.read_text(encoding="utf-8")
        assert "kind: PersistentVolume\n" not in raw, f.name
        assert "kind: StorageClass" not in raw, f.name


def test_schema_storage_forbids_extra_fields() -> None:
    schema = json.loads((CHART / "values.schema.json").read_text(encoding="utf-8"))
    for d in ("datastoreStorage", "appStorage"):
        assert schema["definitions"][d]["additionalProperties"] is False
    assert schema["properties"]["storage"]["additionalProperties"] is False
