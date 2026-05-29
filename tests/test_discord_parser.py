"""Unit tests for apps/discord-gateway/src/parser.parse_discord_message."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_DG_SRC = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"


def _load_parser() -> ModuleType:
    sys.path.insert(0, str(_DG_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "discord_gateway_parser", _DG_SRC / "parser.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


def test_parse_slash_command_dev_test():
    parser = _load_parser()
    out = parser.parse_discord_message(
        '/ai task type=dev.test description="create user management module"',
        channel_id="ch-1",
        user_id="u-1",
        message_id="m-1",
    )
    assert out["source"] == "discord-sandbox"
    assert out["command_type"] == "slash"
    assert out["request"]["type"] == "dev.test"
    assert out["request"]["description"] == "create user management module"
    assert out["request"]["github"]["enabled"] is True
    assert out["request"]["github"]["dry_run"] is True
    assert out["request"]["discord"]["channel_id"] == "ch-1"
    assert out["request"]["discord"]["user_id"] == "u-1"
    assert out["request"]["discord"]["message_id"] == "m-1"
    assert out["task_id"].startswith("discord-")


def test_parse_natural_message():
    parser = _load_parser()
    out = parser.parse_discord_message(
        "ai task: create user management module",
        channel_id="ch-2",
        user_id="u-2",
    )
    assert out["command_type"] == "natural"
    assert out["request"]["type"] == "dev.test"
    assert out["request"]["description"] == "create user management module"


def test_parse_production_command_inherits_default_github():
    parser = _load_parser()
    out = parser.parse_discord_message(
        '/ai task type=production.deploy description="deploy to production"'
    )
    assert out["request"]["type"] == "production.deploy"
    # production tasks still default github.enabled=True / dry_run=True; the
    # safety contract is enforced by the orchestrator approval flow, not by
    # the parser disabling github here.
    assert out["request"]["github"]["enabled"] is True
    assert out["request"]["github"]["dry_run"] is True


def test_parse_with_github_options_disabled():
    parser = _load_parser()
    out = parser.parse_discord_message(
        '/ai task type=dev.test description="test only" github.enabled=false'
    )
    assert out["request"]["github"]["enabled"] is False
    assert out["request"]["github"]["dry_run"] is True  # default


def test_parse_with_github_options_repo_override():
    parser = _load_parser()
    out = parser.parse_discord_message(
        '/ai task type=dev.test description="update docs" '
        "github.enabled=true github.dry_run=true github.repo=other/repo"
    )
    assert out["request"]["github"]["repo"] == "other/repo"
    assert out["request"]["github"]["enabled"] is True


def test_parse_empty_message_raises():
    parser = _load_parser()
    with pytest.raises(parser.ParseError):
        parser.parse_discord_message("")
    with pytest.raises(parser.ParseError):
        parser.parse_discord_message("   ")


def test_parse_unsupported_prefix_raises():
    parser = _load_parser()
    with pytest.raises(parser.ParseError):
        parser.parse_discord_message("hello world, no command prefix")


def test_parse_slash_without_description_raises():
    parser = _load_parser()
    with pytest.raises(parser.ParseError):
        parser.parse_discord_message("/ai task type=dev.test")


def test_parse_preserves_caller_task_id():
    parser = _load_parser()
    out = parser.parse_discord_message(
        '/ai task type=dev.test description="x"',
        task_id="caller-supplied-1",
    )
    assert out["task_id"] == "caller-supplied-1"


def test_parse_single_quotes_around_description():
    parser = _load_parser()
    out = parser.parse_discord_message("/ai task type=dev.test description='single-quoted desc'")
    assert out["request"]["description"] == "single-quoted desc"
