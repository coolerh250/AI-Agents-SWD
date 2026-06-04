# Stage 31 — Flexible Human Approval Policy

Stage 31 introduces a policy layer that lets a human operator pick
the **granularity** of approval for an LLM proposal promotion, a QA
auto-fix, or any other audit-bearing action — without ever
overriding the hard safety rails the platform ships with.

## Approval modes

| Mode          | Use when …                                                                | Authorises automatically? |
| ------------- | ------------------------------------------------------------------------- | ------------------------- |
| `per_action`  | Every single action needs a fresh human approve / reject.                 | No. Explicit only.        |
| `per_feature` | One feature / task should get bounded automation.                          | Yes, inside its constraints. |
| `per_stage`   | One workflow stage (e.g. `code_generation`) should get bounded automation. | Yes, inside its stage.     |
| `delegated`   | The agent acts on behalf of the operator inside hard constraints.         | Yes, while constraints hold. |

`per_action` is the default and the safest. The other three modes
require a non-empty `allowed_actions` + `allowed_paths`; `delegated`
additionally requires the full constraint set (see below).

## Constraints

| Field                    | Required by                  |
| ------------------------ | ---------------------------- |
| `allowed_actions`        | `per_feature`, `per_stage`, `delegated` |
| `allowed_paths`          | `per_feature`, `per_stage`, `delegated` |
| `allowed_stages`         | `per_stage`                 |
| `allowed_agents`         | optional everywhere         |
| `denied_paths`           | `delegated`                 |
| `max_actions`            | `delegated`                 |
| `max_files_changed`      | `delegated`                 |
| `max_auto_fix_attempts`  | `delegated`                 |
| `expires_at`             | `delegated`                 |

A `delegated` policy that misses any required field is refused with
`HTTP 400 delegated_missing:<field>`.

## Hard safety policy (always wins)

The following actions can **never** be authorised by any policy, in
any mode, by anyone:

* `production_deploy`
* `real_github_write`
* `real_github_pr_merge`
* `branch_protection_modification`
* `force_push`
* `delete_file`
* `secret_write`
* `destructive_command`
* `real_llm_network_call`
* `denylist_path_mutation`

Additionally, even a policy that lists an allowlisted action will be
refused if the action's content:

* matches a known secret-shape pattern (token / key / private key),
* matches a destructive command pattern (`rm -rf`, `DROP TABLE`,
  `git push --force`, …), or
* touches a denylisted path (`.github/*`, `infra/*`, `migrations/*`,
  `shared/sdk/secrets/*`, `source/progress.md`, `*.env`, `*.pem`,
  `*.key`, `*secret*`, …).

The `EvaluationResult.hard_policy_block` field flips `True` when the
refusal came from the hard rails. The reason starts with
`hard_safety:`.

## Approval vs promotion

* **Approval** is the operator's decision on a proposal:
  `POST /llm/proposals/{id}/approval/request` then `…/approve` /
  `…/reject`.
* **Promotion** is the act of materialising the approved proposal
  into the controlled code workspace:
  `POST /llm/proposals/{id}/promote`.

`per_action` mode requires an `approved` row in
`llm_proposal_approvals` before `…/promote` accepts the request. The
other three modes can authorise via an active
`human_approval_policies` row instead — the promotion records
`decision_source=policy_allows` and the policy's `actions_used`
counter bumps.

## Delegated mode limitations

A delegated policy:

* MUST list every action it allows (`allowed_actions`).
* MUST set a finite `max_actions`. The orchestrator increments
  `actions_used` on every authorised action; the evaluator refuses
  the next one once `actions_used >= max_actions`.
* MUST set a finite `max_files_changed`. A proposal that exceeds it
  is refused even when the action and paths are otherwise allowed.
* MUST set `max_auto_fix_attempts` so the QA auto-fix loop can't
  spin forever.
* MUST set `expires_at`. After expiry the evaluator refuses with
  `policy_expired`.
* MUST set `denied_paths` (in addition to the platform-wide
  denylist). The evaluator stacks them.
* CANNOT authorise any `HARD_SAFETY_ACTIONS` — even if listed.

## Revoke / expire

