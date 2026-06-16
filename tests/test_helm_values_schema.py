"""Step 51.1 -- values.schema.json shape + (optional) validation of merged values."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
SCHEMA = CHART / "values.schema.json"

ENV_FILES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "production": "values-prod-placeholder.yaml",
}


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _merged(env: str) -> dict:
    base = _load_yaml(CHART / "values.yaml")
    return _deep_merge(base, _load_yaml(CHART / ENV_FILES[env]))


def test_schema_parses_and_constrains_environment() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    env = schema["properties"]["global"]["properties"]["environment"]
    assert env["enum"] == ["dev", "test", "staging", "production"]
    assert schema["properties"]["global"]["properties"]["production"]["type"] == "boolean"
    assert schema["properties"]["global"]["properties"]["realDeployEnabled"]["type"] == "boolean"
    assert "components" in schema["required"]


def test_schema_has_no_inline_secret_fields() -> None:
    raw = SCHEMA.read_text(encoding="utf-8").lower()
    for forbidden in ('"password"', '"token"', '"apikey"', '"secretvalue"'):
        assert forbidden not in raw, forbidden


def test_component_schema_requires_image_repository() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    comp = schema["properties"]["components"]["additionalProperties"]
    assert "enabled" in comp["required"]
    assert "image" in comp["required"]
    assert comp["properties"]["image"]["required"] == ["repository"]
    assert comp["properties"]["containerPort"]["type"] == "integer"


@pytest.mark.parametrize("env", list(ENV_FILES))
def test_merged_values_validate_against_schema(env: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=_merged(env), schema=schema)
