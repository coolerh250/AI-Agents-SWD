import importlib.util
import sys
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


def _preload_module(module_name: str, path: Path) -> None:
    """Preload a sibling module under a fixed sys.modules name.

    The retry-scheduler's main.py does ``from scheduler import RetryScheduler``;
    preloading scheduler.py here lets test files do the same import at module
    level without putting another src/ on sys.path.
    """
    if module_name in sys.modules or not path.exists():
        return
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


_preload_module("scheduler", _REPO_ROOT / "apps" / "retry-scheduler" / "src" / "scheduler.py")
_preload_module("real_guard", _REPO_ROOT / "apps" / "github-automation" / "src" / "real_guard.py")


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


@pytest.fixture
def github_automation_module():
    return _load_service_module("github-automation")


@pytest.fixture
def github_automation_app(github_automation_module):
    return github_automation_module.app


@pytest.fixture
def retry_scheduler_module():
    return _load_service_module("retry-scheduler")


def _load_agent_module(agent: str) -> ModuleType:
    """Load an agent's agents/<agent>/src/main.py for in-process testing.

    main.py does ``from agent import ...``; agent.py is loaded first under the
    module name ``agent`` so that import resolves without a shared sys.path entry.
    """
    src = _REPO_ROOT / "agents" / agent / "src"
    agent_spec = importlib.util.spec_from_file_location("agent", src / "agent.py")
    assert agent_spec is not None and agent_spec.loader is not None
    agent_module = importlib.util.module_from_spec(agent_spec)
    sys.modules["agent"] = agent_module
    agent_spec.loader.exec_module(agent_module)

    main_name = f"{agent.replace('-', '_')}_main"
    main_spec = importlib.util.spec_from_file_location(main_name, src / "main.py")
    assert main_spec is not None and main_spec.loader is not None
    main_module = importlib.util.module_from_spec(main_spec)
    main_spec.loader.exec_module(main_module)
    return main_module


@pytest.fixture
def intake_agent():
    return _load_agent_module("intake-agent")


@pytest.fixture
def requirement_agent():
    return _load_agent_module("requirement-agent")


@pytest.fixture
def development_agent():
    return _load_agent_module("development-agent")


@pytest.fixture
def qa_agent():
    return _load_agent_module("qa-agent")


@pytest.fixture
def devops_agent():
    return _load_agent_module("devops-agent")
