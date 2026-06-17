"""Step 51.2C1 -- per-environment storage rules."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _merged(env_file: str) -> dict:
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((CHART / env_file).read_text(encoding="utf-8"))

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out

    return merge(base, over)


def test_dev_test_generated_pvc() -> None:
    for f in ("values-dev.yaml", "values-test.yaml"):
        st = _merged(f)["storage"]
        assert st["postgres"]["strategy"] == "generatedPVC"
        assert st["redis"]["strategy"] == "generatedPVC"


def test_staging_prod_no_generated_pvc() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        m = _merged(f)
        st = m["storage"]
        assert st["postgres"]["strategy"] == "externalService"
        assert st["redis"]["strategy"] == "externalService"
        # internal datastores disabled => no generated PVC can render
        assert m["components"]["postgres"]["enabled"] is False
        assert m["components"]["redis"]["enabled"] is False


def test_no_real_storage_class_in_any_env() -> None:
    bad = {"gp2", "gp3", "standard", "managed-premium", "ebs-sc", "local-path"}
    for f in (
        "values.yaml",
        "values-dev.yaml",
        "values-test.yaml",
        "values-staging-placeholder.yaml",
        "values-prod-placeholder.yaml",
    ):
        m = yaml.safe_load((CHART / f).read_text(encoding="utf-8"))
        st = (m or {}).get("storage", {})
        for key, s in st.items():
            if isinstance(s, dict):
                assert (s.get("storageClassName") or "").lower() not in bad, (f, key)
