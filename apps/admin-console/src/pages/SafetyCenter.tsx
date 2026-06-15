import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getSafetySummary } from "../api/operations";

export function SafetyCenter() {
  return (
    <AsyncView load={getSafetySummary}>
      {(d) => (
        <>
          <h2>Safety Center</h2>
          <KeyValueTable data={d as Record<string, unknown>} />
        </>
      )}
    </AsyncView>
  );
}
