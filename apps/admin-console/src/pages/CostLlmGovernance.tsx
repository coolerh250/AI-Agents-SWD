import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getOverview } from "../api/operations";

export function CostLlmGovernance() {
  return (
    <AsyncView load={getOverview}>
      {(d) => {
        const llm = d.llm_summary || {};
        const hasData = Object.values(llm).some((v) => Number(v) > 0);
        return (
          <>
            <h2>Cost / LLM Governance</h2>
            {hasData ? (
              <KeyValueTable data={llm} />
            ) : (
              <EmptyState message="No usage data available" />
            )}
          </>
        );
      }}
    </AsyncView>
  );
}
