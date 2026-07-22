# Current-State Assessment — Step 66C.4-P

> **Planning document only. Read-only inspection. No backend/frontend runtime change. No API
> implementation change. No database schema change. No migration created. No workflow change. No
> scheduler activated. No dispatch/resume executed. No deployment.**

All facts below are verified directly against repository source and the internal test runtime
(read-only), not assumed from prior stage prose.

## 1. Existing `operator_clarification_requests` table

Source: `migrations/030_workroom_clarification_foundation.sql:56-77`.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | UUID PK | no | `uuid_generate_v4()` |
| `task_id` | UUID | no | FK -> `operator_tasks(id)` |
| `question_message_id` | UUID | no | FK -> `task_messages(id)` |
| `status` | TEXT | no | CHECK IN (`open`,`answered`,`expired`,`canceled`), default `open` |
| `question` | TEXT | no | CHECK nonempty, CHECK length <= 4000 |
| `requested_by_type` / `requested_by_id` | TEXT | no | |
| `assigned_to` | TEXT | yes | |
| `due_at` | TIMESTAMPTZ | **no** | set at insert = now()+72h (app layer) |
| `reminder_at` | TIMESTAMPTZ | **no** | set at insert = now()+24h (app layer) |
| `answered_at` | TIMESTAMPTZ | yes | set by the CAS claim |
| `answer_message_id` | UUID | yes | FK -> `task_messages(id)` |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | default `now()` |

Indexes: `idx_operator_clarification_requests_task_id`, `idx_operator_clarification_requests_status`.

**Fields already present that this stage needs:** `due_at`, `reminder_at`, `answered_at`, `status`
enum (`open`/`answered`/`expired`/`canceled`).

**Fields NOT present (confirmed by direct grep, not assumed):** `reminder_due_at` (redundant with
existing `reminder_at`), `reminder_sent_at`, `reminder_count`, `expires_at`/`expired_at`
(redundant with existing `due_at` + `status='expired'`), `resume_eligible_at`,
`resume_requested_at`, `resume_requested_by`, `resume_authorized_at`, `resume_dispatched_at`,
`answered_by` (recoverable only indirectly via `answer_message_id` -> `task_messages.sender_id`),
`version`/`lock_version` (no optimistic-lock column on this table).

## 2. Task status enum

Source: `shared/sdk/tasks/models.py` (backend) and `apps/admin-console/src/tasks/taskTypes.ts`
(frontend) -- **identical, 17 values**: `draft, submitted, intake_review,
clarification_needed, clarification_expired, approved_for_execution, running, waiting_approval,
blocked, failed, delivery_ready, changes_requested, qa_rerun_requested, accepted, rejected,
archived, canceled`.

`clarification_expired` **already exists** in the enum (defined since Step 66B.1) but **no code
path anywhere in `apps/orchestrator/src` currently sets it** (confirmed via grep across
`workroom_api.py`, `workroom_store.py`, `task_api.py` -- zero hits). This transition is entirely
unimplemented today; it is pure Step 66C.4 scope. `clarification_needed`, `blocked`, and
`waiting_approval` also already exist -- there is no generic `waiting` value, and none is needed
(see lifecycle-and-time-contract.md).

Same CHECK constraint duplicated at the DB layer: `migrations/029_operator_task_api_foundation.sql`
(`chk_operator_tasks_status`).

## 3. Timestamp semantics

All timestamp columns across `operator_tasks`, `task_messages`, `operator_clarification_requests`
are `TIMESTAMPTZ` (timezone-aware). App layer uses `datetime.now(timezone.utc)` consistently
(`shared/sdk/tasks/workroom_store.py`). No naive-datetime columns found in any relevant table.

## 4. Existing CAS / idempotency precedent

`WorkroomStore.claim_clarification_answer` (`shared/sdk/tasks/workroom_store.py:132-157`):

```sql
UPDATE operator_clarification_requests
SET status='answered', answered_at=now(), updated_at=now()
WHERE id=$1 AND status='open'
RETURNING *
```

The `WHERE status='open'` guard is the compare-and-swap: a losing concurrent UPDATE returns no
row. `answer_clarification` (`apps/orchestrator/src/workroom_api.py`) calls this claim BEFORE
creating the answer message/audit event specifically so a lost race never has a side effect. This
is the direct, reusable precedent for both the reminder-claim and expiry-claim queries this stage
must design (see race-condition-and-failure-analysis.md).

Other schema idempotency precedent: `operator_action_requests.idempotency_key TEXT NOT NULL
UNIQUE` and `action_key TEXT NOT NULL UNIQUE` (`migrations/023_admin_console_operator_actions.sql`).

## 5. Existing APIs (all in `apps/orchestrator/src/workroom_api.py`, `task_api.py`)

