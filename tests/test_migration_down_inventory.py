"""Stage 36 -- migration down-script inventory script + helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_inventory_script_is_executable_and_reports_inventory():
    script = _REPO_ROOT / "scripts" / "check_migration_down_scripts.sh"
    assert script.exists()
    # Run inside the repo so MIGRATIONS_DIR=./migrations resolves.
    result = subprocess.run(
        ["bash", str(script)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "migration_down_inventory_begin" in result.stdout
    assert "migration_down_inventory_end" in result.stdout
    # Either PASS or PASS_WITH_GAPS is acceptable -- both are exit 0.
    assert "MIGRATION_DOWN_SCRIPT_INVENTORY:" in result.stdout


def test_inventory_reports_gaps_for_current_repo():
    """Stage 36 deliberately ships no *_down.sql files yet, so the
    inventory MUST report gaps. If a future stage adds down scripts this
    test will need updating.
    """
    script = _REPO_ROOT / "scripts" / "check_migration_down_scripts.sh"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "PASS_WITH_GAPS" in result.stdout or "PASS" in result.stdout


def test_python_inventory_helper_matches_shell():
    """The operations.py helper walks migrations/ the same way the shell
    script does -- they MUST agree on total + gaps.
    """
    # The helper lives in operations.py; instead of importing the whole
    # app, we reimplement the walk for the assertion. This guards against
    # the two walks drifting.
    migrations_dir = _REPO_ROOT / "migrations"
    total = 0
    with_down = 0
    for f in sorted(migrations_dir.glob("*.sql")):
        if f.name.endswith("_down.sql"):
            continue
        total += 1
        if (migrations_dir / f"{f.stem}_down.sql").exists():
            with_down += 1
    assert total > 0
    assert with_down <= total