```
POST /approval-policies/{policy_id}/revoke
{"revoked_by": "operator", "reason": "feature complete"}
```

A revoked policy becomes `status=revoked` and the evaluator refuses
new actions against it. The audit trail keeps the original creation
+ revocation rows.

Policies with an `expires_at` in the past are treated as
`policy_expired`. The evaluator refuses; the row is left alone so an
operator can inspect history.

## Operations queries

* `GET /operations/approval-policies` — list policies (filterable by
  `task_id`, `workflow_id`, `status`, `approval_mode`, `limit`).
* `GET /operations/approval-policies/{task_id}` — task summary
  (active count, revoked count, promotions).
* `GET /operations/approval-decisions/{task_id}` — every recorded
  decision row, newest first.
* `GET /operations/workflows/{task_id}.approval_policy` — the
  embedded section with `active_policies`, `approval_mode`,
  `decisions`, `delegated_actions_used`, `delegated_actions_remaining`,
  `revoked_policies`, `expired_policies`, `hard_policy_blocks`,
  `promotions`.
* `GET /operations/summary.approval_policy_summary` — aggregated
  counters (`total_policies`, `active_policies`, `delegated_policies`,
  `per_feature_policies`, `per_stage_policies`, `revoked_policies`,
  `total_decisions`, `approved_decisions`, `rejected_decisions`,
  `total_promotions`, `promoted_count`, `blocked_by_policy_count`).
* `GET /operations/safety` — `delegated_agent_enabled`,
  `active_delegated_policies`, `hard_policy_enforced`,
  `production_delegation_allowed=false`,
  `real_github_delegation_allowed=false`.

## Discord operator commands

The discord-gateway proxies the orchestrator's policy + approval +
promotion endpoints so a Discord-only operator can drive the flow:

* `POST /discord/approval-policies` → orchestrator `/approval-policies`
* `GET  /discord/approval-policies/{task_id}` →
  `/operations/approval-policies/{task_id}`
* `POST /discord/approval-policies/{policy_id}/revoke` →
  `/approval-policies/{policy_id}/revoke`
* `POST /discord/llm/proposals/{proposal_id}/approve` →
  `/llm/proposals/{proposal_id}/approval/approve`
* `POST /discord/llm/proposals/{proposal_id}/reject` →
  `/llm/proposals/{proposal_id}/approval/reject`
* `POST /discord/llm/proposals/{proposal_id}/promote` →
  `/llm/proposals/{proposal_id}/promote`

`/discord/tasks/{task_id}` carries `approval_mode`,
`active_approval_policy`, `delegated_actions_used`,
`delegated_actions_remaining`, `latest_approval_decision`, and
`llm_promotion_status`.

## Audit / notification

| audit `decision_type`                | notification `event_type`        |
| ------------------------------------ | -------------------------------- |
| `approval_policy_created`            | `approval.policy_created`        |
| `approval_policy_activated`          | `approval.policy_activated`      |
| `approval_policy_revoked`            | `approval.policy_revoked`        |
| `approval_policy_expired`            | `approval.policy_expired`        |
| `approval_policy_action_allowed`     | `approval.action_allowed`        |
| `approval_policy_action_blocked`     | `approval.action_blocked`        |
| `llm_proposal_approval_requested`    | —                                |
| `llm_proposal_approved`              | `llm.proposal_approved`          |
| `llm_proposal_rejected`              | `llm.proposal_rejected`          |
| `llm_proposal_promoted`              | `llm.proposal_promoted`          |
| `llm_promotion_blocked`              | `llm.promotion_blocked`          |

Every `artifact_refs` carries `production_executed=false`. The
audit + notification publishers use the existing `stream.audit` +
`stream.notifications` paths — no direct HTTP write.

## Limitations

* **No production deploy can be delegated.** Period.
* **No real GitHub write can be delegated.** Period.
* **No `delete_file` action exists.** Stage 28 forbade `delete` at
  the workspace policy level; Stage 31 reaffirms it at the
  approval policy level.
* **No silent over-ride.** Every promotion writes an audit row +
  notification + decision row; the operator can revoke at any time.
* **No real LLM network call.** Stage 30's external-provider guard
  still applies — Stage 31 does not introduce a new bypass.
