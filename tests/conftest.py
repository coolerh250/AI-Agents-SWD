import importlib.util
import subprocess
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
_preload_module("validate_runtime_config", _REPO_ROOT / "scripts" / "validate_runtime_config.py")
_preload_module("list_required_secrets", _REPO_ROOT / "scripts" / "list_required_secrets.py")
_preload_module(
    "code_generator",
    _REPO_ROOT / "agents" / "development-agent" / "src" / "code_generator.py",
)
_preload_module(
    "llm_planner",
    _REPO_ROOT / "agents" / "development-agent" / "src" / "llm_planner.py",
)


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


class _CanonicalGitRepo:
    """A real, isolated Git repository for exercising canonical-ref decision discovery against
    genuine Git tree/blob/log semantics -- never this repository's own history, never faked text.

    Used by ``successor_lifecycle``'s canonical-authority tests: a test writes decision files,
    commits them for real, and points ``CANONICAL_DECISION_REF`` at whichever commit it wants
    treated as canonical -- so "not yet canonical" and "now canonical" are both real Git states,
    not monkeypatched strings.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self._run("init", "-q", "-b", "main")
        self._run("config", "user.email", "test@example.invalid")
        self._run("config", "user.name", "Test")

    def _run(self, *args: str, env: dict | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=env,
        )
        return result.stdout.strip()

    def write_decision(self, filename: str, content: str) -> None:
        target = self.path / "docs" / "decisions" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def write(self, relpath: str, content: str) -> None:
        target = self.path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit(self, message: str = "commit") -> str:
        self._run("add", "-A")
        self._run("commit", "-q", "-m", message, "--allow-empty")
        return self._run("rev-parse", "HEAD")

    def add_symlink_entry(self, filename: str, target: str) -> None:
        """Add a real Git symlink TREE ENTRY (mode 120000) without needing OS symlink support --
        exercises the exact thing discovery must reject, portable to a host with no symlink
        privilege at all."""
        blob_sha = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=self.path,
            input=target,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()
        self._run(
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{blob_sha},docs/decisions/{filename}",
        )
        self._run("commit", "-q", "-m", "add symlinked decision entry")

    def set_canonical(self, commit: str) -> None:
        self._run("update-ref", "refs/remotes/origin/main", commit)

    def head(self) -> str:
        return self._run("rev-parse", "HEAD")

    def commit_tree_with_extra_files(
        self, base_commit: str, extra_files: dict[str, str], message: str
    ) -> str:
        """A new commit -- ``base_commit``'s tree plus ``extra_files`` layered on top -- created
        with no ref pointing at it and the real index never touched (a scratch ``GIT_INDEX_FILE``
        is used instead). Models "an acceptance decision commit landing on top of an already-real
        implementation commit" without ever creating a real, referenced decision.
        """
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
            self._run("read-tree", base_commit, env=env)
            for relpath, content in extra_files.items():
                blob_sha = subprocess.run(
                    ["git", "hash-object", "-w", "--stdin"],
                    cwd=self.path,
                    input=content,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                    env=env,
                ).stdout.strip()
                self._run(
                    "update-index", "--add", "--cacheinfo", f"100644,{blob_sha},{relpath}", env=env
                )
            tree_sha = self._run("write-tree", env=env)
            return self._run("commit-tree", tree_sha, "-p", base_commit, "-m", message, env=env)


@pytest.fixture
def canonical_git_repo(tmp_path, monkeypatch):
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    import successor_lifecycle as lifecycle

    repo = _CanonicalGitRepo(tmp_path / "canon")
    monkeypatch.setattr(lifecycle, "ROOT", repo.path)
    return repo
