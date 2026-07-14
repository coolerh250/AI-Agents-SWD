# Step 66UI.2-FE.1 - Open Questions and Gaps

Marker: `STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY: PASS`

Branch: `frontend/66ui2-navigation-grouping`

## Purpose

This document records design gaps, implementation limits, and review questions that should be visible to Product Owner, Claude Code, Claude Design, and future frontend implementers.

## Open Questions

1. Delivery Package group placement

   The authorized FE.1 task places Delivery Package under Deliveries. The current 66UI.2-R summary on `main` says DeliveryPackage remains under Platform Ops. The implementation follows the authorized FE.1 task text and keeps the route unchanged. Product Owner and Claude Code should confirm the final IA placement before Step 66D.

2. Safety status bar field contract

   `SafetyStatusBar` reads the existing safety endpoint data only. It displays `not reported` for absent fields rather than inferring values on the client. Claude Code should decide whether a future frontend contract should define a stable safety summary shape for shell-level display.

3. Notifications stage ownership

   Notifications are represented as a placeholder because no implemented in-app notifications page was found in the current Admin Console. Product Owner should confirm whether this belongs to a future notification stage or a settings/operator stage.

4. Clarifications overview scope

   The existing Workroom supports task-scoped clarification flows. The new Clarifications nav item is a safe placeholder, not a global clarification inbox. Product Owner and Claude Design should define whether a global clarification inbox is expected.

5. Settings information architecture

   Settings placeholders are currently grouped under Roles & Permissions, Identity / Session, Integrations, Web Research Sources, and Approval Policy. Claude Design should validate labels and order before Step 66S implementation.

## Implementation Limits

- No Delivery 66D real UI was implemented.
- No Reminder / Expiry 66C.4 real UI was implemented.
- No Approvals or DLQ / Retry real UI was implemented.
- No Settings 66S real UI was implemented.
- No Pipeline board was implemented.
- No drag-and-drop behavior was introduced.
- No workflow dispatch, workflow resume, production action, or external integration controls were introduced.
- No backend, API contract, database, workflow, approval, policy, audit service, infrastructure, or production behavior was changed.

## Non-Blocking Risks

- Existing npm audit findings remain unresolved because dependency upgrades were out of scope for this IA-only frontend task.
- `apps/admin-console/tsconfig.tsbuildinfo` is tracked in the repo and changed after adding new TypeScript/TSX files. Claude Code should confirm whether this tracked build metadata should remain part of frontend commits.
- The top safety bar may show several fields as `not reported` until the backend provides stable shell-level safety fields.

## Review Requests

Product Owner:

- Confirm Delivery Package placement.
- Confirm seven group labels and order.
- Confirm direct-route-only Demo Evidence behavior.
- Confirm placeholder wording and required stages.

Claude Code:

- Confirm branch base and no design-branch merge.
- Confirm no forbidden scope changes.
- Confirm verifier coverage.
- Decide whether to adjust the 66UI.2-R summary or the implementation for Delivery Package grouping.

Claude Design:

- Provide detailed treatments for Delivery Inbox, Delivery Detail, Approvals, DLQ / Retry, Reminder / Expiry, and Settings pages.
- Confirm whether Platform Ops collapsed-by-default behavior needs visual affordance changes.
- Confirm final label copy for placeholders and unfinished settings areas.
