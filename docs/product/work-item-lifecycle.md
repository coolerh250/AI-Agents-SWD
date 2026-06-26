# Work-item Lifecycle (Step 57)

States: created → triaged → ready_for_dispatch → dispatched → in_progress → completed,
with waiting_approval, blocked, cancelled, failed, archived. Enforced by
`shared/sdk/work_items/lifecycle.py` against
[`infra/delivery/work-item-lifecycle.yaml`](../../infra/delivery/work-item-lifecycle.yaml).

- `created` cannot jump straight to `dispatched` (must triage first).
- `completed`/`cancelled`/`archived` are terminal; `completed` cannot be re-dispatched
  (create a new work item).
- `failed` may be manually re-dispatched (→ ready_for_dispatch).
- **production_effect=true ⇒ waiting_approval** (never dispatched directly).
- Human acceptance ≠ deployment approval. No production action is executed.
