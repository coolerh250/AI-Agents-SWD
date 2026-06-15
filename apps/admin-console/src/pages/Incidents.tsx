import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getOverview } from "../api/operations";

export function Incidents() {
  return (
    <AsyncView load={getOverview}>
      {(d) => {
        const inc = d.incidents_summary || {};
        const total = Object.values(inc).reduce((a, b) => a + Number(b || 0), 0);
        return (
          <>
            <h2>Incidents</h2>
            {total > 0 ? (
              <KeyValueTable data={inc} />
            ) : (
              <EmptyState message="No incidents" />
            )}
          </>
        );
      }}
    </AsyncView>
  );
}
