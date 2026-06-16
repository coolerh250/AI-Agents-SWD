"""Step 51.2A -- RBAC safety catalog + absence of RBAC objects."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CATALOG = ROOT / "infra" / "kubernetes" / "rbac-safety-catalog.yaml"


def _cat() -> dict:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))


def test_rbac_flags_all_false() -> None:
    rbac = _cat()["rbac"]
    for fl in (
        "clusterRolesAllowed",
        "clusterRoleBindingsAllowed",
        "wildcardPermissionsAllowed",
        "secretReadPermissionsAllowed",
        "deploymentMutationPermissionsAllowed",
        "jobCreationPermissionsAllowed",
        "podsExecAllowed",
        "podsPortForwardAllowed",
    ):
        assert rbac[fl] is False, fl


def test_no_rbac_objects_created_this_stage() -> None:
    rbac = _cat()["rbac"]
    for counter in (
        "rolesCreatedThisStage",
        "roleBindingsCreatedThisStage",
        "clusterRolesCreatedThisStage",
        "clusterRoleBindingsCreatedThisStage",
    ):
        assert rbac[counter] == 0, counter


def test_all_components_no_kube_api() -> None:
    comps = _cat()["components"]
    assert len(comps) == 23, len(comps)
    for n, c in comps.items():
        assert c["kubernetesApiRequired"] is False, n
        assert c["allowedRoles"] == [], n


def test_no_unresolved_kube_api_needs() -> None:
    assert _cat().get("unresolvedKubernetesApiNeeds") == []


def test_no_rbac_kinds_in_templates() -> None:
    text = "\n".join(p.read_text(encoding="utf-8") for p in (CHART / "templates").glob("*.yaml"))
    for kind in ("ClusterRole", "ClusterRoleBinding", "Role", "RoleBinding"):
        assert not re.search(rf"kind:\s*{kind}\b", text), kind


def test_future_deployment_boundary_documented() -> None:
    assert _cat()["futureBoundary"]["deploymentAgentPolicy"]
