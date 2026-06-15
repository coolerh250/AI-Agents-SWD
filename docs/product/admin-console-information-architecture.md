# Admin Console v0 — Information Architecture (Stage 50)

How the read-only console serves each audience.

## Business owner view

Primary page: **Executive Overview**. Answers "is my delivery on track and is
the platform safe?" without technical detail: active projects, delivery package
status, acceptance gate decision, human acceptance (pending), safety result,
regression status, backup readiness gaps. Plus the **Delivery Package** page's
business-facing status cards and the business handoff summary.

## Platform / project manager view

Primary pages: **Projects**, **Project Detail**, **Mini Delivery Pilot**,
**Delivery Package / Acceptance Gate**. Answers "which projects exist, what
stage are they at, what is the acceptance gate result, what is pending human
review?". Per-project rollup: status, risk, autonomy, latest pilot status,
latest package status, readiness, human acceptance.

## System administrator view

Primary pages: **Safety Center**, **Regression / Verification**, **Incidents**,
**Cost / LLM Governance**. Answers "is the platform safe and healthy?": the full
read-only safety posture (controlled-only flags, production_executed count,
operator-actions disabled, audit integrity, denylist posture, backup gaps),
latest regression result + allowed gaps, incident counts, and LLM/cost summary.

## Project detail model

`/operations/admin-console/projects/{id}` returns the project record, a rollup
(latest pilot / package / readiness / human acceptance), and the latest pilot +
delivery package. The Project Detail page renders these as redacted key/value
tables. Brief / scope / user stories / milestones / work items / dependencies /
risks / artifacts are available via the existing project `/operations/*`
endpoints and are surfaced as the console grows.

## Delivery package model

`/operations/admin-console/latest-delivery-state` returns the latest pilot,
delivery package, acceptance gate, readiness snapshot, and human acceptance
status. The Delivery Package page shows package status, gate status / decision,
readiness, and human acceptance (pending), plus the gate + readiness detail.
Accept / reject / request-changes are shown as a disabled future feature.

## Safety center model

`/operations/admin-console/safety-summary` returns a compact, read-only subset
of `/operations/safety`: overall result, production_executed count, the
delivery-package controlled-only flags, latest human acceptance / readiness, and
the admin-console flags (`admin_console_read_only=true`,
`admin_console_operator_actions_enabled=false`,
`admin_console_write_api_enabled=false`,
`admin_console_secret_redaction_enabled=true`). All values are redacted of
secret-like keys before display.
