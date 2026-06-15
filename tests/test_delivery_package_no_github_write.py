"""Stage 49 -- delivery package build never writes GitHub / opens a PR."""

from __future__ import annotations

from delivery_package_fakes import build_fake_package


async def test_no_github_write_no_pr(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    assert result.github_write_performed is False
    assert result.pr_created is False

    report = await stores["package"].get_delivery_package_report(result.package_id)
    assert report["github_write_performed"] is False
    assert report["pr_created"] is False

    checks = await stores["package"].get_gate_check_results(result.package_id)
    by_key = {c["check_key"]: c for c in checks}
    assert by_key["no_github_write"]["status"] == "passed"
    assert by_key["no_pr_created"]["status"] == "passed"
