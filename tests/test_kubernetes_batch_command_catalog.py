"""Step 51.2C2 -- batch command catalog: fixed, shell-free, no drift."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "infra" / "kubernetes" / "batch-command-catalog.yaml"
VALUES = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values.yaml"

SHELL_TOKENS = ("-c", "$(", "&&", ";", "|", "`")


def _cat() -> dict:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["commands"]


def _bcmd() -> dict:
    return yaml.safe_load(VALUES.read_text(encoding="utf-8"))["batchCommands"]


def test_commands_fixed_and_shell_free() -> None:
    for k, c in _cat().items():
        assert c["shell"] is False, k
        assert c["allowVariableArgs"] is False, k
        assert c["executable"], k
        for tok in c["executable"] + c.get("args", []):
            assert not any(t in str(tok) for t in SHELL_TOKENS), (k, tok)


def test_source_paths_exist() -> None:
    for k, c in _cat().items():
        for sp in c.get("sourcePaths", []):
            assert (ROOT / sp).exists(), f"{k}: {sp}"


def test_catalog_matches_values_batch_commands() -> None:
    cat, bcmd = _cat(), _bcmd()
    assert set(cat) == set(bcmd)
    for k, c in cat.items():
        assert bcmd[k]["command"] == c["executable"], k
        assert bcmd[k]["args"] == c["args"], k
        assert bcmd[k]["shell"] is False, k


def test_no_arbitrary_command_keys() -> None:
    assert set(_cat()) == {"migration", "encrypted-backup", "isolated-restore-drill"}
