"""Step 51.2C1 -- mount path safety."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
VALIDATE = CHART / "templates" / "validate-values.yaml"

FORBIDDEN = {"/", "/app", "/etc", "/bin", "/sbin", "/usr", "/proc", "/sys", "/dev"}
ALLOWED = {"/var/lib/postgresql/data", "/data"}


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_datastore_mount_paths_safe_and_known() -> None:
    st = _v()["storage"]
    for key in ("postgres", "redis"):
        mp = st[key]["mountPath"]
        assert mp.startswith("/")
        assert mp not in FORBIDDEN
        assert mp in ALLOWED, mp


def test_validate_values_blocks_forbidden_mounts() -> None:
    t = VALIDATE.read_text(encoding="utf-8")
    assert "$forbiddenMounts" in t
    assert "docker.sock" in t
    assert "mountPath must be absolute" in t


def test_no_docker_socket_anywhere() -> None:
    raw = (CHART / "values.yaml").read_text(encoding="utf-8")
    assert "docker.sock" not in raw
