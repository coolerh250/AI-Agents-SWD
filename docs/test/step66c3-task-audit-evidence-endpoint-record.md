# Step 66C.3 — Task Audit Evidence Endpoint Record (G3)

> **Record only. No production action. No external action.**

## 1. Endpoint

`GET /tasks/{task_id}/audit-evidence` (`apps/orchestrator/src/workroom_api.py::get_audit_evidence`).
Reads the existing `audit_logs` table via `shared.sdk.audit.store.AuditStore.get_audit_logs(task_id)`
— the same table Stage 19's `stream.audit` → `audit-worker` pipeline already writes into. **No new
table, no new migration.**

## 2. Fields returned (allowlist)

`_AUDIT_EVIDENCE_REF_FIELDS` in `workroom_api.py` is an **allowlist**, not a blocklist — any field
present in the underlying `artifact_refs` JSONB that is not named here is silently dropped, even if a
future decision type were to add one:

`audit_event_id`, `task_id`, `event_type`, `created_at`, `correlation_id`, `actor`, `role`, `action`,
`status` (doubles as the RBAC-denial reason constant for `*_rbac_denied` events), `message_id`,
`clarification_id`, `message_type`, `visibility`, `body_length`, `body_hash`.

## 3. Fields never returned

Raw message body, raw clarification answer, request payload dump, headers, cookies, tokens, `.env`
values, secret values, raw full audit payload. These are never in `artifact_refs` to begin with
(`safe_workroom_refs`/`safe_task_refs` only ever store `body_length`/`body_hash`, never `body`), so
the allowlist is defense in depth, not the only safeguard — proven by
`test_audit_evidence_does_not_expose_raw_message_body`,
`test_audit_evidence_does_not_expose_raw_clarification_answer`, and
`test_audit_evidence_does_not_expose_headers_cookies_tokens`
(`tests/test_step66c3_workroom_audit_visibility.py`), which each deliberately seed a forbidden field
into `artifact_refs` and assert the endpoint strips it.

## 4. RBAC

| Role | Access |
| --- | --- |
| Platform Admin | allowed |
| Agent Operator | allowed |
| Security/Compliance Reviewer | allowed, read-only (workroom mutation remains denied for this role) |
| PM/Engineering Lead | allowed |
| Requester | denied by default — audit evidence is a more sensitive surface than the workroom itself (RBAC-denial reasons + body hashes across the whole task, not just messages the role already sees) |
| Reviewer/Approver | denied by default — same reasoning |

A denial emits `DECISION_AUDIT_EVIDENCE_RBAC_DENIED` (`audit_evidence_rbac_denied`) via the existing
`task_api._audit` publisher, matching the pattern of every other RBAC denial in this module.

## 5. Test evidence

`tests/test_step66c3_workroom_audit_visibility.py`: `test_audit_evidence_platform_admin_allowed`,
`test_audit_evidence_agent_operator_allowed`,
`test_audit_evidence_security_compliance_reviewer_allowed_read_only`,
`test_audit_evidence_pm_engineering_lead_allowed`, `test_audit_evidence_requester_denied`,
`test_audit_evidence_reviewer_approver_denied`, `test_audit_evidence_task_not_found`,
`test_audit_evidence_returns_safe_metadata_only`,
`test_audit_evidence_allowlist_excludes_forbidden_fields`.

## 6. Frontend

`AuditEvidenceSection` (`TaskWorkroom.tsx`) fetches this endpoint independently of the main workroom
load. `403` renders a readable restricted message, not a page-breaking error; success renders only
the safe fields via plain React text interpolation (no raw body rendering path exists to begin with).

## 7. Statement

No raw message body exposed through audit evidence. No workflow dispatch occurred. No workflow
resume occurred. No external action occurred. No production action occurred.
production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
