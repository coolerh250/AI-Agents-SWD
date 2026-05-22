import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_service_module(service: str) -> ModuleType:
    """Load a service's apps/<service>/src/main.py as a uniquely-named module.

    Each service has its own main.py; loading by file path avoids the module
    name collision that a shared sys.path entry would cause.
    """
    path = _REPO_ROOT / "apps" / service / "src" / "main.py"
    module_name = f"{service.replace('-', '_')}_main"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def policy_engine_app():
    return _load_service_module("policy-engine").app


@pytest.fixture
def approval_engine_app():
    return _load_service_module("approval-engine").app


@pytest.fixture
def audit_service_app():
    return _load_service_module("audit-service").app


@pytest.fixture
def communication_gateway_app():
    return _load_service_module("communication-gateway").app
