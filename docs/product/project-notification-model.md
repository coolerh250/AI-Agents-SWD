# Project Notification Model (Step 57)

Mock notification events only (project_created, work_item_created, work_item_dispatched,
work_item_blocked, work_item_completed, delivery_package_linked,
project_delivery_state_updated). See
[`infra/delivery/project-notification-model.yaml`](../../infra/delivery/project-notification-model.yaml).
External send (Slack/email/webhook) is disabled; future Slack integration requires
approval.
