"""Stage 51 -- schedule specs are dry-run validated, never production-enabled."""

from __future__ import annotations

from shared.sdk.backup_dr.schedule_builder import (
    build_cron_spec,
    build_kubernetes_cronjob_spec,
    build_systemd_timer_spec,
    render_kubernetes_cronjob_yaml,
    schedule_gap_closed,
    validate_cron_expression,
)


def test_cron_spec_validated_disabled() -> None:
    s = build_cron_spec()
    assert s.dry_run_validated is True
    assert s.production_schedule_enabled is False
    assert s.enabled is False
    assert schedule_gap_closed(s) is True


def test_systemd_and_k8s_specs() -> None:
    for s in (build_systemd_timer_spec(), build_kubernetes_cronjob_spec()):
        assert s.dry_run_validated is True
        assert schedule_gap_closed(s) is True


def test_invalid_cron_not_validated() -> None:
    assert validate_cron_expression("not a cron") is False
    s = build_cron_spec(schedule_expression="bad")
    assert s.dry_run_validated is False
    assert schedule_gap_closed(s) is False


def test_k8s_yaml_is_suspended() -> None:
    yaml = render_kubernetes_cronjob_yaml(build_kubernetes_cronjob_spec())
    assert "suspend: true" in yaml


def test_command_preview_rejects_production() -> None:
    s = build_cron_spec(command_preview="run_encrypted_backup.sh --environment production")
    assert s.dry_run_validated is False
