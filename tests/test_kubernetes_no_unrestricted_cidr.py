"""Step 51.2B -- no unrestricted CIDR anywhere in the network config."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"

# validate-values.yaml names the forbidden CIDRs in its guard messages; exclude it.
SCAN = [
    CHART / "values.yaml",
    CHART / "values-dev.yaml",
    CHART / "values-test.yaml",
    CHART / "values-staging-placeholder.yaml",
    CHART / "values-prod-placeholder.yaml",
    CHART / "templates" / "networkpolicies.yaml",
    CATALOG,
]


def test_no_unrestricted_cidr() -> None:
    for p in SCAN:
        text = p.read_text(encoding="utf-8")
        assert "0.0.0.0/0" not in text, p.name
        assert "::/0" not in text, p.name


def test_schema_forbids_unrestricted_cidr() -> None:
    import json

    schema = json.loads((CHART / "values.schema.json").read_text(encoding="utf-8"))
    cidrs = schema["properties"]["externalDataServices"]["additionalProperties"]["properties"][
        "cidrs"
    ]
    assert cidrs["items"]["not"]["enum"] == ["0.0.0.0/0", "::/0"]
