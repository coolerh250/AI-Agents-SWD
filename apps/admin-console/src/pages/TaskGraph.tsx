import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getLatestDeliveryState } from "../api/operations";

// v0: surfaces the latest pilot's project context. A full per-project work-item
// graph drill-down (table + dependencies; optional React Flow) is future work;
// this fallback table keeps the page renderable without extra dependencies.
export function TaskGraph() {
  return (
    <AsyncView load={getLatestDeliveryState}>
      {(d) =>
        d.latest_pilot ? (
          <>
            <h2>Task Graph</h2>
            <p className="note">
              Latest project context. Per-project work-item graph drill-down is planned.
            </p>
            <KeyValueTable data={d.latest_pilot} />
          </>
        ) : (
          <>
            <h2>Task Graph</h2>
            <EmptyState message="No project graph available yet" />
          </>
        )
      }
    </AsyncView>
  );
}