| Endpoint | RBAC | Idempotency | Notes |
| --- | --- | --- | --- |
| `POST /tasks/{id}/clarifications` | `pm_engineering_lead`, `platform_admin`, `agent_operator` | none (double-call creates two rows) | computes `due_at`/`reminder_at` server-side |
| `GET /tasks/{id}/workroom` | all 6 roles (Requester scoped to own task) | n/a (read) | returns embedded `clarification_requests`, `dispatch_enabled: false`, `resume_dispatch_enabled: false` |
| `POST /tasks/{id}/clarifications/{cid}/answer` | `requester` (own task), `pm_engineering_lead`, `platform_admin` | CAS via `status='open'` guard | 409 `clarification_already_answered`, 409 `invalid_state_for_answer:{status}` |
| `POST /tasks/{id}/workroom/messages` | all except `security_compliance_reviewer` | none | |
| `GET /tasks/{id}/audit-evidence` | `platform_admin`, `agent_operator`, `security_compliance_reviewer`, `pm_engineering_lead` | n/a (read) | allowlist projection, never raw bodies |
| `GET/POST /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/submit` | per TASK_ROLES | n/a | |

**No resume-related endpoint exists at all** -- `dispatch_enabled` and `resume_dispatch_enabled`
are hardcoded Python/JS literal `false` in every response (`workroom_api.py`, `task_api.py`), not a
config flag with a wired-up code path. There is no `/resume` route, no dispatch trigger route, no
resume method on any store, anywhere in the repository.

## 6. Existing schedulers/workers

`retry-scheduler` (`apps/retry-scheduler/src/{main.py,scheduler.py}`) is a **Redis Streams
consumer**, not a DB-poller and not interval/cron-based: it loops `XREADGROUP` against
`stream.deadletter` (consumer group `retry-scheduler-group`), using `asyncio.sleep(delay)` per
message for retry backoff, not a global timer. It also serves `GET /deadletter` and
`POST /deadletter/replay/{id}`. This service is itself the DLQ/replay worker (no separate one
exists).

**No time-based/cron scheduler pattern exists anywhere in this repository** -- no APScheduler, no
Celery, no croniter. Every background loop found (`audit-worker`, `notification-worker`,
`workflow_events.py`, `stream_agent.py`) is the same idiom: event-driven Redis Streams consumption,
not "wake up every N seconds and check for a due timestamp." **A time-based due-timestamp checker
would be new architecture for this project** (see scheduler-architecture-decision.md).

Redis Streams + consumer groups are used extensively (`shared/sdk/event_bus/redis_streams.py`).
No outbox-table-plus-relay pattern exists anywhere (grepped `*.py`/`*.sql` for `outbox`, zero hits).

## 7. Frontend current state

`/clarification-reminders` is confirmed still a `PlaceholderPage` (`apps/admin-console/src/App.tsx`,
`requiredStep="66C.4"`; nav entry in `Nav.tsx` badged "Soon"). `TaskWorkroom.tsx` already renders
`ClarificationCard` with `status`/`question`/`reminder_at`/`due_at`/`answered_at` and conditionally
an `AnswerForm` only when `status === "open"` -- there is no distinct "reminder sent" or "expiring
soon" visual state today.

## 8. Prior planning/decision docs

- Stage 66A.3 Q2 (`source/progress.md`): "clarification timeout (24h reminder / 72h
  blocked-expired, project-config, owner extend once)" -- operator-confirmed. Implemented today as
  fixed constants `CLARIFICATION_REMINDER_HOURS = 24` / `CLARIFICATION_DUE_HOURS = 72`
  (`shared/sdk/tasks/workroom_models.py`), explicitly commented "fixed defaults only in 66C.1" --
  project-configurability and "owner extend once" were deferred, and **neither is implemented
  anywhere** (no extend endpoint/column found).
- The Master Plan (`canonical-milestone-manifest.md`, `next-executable-stage-sequence.md`) already
  states the scheduler mechanism decision is **not yet made** and is this stage's own job to
  decide, and reconfirms no new task-status value is needed.
- `docs/test/step66c3-answered-twice-guard-record.md` documents the exact root-cause/fix/
  verification pattern for the CAS guard above -- the direct template for this stage's
  reminder-claim and expiry-claim queries.

## 9. Read-only runtime evidence (test runtime, masked host)

```text
production_executed_true_count: 0 (confirmed via /operations/safety, read-only GET)
Container health: aiagents-test-orchestrator-1, audit-service-1, audit-worker-1,
  retry-scheduler-1, postgres-1 all "Up 4 days (healthy)"
operator_clarification_requests current state: 1 row status=open, 5 rows status=answered,
  0 rows status=expired, 0 rows status=canceled (confirmed via read-only SELECT COUNT ... GROUP BY)
```

Zero rows with `status='expired'` is additional direct confirmation that the expiry transition has
never executed in this environment -- consistent with the code-level finding above.

## 10. Migration necessity

**No migration is required to add the fields listed as reusable** (`due_at`, `reminder_at`,
`answered_at`, `status`) -- they already exist. **New fields ARE required** for reminder-sent
tracking, resume lifecycle tracking, and answerer identity -- see data-model-contract.md for the
full proposed field list, none of which is created by this stage (planning only).

## Statement

Planning document only. Read-only inspection. No backend/frontend runtime change. No API
implementation change. No database schema change. No migration created. No workflow change. No
scheduler activated. No dispatch/resume executed. No deployment.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
