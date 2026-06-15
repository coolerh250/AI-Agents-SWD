import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getRegressionSummary } from "../api/operations";

export function RegressionStatus() {
  return (
    <AsyncView load={getRegressionSummary}>
      {(d) => (
        <>
          <h2>Regression / Verification</h2>
          <KeyValueTable data={d as Record<string, unknown>} />
        </>
      )}
    </AsyncView>
  );
}
