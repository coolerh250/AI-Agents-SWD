"""Stage 25 staging env-generator tests.

The generator script (``scripts/generate_staging_env.sh``) is exercised
via subprocess so the test reflects exactly what the operator runs.
The generated file MUST NOT carry a real GitHub / Discord / Vault
token; the only real value is the randomly-generated Postgres password,
and that file must be gitignored.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GEN = _REPO_ROOT / "scripts" / "generate_staging_env.sh"
_EXAMPLE = _REPO_ROOT / "infra" / "runtime" / "env.staging.example"


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Copy the bits of the repo the script touches into a temp dir so
    each test runs in isolation.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "infra" / "runtime").mkdir(parents=True)
    shutil.copy(_GEN, tmp_path / "scripts" / "generate_staging_env.sh")
    shutil.copy(_EXAMPLE, tmp_path / "infra" / "runtime" / "env.staging.example")
    return tmp_path


def _run_generator(workspace: Path, bash_path: str, *args, env_overrides=None):
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [bash_path, "scripts/generate_staging_env.sh", *args],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )


def test_generator_script_exists():
    assert _GEN.is_file()


def test_generator_bash_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_GEN)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_generator_produces_local_env(tmp_workspace, bash_path):
    res = _run_generator(tmp_workspace, bash_path)
    assert res.returncode == 0, res.stderr + res.stdout
    out = tmp_workspace / "infra" / "runtime" / ".env.staging.local"
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=" in text
    # Generated password MUST NOT carry the placeholder marker.
    line = next(raw for raw in text.splitlines() if raw.startswith("POSTGRES_PASSWORD="))
    value = line.split("=", 1)[1]
    assert value != "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"
    assert len(value) >= 16
    # The other secret-shaped fields stay as placeholders so the
    # validator can fail loudly if the operator forgets to fill them.
    for k in ("GITHUB_TOKEN", "DISCORD_BOT_TOKEN", "VAULT_TOKEN", "ALERTMANAGER_WEBHOOK_URL"):
        assert (
            f"{k}=PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" in text
        ), f"{k} placeholder missing (operator-supplied value should be opt-in)"


def test_generator_refuses_overwrite_without_flag(tmp_workspace, bash_path):
    _run_generator(tmp_workspace, bash_path)
    res2 = _run_generator(tmp_workspace, bash_path)
    assert res2.returncode == 0
    assert "GENERATE_STAGING_ENV: SKIP" in res2.stdout
    assert "ALLOW_OVERWRITE=true" in res2.stdout


def test_generator_overwrites_with_flag(tmp_workspace, bash_path):
    _run_generator(tmp_workspace, bash_path)
    out = tmp_workspace / "infra" / "runtime" / ".env.staging.local"
    first_text = out.read_text(encoding="utf-8")
    first_pw_line = next(
        raw for raw in first_text.splitlines() if raw.startswith("POSTGRES_PASSWORD=")
    )

    res = _run_generator(tmp_workspace, bash_path, env_overrides={"ALLOW_OVERWRITE": "true"})
    assert res.returncode == 0, res.stderr
    second_text = out.read_text(encoding="utf-8")
    second_pw_line = next(
        raw for raw in second_text.splitlines() if raw.startswith("POSTGRES_PASSWORD=")
    )
    # New random password — extremely unlikely to collide.
    assert first_pw_line != second_pw_line


def test_generated_file_permissions_restricted(tmp_workspace, bash_path):
    _run_generator(tmp_workspace, bash_path)
    out = tmp_workspace / "infra" / "runtime" / ".env.staging.local"
    mode = stat.S_IMODE(out.stat().st_mode)
    # chmod 600 is the script's intent; on Windows the bits may not
    # apply, so we only assert "not world-readable" where the platform
    # supports it.
    if os.name == "posix":
        assert mode & stat.S_IRGRP == 0
        assert mode & stat.S_IROTH == 0


def test_generated_file_carries_no_token_substring(tmp_workspace, bash_path):
    _run_generator(tmp_workspace, bash_path)
    out = tmp_workspace / "infra" / "runtime" / ".env.staging.local"
    text = out.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None


def test_gitignore_excludes_env_staging_local():
    """The .gitignore must catch any .env.staging.local file regardless
    of where it sits in the tree (Stage 25 added an explicit infra
    pattern on top of the broad .env.* rule)."""
    text = (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "infra/runtime/.env.staging.local" in text or ".env.staging.local" in text
