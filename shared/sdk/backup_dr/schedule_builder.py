"""Stage 51 -- backup schedule spec builder (dry-run only).

Generates cron / systemd-timer / Kubernetes-CronJob schedule specs and
validates the command preview. NEVER installs or enables a real schedule:
``enabled`` and ``production_schedule_enabled`` stay false; ``dry_run_validated``
is set once the spec passes validation.
"""

from __future__ import annotations

import re

from shared.sdk.backup_dr.models import BackupScheduleDefinition

DEFAULT_COMMAND_PREVIEW = "/opt/AI-Agents-SWD/scripts/run_encrypted_backup.sh --environment test"

_CRON_RE = re.compile(r"^\S+\s+\S+\s+\S+\s+\S+\s+\S+$")


def validate_cron_expression(expr: str) -> bool:
    return bool(_CRON_RE.match((expr or "").strip()))


def _validate_command_preview(command_preview: str) -> bool:
    cp = (command_preview or "").strip()
    if not cp:
        return False
    # The command must reference a known controlled backup script and must not
    # contain a production marker.
    if "run_encrypted_backup.sh" not in cp and "backup_postgres" not in cp:
        return False
    if "--environment production" in cp or "production" in cp.split("#", 1)[0].split():
        return False
    return True


def build_cron_spec(
    *,
    schedule_key: str = "backup-dr-daily-cron",
    schedule_expression: str = "0 2 * * *",
    command_preview: str = DEFAULT_COMMAND_PREVIEW,
) -> BackupScheduleDefinition:
    valid = validate_cron_expression(schedule_expression) and _validate_command_preview(
        command_preview
    )
    return BackupScheduleDefinition(
        schedule_key=schedule_key,
        schedule_type="cron_spec",
        schedule_expression=schedule_expression,
        command_preview=command_preview,
        enabled=False,
        dry_run_validated=valid,
        production_schedule_enabled=False,
        metadata={"dry_run_only": True},
    )


def build_systemd_timer_spec(
    *,
    schedule_key: str = "backup-dr-daily-systemd",
    on_calendar: str = "*-*-* 02:00:00",
    command_preview: str = DEFAULT_COMMAND_PREVIEW,
) -> BackupScheduleDefinition:
    valid = bool(on_calendar.strip()) and _validate_command_preview(command_preview)
    return BackupScheduleDefinition(
        schedule_key=schedule_key,
        schedule_type="systemd_timer_spec",
        schedule_expression=on_calendar,
        command_preview=command_preview,
        enabled=False,
        dry_run_validated=valid,
        production_schedule_enabled=False,
        metadata={"dry_run_only": True, "on_calendar": on_calendar},
    )


def build_kubernetes_cronjob_spec(
    *,
    schedule_key: str = "backup-dr-daily-k8s",
    schedule_expression: str = "0 2 * * *",
    command_preview: str = DEFAULT_COMMAND_PREVIEW,
) -> BackupScheduleDefinition:
    """A disabled / dry-run Kubernetes CronJob spec. Never applied to a cluster."""
    valid = validate_cron_expression(schedule_expression) and _validate_command_preview(
        command_preview
    )
    return BackupScheduleDefinition(
        schedule_key=schedule_key,
        schedule_type="kubernetes_cronjob_spec",
        schedule_expression=schedule_expression,
        command_preview=command_preview,
        enabled=False,
        dry_run_validated=valid,
        production_schedule_enabled=False,
        metadata={"dry_run_only": True, "applied": False, "suspend": True},
    )


def render_kubernetes_cronjob_yaml(spec: BackupScheduleDefinition) -> str:
    """Render a disabled (``suspend: true``) Kubernetes CronJob YAML preview."""
    return (
        "apiVersion: batch/v1\n"
        "kind: CronJob\n"
        "metadata:\n"
        f"  name: {spec.schedule_key}\n"
        "spec:\n"
        "  suspend: true  # dry-run only -- never applied to a cluster\n"
        f'  schedule: "{spec.schedule_expression}"\n'
        "  jobTemplate:\n"
        "    spec:\n"
        "      template:\n"
        "        spec:\n"
        "          restartPolicy: Never\n"
        "          containers:\n"
        "            - name: backup\n"
        "              image: aiagents/backup:dry-run\n"
        f'              command: ["/bin/sh", "-c", "{spec.command_preview}"]\n'
    )


def schedule_gap_closed(spec: BackupScheduleDefinition) -> bool:
    """Closed when a schedule spec exists and is dry-run validated, with the
    real production schedule disabled."""
    return spec.dry_run_validated and not spec.production_schedule_enabled and not spec.enabled


__all__ = [
    "DEFAULT_COMMAND_PREVIEW",
    "validate_cron_expression",
    "build_cron_spec",
    "build_systemd_timer_spec",
    "build_kubernetes_cronjob_spec",
    "render_kubernetes_cronjob_yaml",
    "schedule_gap_closed",
]
