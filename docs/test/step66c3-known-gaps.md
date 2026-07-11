# Step 66C.3 — Known Gaps

> **Documentation only. No production action.**

## Blocking (none)

No blocking gaps — 66C.3 PASS criteria met (see
`step66c3-workroom-audit-visibility-hardening-report.md`). Message visibility filtering is
server-side (not frontend-only). The audit-evidence endpoint never exposes a raw message body or
clarification answer. The answered-twice guard is atomic and covered by dedicated tests.

## Gaps closed by this stage (operator-confirmed, Step 66C.3-V)

- **G1 — message visibility filtering not implemented.** Closed — see
  `step66c3-message-visibility-evidence.md`. Operator-confirmed VISIBLE.
- **G3 — per-task audit lookup endpoint not implemented.** Closed — see
  `step66c3-task-audit-evidence-endpoint-record.md`. Operator-confirmed VISIBLE.
- **G5 — answered-twice guard lacks a dedicated test.** Closed — see
  `step66c3-answered-twice-guard-record.md`. Operator-confirmed VISIBLE.

See `step66c3-operator-validation-record.md` for the full per-item operator validation.

## Non-blocking

1. **Enforced visibility matrix is conservative, not a full reproduction of the spec's illustrative
   table.** Reviewer/Approver does not see `operators`-visibility messages; PM/Engineering Lead and
   Platform Admin do not see `audit_only`; only Security/Compliance Reviewer sees `audit_only`
   in-workroom. Documented explicitly in `step66c3-message-visibility-evidence.md` §1, not
   overclaimed. Can be revisited if the operator wants a different matrix.
2. **No UI to create a message/clarification with a non-`task_participants` visibility.** The message
   composer and Create Clarification form still only ever create `task_participants`-visibility
   content (unchanged from 66C.1/66C.2) — G1's filtering is meaningful for whatever `operators`/
   `audit_only`/`private_system` messages a future agent/system-event producer creates, but nothing in
   this stage or earlier creates them yet. Out of scope per spec.
3. **Audit evidence has no pagination.** `AuditStore.get_audit_logs(task_id)` returns every row for
   the task with no limit. Acceptable at current task/message volumes; revisit if task audit trails
   grow large. Deferred to later.
4. **No real-time/websocket delivery for either the workroom or audit evidence.** Both are
   read-once-per-navigation/refresh. Carried over from 66C.1/66C.2 (G6, out of scope per spec).
   Deferred to later.
5. **RBAC is server-enforced only, not client-side hidden.** The Audit Evidence section always
   attempts to fetch; a denied role sees a readable restricted message after the request fails, not a
   pre-hidden panel. Matches the established pattern from every prior workroom form. Client-hidden
   RBAC improvements (pre-emptively hiding actions a role can't perform) are deferred to later.
6. **Clarification reminder/expiry scheduler still not implemented (G2).** Unaffected by this stage,
   explicitly out of scope — see `step66c3-known-gaps.md` mapping below.
7. **Project/team RBAC scoping still not implemented (G4).** Unaffected by this stage, explicitly out
   of scope.

## Gap status (per spec's required mapping)

- **G1** — message visibility filtering — **closed** (this stage).
- **G2** — clarification reminder / expiry scheduler not implemented → 66C.4.
- **G3** — per-task audit lookup endpoint — **closed** (this stage).
- **G4** — project/team RBAC scoping not implemented → 66S.
- **G5** — answered-twice guard dedicated test — **closed** (this stage).
- **G6** — real-time Workroom delivery not implemented → later.

## Statement

No production action occurred. No workflow dispatch occurred. No workflow resume occurred. No
external action occurred. Gaps above are all non-blocking for the 66C.3 PASS criteria.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
