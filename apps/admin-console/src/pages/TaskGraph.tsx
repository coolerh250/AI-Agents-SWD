import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import { KeyValueTable } from "../components/KeyValueTable";
import { getLatestDeliveryState, getWorkflows } from "../api/operations";

type Dict = Record<string, unknown>;

const loadGraph = () =>
  Promise.all([getLatestDeliveryState(), getWorkflows()]).then(([pilot, workflows]) => ({
    pilot,
    workflows,
  }));

// Step 64E.4B -- Workflows / Task Graph. Renders the read-only workflow/stage
// trace from /operations/workflows (task_id / stage / status / production_executed)
// in addition to the latest project context. GET-only; a full per-project graph
// drill-down remains future work, but the workflow table is always renderable.
export function TaskGraph() {
  return (
    <AsyncView load={loadGraph}>
      {({ pilot, workflows }) => {
        const rows = ((workflows as Dict).workflows as Dict[]) || [];
        const latestPilot = (pilot as { latest_pilot?: Record<string, unknown> }).latest_pilot;
        return (
          <>
            <h2>Workflows / Task Graph</h2>
            <p className="note">
              Read-only workflow/stage trace for the staging demonstration (non-production).
              production_executed=false; no production action.
            </p>
            <section>
              <h3>Workflows</h3>
              <EvidenceTable
                rows={rows}
                cols={[
                  "task_id",
                  "stage",
                  "approval_status",
                  "risk_level",
                  "production_executed",
                  "updated_at",
                ]}
                empty="No workflows yet"
              />
            </section>
            <section>
              <h3>Latest project context</h3>
              {latestPilot ? (
                <KeyValueTable data={latestPilot} />
              ) : (
                <p className="note">No latest project context available yet.</p>
              )}
            </section>
          </>
        );
      }}
    </AsyncView>
  );
}
