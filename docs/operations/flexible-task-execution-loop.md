# Flexible Task Execution Loop (Stage 27)

The platform now supports Discord-driven task intake with a deterministic
"figure out what kind of task this is, ask if unclear, mark when ready"
loop. Three execution modes exist; only one of them turns on Scrum
ceremony, and Scrum only fires when the requester explicitly asks for
it.

## How to create a task from Discord

```
curl -sS -X POST http://localhost:8007/discord/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"/ai task type=dev.test description=\"implement a new /healthz endpoint\" task_id=demo-1","channel_id":"sandbox","user_id":"alice"}'
```

The discord-gateway parses the message, dispatches it to the orchestrator,
and the intake → requirement → development → qa → devops agent pipeline
runs the same as before. New in Stage 27: requirement-agent creates a
`task_work_items` row, every agent appends to `agent_discussions`, and
the operations API surfaces the result.

## Execution modes

The classifier (`shared/sdk/task_execution/mode_classifier.py`) is
deterministic; it does NOT call any LLM.

| Mode | Trigger | Behaviour |
| --- | --- | --- |
| `simple_task` | Default when no dev/Scrum keyword is detected | Lightweight bookkeeping; no Scrum fields; agent pipeline runs but may complete fast |
| `delivery_task` | Description mentions any dev keyword (`build`, `implement`, `develop`, `fix`, `refactor`, `code`, `test`, `API`, `UI`, `feature`, `bug`, `開發`, `修正`, `實作`, `測試`, …) OR `request_type` starts with `dev.` | Full agent pipeline runs; GitHub dry-run PR is created |
| `scrum_project` | Description mentions Scrum vocabulary (`scrum`, `sprint`, `backlog`, `acceptance criteria`, `definition of done`, `DoD`, `project kickoff`, `敏捷`, `衝刺`, `待辦清單`, `驗收標準`, `完成定義`) | All of `delivery_task` + `scrum_enabled=true`, `acceptance_criteria` + `definition_of_done` drafts, `scrum_metadata.project_kickoff=true` |

### When NOT to use Scrum

`simple_task` and `delivery_task` do not get `acceptance_criteria`,
`definition_of_done`, or `scrum_metadata`. The classifier only flips to
`scrum_project` when the requester (or the task description) contains
an explicit Scrum keyword. The platform never invents Scrum ceremony
on the operator's behalf.

## Needs-clarification flow

If the description is shorter than 6 non-whitespace characters, or
contains a clarification signal (`TBD`, `to be decided`, `need
clarification`, `please clarify`, `?`, `？`, `請再確認`, `請補充`,
`需要釐清`, `缺少`, …), the requirement-agent:

1. Sets `task_work_items.status = needs_clarification`.
2. Writes a row in `clarification_requests` (status=open) with a
   default question asking for more detail.
3. Publishes `task.needs_clarification` notification +
   `clarification_requested` audit decision_type.
4. **Does NOT publish to `stream.development`.** The downstream
   agent pipeline therefore stays idle until the work item is
   re-classified.

The operator can see open clarifications via:

```
curl -sS http://localhost:8007/discord/clarifications/<task_id> | jq
```

## How to answer a clarification

```
curl -sS -X POST http://localhost:8007/discord/clarifications/<clarification_id>/answer \
  -H "Content-Type: application/json" \
  -d '{"answer":"please add a /healthz endpoint returning 200","user_id":"alice"}'
```

The discord-gateway:

1. Writes the answer to `clarification_requests.user_response`
   (`status=answered`).
2. Publishes a `clarification.answered` notification + audit row.
3. Calls
   `POST /workflow/resume-after-clarification/<task_id>` on the
   orchestrator. The orchestrator re-classifies the task using ONLY
   the user's answers (so the original "TBD" doesn't keep the work
   item stuck), flips the work item to
   `ready_for_development`, and republishes the intake event on
   `stream.tasks` so the agent pipeline runs.

## How to resume the workflow manually

If you have an out-of-band answer:

```
curl -sS -X POST http://localhost:8000/workflow/resume-after-clarification/<task_id>
```

Safe to call repeatedly. Open clarifications block the resume; the
endpoint returns `resumed=false, reason="open_clarifications_pending"`.

## How to view agent discussions

```
curl -sS http://localhost:8000/operations/tasks/work-items/<task_id> | jq '.agent_discussions'
```

Each row carries `agent`, `role`, `message_type` (analysis | question |
assumption | risk | recommendation | decision | execution_plan |
validation_note), `content`, `confidence`, and free-form `references`.

## How to view the execution plan

```
curl -sS http://localhost:8000/operations/workflows/<task_id> | jq '.task_execution.execution_plan'
```

The execution plan is a free-form JSON object containing the agent
pipeline + production_executed + the classifier reason. Stage 27 ships
a default 5-stage plan; later stages may write richer per-task plans.

## What's NOT in this stage

* **No production deploy.** `production_executed=true` count must stay
  at `0` on every stack. The platform's existing safety counters
  enforce this.
* **No real LLM.** All classification, clarification, and discussion
  content is rule-based or template-generated. There is no
  `openai`/`anthropic` SDK call anywhere in the loop.
* **No real Discord write** outside the Stage 22 opt-in
  `/discord/real/test-message` route, which is unchanged.
* **No real code generation.** development-agent still produces a
  mock `code_change` artifact. Real code generation is deferred to a
  future stage.
* **No backlog management UI.** Scrum metadata is captured but the
  platform does not yet draw a Kanban board or run sprint ceremonies.

## Operations summary

`GET /operations/summary` now carries a `task_execution_summary`
section with per-mode counts:

```
{
  "task_execution_summary": {
    "total_work_items": 7,
    "simple_task_count": 3,
    "delivery_task_count": 3,
    "scrum_project_count": 1,
    "needs_clarification_count": 1,
    "ready_for_development_count": 5,
    "blocked_count": 0
  }
}
```

## Metrics

| Metric | Labels |
| --- | --- |
| `task_work_items_total` | execution_mode, status |
| `task_execution_mode_total` | execution_mode, request_type |
| `clarification_requests_total` | status (requested / answered) |
| `task_ready_for_development_total` | execution_mode |
| `task_blocked_total` | reason |
| `agent_discussions_total` | agent, message_type |

## Spans

| Span name | Attributes |
| --- | --- |
| `task_execution.create_work_item` | task_id, workflow_id, execution_mode, status |
| `task_execution.classify_mode` | task_id, workflow_id |
| `task_execution.create_clarification` | task_id, workflow_id, requested_by_agent |
| `task_execution.answer_clarification` | clarification_id |
| `task_execution.record_agent_discussion` | task_id, workflow_id, agent, message_type |

## Audit decision_types

* `clarification_requested`
* `clarification_answered`
* `task_ready_for_development`
* `agent_discussion_recorded` (reserved for a future enhancement —
  Stage 27 piggybacks on the StreamAgent audit row)
