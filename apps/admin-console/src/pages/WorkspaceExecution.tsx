import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getLatestDeliveryState } from "../api/operations";

// v0: shows the latest workspace execution summary (status / file manifest /
// tests via the pilot context). Raw generated code is never displayed.
export function WorkspaceExecution() {
  return (
    <AsyncView load={getLatestDeliveryState}>
      {(d) =>
        d.latest_pilot ? (
          <>
            <h2>Workspace Execution</h2>
            <p className="note">Controlled-only; file manifest / summaries only, no raw code.</p>
            <KeyValueTable data={d.latest_pilot} />
          </>
        ) : (
          <>
            <h2>Workspace Execution</h2>
            <EmptyState message="No workspace execution available yet" />
          </>
        )
      }
    </AsyncView>
  );
}
