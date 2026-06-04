# Stage 31 — LLM Proposal Promotion

Promotion is the act of converting an `llm_proposal_artifacts` row
into `code_change_artifacts` inside the controlled workspace. It is
guarded by **three** layers; all three must agree.

## Layers

1. **LLM safety policy** (`shared.sdk.llm.policy`). Re-scans the
   proposal. Refuses if any change violates `path_blocked`,
   `change_type_blocked`, `secret_like_content`,
   `destructive_content`, `too_many_files`, `content_too_large`, or
   `schema_invalid`.
2. **Approval policy evaluator**
   (`shared.sdk.approval_policy.evaluate_action`). Looks for an
   active `human_approval_policies` row that authorises the
   `llm_proposal_promote` action under the proposal's paths +
   files_changed count. Hard safety rails ALWAYS win.
3. **Explicit approval row**
   (`llm_proposal_approvals.status='approved'`). The fallback when
   no policy authorises automatically.

The promotion succeeds only when (1) returns `allowed=True` AND
((2) returns `allowed=True` OR (3) yields an approved row). Even
with all three green, the platform STILL re-checks the workspace
allowlist + denylist before persisting each file.

## Endpoints

* `POST /llm/proposals/{proposal_id}/approval/request` — open a
  pending approval.
* `POST /llm/proposals/{proposal_id}/approval/approve` — approve
  the pending row.
* `POST /llm/proposals/{proposal_id}/approval/reject` — reject the
  pending row.
* `POST /llm/proposals/{proposal_id}/promote` — attempt the
  promotion. Returns the constructed `LLMProposalPromotion` plus
  the evaluator result, accepted files, refused files, and the
  decision source (`explicit_approval` or `policy_allows`).

## Promotion modes

The `promotion_mode` written on `llm_proposal_promotions` records
the path taken:

* `manual` — promotion ran via explicit `per_action` approval.
* `policy_allowed` — promotion authorised by a non-delegated active
  policy (`per_feature` or `per_stage`).
* `delegated_agent` — promotion authorised by a delegated policy.

## Status lifecycle

| Status                | Meaning                                                    |
| --------------------- | ---------------------------------------------------------- |
| `requested`           | Row created; promotion about to run.                       |
| `promoted`            | At least one accepted file written into the workspace.     |
| `validation_failed`   | The proposal passed approval but every file was refused.   |
| `qa_passed`           | (Reserved) QA gate post-promotion succeeded.               |
| `qa_blocked`          | (Reserved) QA gate post-promotion blocked.                 |
| `blocked_by_policy`   | Refused by LLM safety policy OR approval policy.           |
| `failed`              | Internal error during promotion.                           |
| `canceled`            | Operator canceled the promotion.                           |

## QA gate still applies

Promoted artifacts enter `code_change_artifacts` exactly like
Stage 28's deterministic generator output. The Stage 29 QA loop
runs against them as usual; a QA block (`blocked_for_human_review`)
still halts the workflow. The promotion is observational, not a
shortcut around QA.

## No PR merge

Promotion does not create a real GitHub PR. The Stage 28 dry-run
demo-PR path is the only emitter; the controlled-real GitHub gate
(Stage 23) is untouched.

## Failure modes

| Cause                                           | Promotion status      |
| ----------------------------------------------- | --------------------- |
| Unknown proposal id                             | `404 not found`       |
| `proposal.status='blocked'`                     | `blocked_by_policy`   |
| LLM safety policy refuses (`allowed=false`)     | `blocked_by_policy`   |
| Hard safety rail (denylist, secret, …)          | `blocked_by_policy`   |
| No active policy AND no `approved` approval row | `blocked_by_policy`   |
| All file paths refused by workspace allowlist   | `validation_failed`   |
| At least one file written                       | `promoted`            |
