"""Step 51.1 -- runtime inventory completeness vs Docker Compose."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"
INVENTORY = ROOT / "infra" / "kubernetes" / "runtime-inventory.yaml"
MATRIX = ROOT / "infra" / "kubernetes" / "runtime-dependency-matrix.yaml"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_every_compose_service_is_inventoried() -> None:
    compose = _load(COMPOSE)
    inv = _load(INVENTORY)
    compose_services = set(compose["services"])
    inv_compose = {s["composeService"] for s in inv["services"] if s.get("composeService")}
    assert compose_services <= inv_compose, compose_services - inv_compose


def test_long_running_services_classified() -> None:
    inv = _load(INVENTORY)
    for s in inv["services"]:
        assert s.get("type"), f"{s['name']} missing type"
        assert "longRunning" in s, f"{s['name']} missing longRunning"


def test_one_shot_jobs_not_deployments() -> None:
    inv = _load(INVENTORY)
    for job in inv.get("oneShotJobs", []):
        assert job["kubernetesTarget"] != "deployment", job["name"]


def test_test_only_services_flagged() -> None:
    inv = _load(INVENTORY)
    vault = next(s for s in inv["services"] if s["name"] == "vault")
    assert vault["testOnly"] is True


def test_dependencies_have_evidence() -> None:
    matrix = _load(MATRIX)
    assert matrix["dependencies"], "dependency matrix is empty"
    for dep in matrix["dependencies"]:
        assert str(dep.get("evidence", "")).strip(), dep


def test_no_silent_unknown_dependencies() -> None:
    matrix = _load(MATRIX)
    # the field must exist (declared, even if empty) so unknowns are never dropped
    assert "unknownDependencies" in matrix


def test_inventory_has_no_secret_values() -> None:
    raw = INVENTORY.read_text(encoding="utf-8")
    # secretReferences are NAMES only; flag obvious value assignments
    for pat in ("password:", "PRIVATE KEY", "ghp_", "xoxb-"):
        assert pat not in raw, f"possible secret value in inventory: {pat}"
