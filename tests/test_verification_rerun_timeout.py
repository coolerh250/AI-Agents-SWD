"""Stage 52 -- verification rerun honours a timeout (no hang)."""

from __future__ import annotations

import subprocess

from shared.sdk.operator_actions import verification_runner as vr


def test_timeout_marks_failed(monkeypatch, tmp_path) -> None:
    # Point the allowlist at a throwaway script and force a timeout.
    script = tmp_path / "scripts" / "verify_admin_console_v0.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env bash\nsleep 30\n", encoding="utf-8")

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="bash", timeout=1)

    monkeypatch.setattr(vr.subprocess, "run", _boom)
    res = vr.run_verification("admin_console_v0", repo_root=tmp_path, timeout=1)
    assert res.timed_out is True
    assert res.status == "failed"
    assert res.production_executed is False
