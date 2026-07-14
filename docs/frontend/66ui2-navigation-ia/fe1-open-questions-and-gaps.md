# Step 66UI.2-FE.1 - Open Questions and Gaps

Marker: `STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY: PASS`

Branch: `frontend/66ui2-navigation-grouping`

## Purpose

This document records design gaps, implementation limits, and review questions that should be visible to Product Owner, Claude Code, Claude Design, and future frontend implementers.

## Open Questions

1. Delivery Package group placement - resolved by FIX1

   Product Owner confirmed Delivery Package must move back to Platform Ops. Deliveries remains placeholder-only with Delivery Inbox and Delivery Detail until Step 66D API / data contract work decides any future integration.

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
- Deliveries remains placeholder-only until Step 66D.
- Delivery Package remains an existing Platform Ops page and route.
- No Reminder / Expiry 66C.4 real UI was implemented.
- Clarifications remains a safe Step 66C.4 placeholder with no fake queue, fake reminder controls, fake expiry controls, workflow resume, or workflow dispatch controls.
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

- Validate Delivery Package under Platform Ops after FIX1.
- Confirm seven group labels and order.
- Confirm direct-route-only Demo Evidence behavior.
- Confirm placeholder wording and required stages.

Claude Code:

- Confirm branch base and no design-branch merge.
- Confirm no forbidden scope changes.
- Confirm verifier coverage.
- Confirm the FIX1 remediation satisfies the 66UI.2-R PASS_WITH_GAPS merge-blocking item.

Claude Design:

- Provide detailed treatments for Delivery Inbox, Delivery Detail, Approvals, DLQ / Retry, Reminder / Expiry, and Settings pages.
- Confirm whether Platform Ops collapsed-by-default behavior needs visual affordance changes.
- Confirm final label copy for placeholders and unfinished settings areas.
