import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import { getAgentExecutions } from "../api/operations";

type Dict = Record<string, unknown>;

// Step 64E.4B -- formal Agent Executions product page. Surfaces the demo
// agent pipeline (intake -> requirement -> development -> qa -> devops) from
// the read-only /operations/agent-executions endpoint. GET-only; no raw
// error/metadata fields are exposed by the endpoint.
export function AgentExecutions() {
  return (
    <AsyncView load={getAgentExecutions}>
      {(d) => {
        const rows = ((d as Dict).executions as Dict[]) || [];
        const count = (d as Dict).count;
        return (
          <>
            <h2>Agent Executions</h2>
            <p className="note">
              Read-only agent execution pipeline for the staging demonstration (non-production).
              production_executed=false; no production action.
            </p>
            <p className="note">count: {fmtCount(count)}</p>
            <EvidenceTable
              rows={rows}
              cols={["agent", "status", "task_id", "started_at", "completed_at"]}
              empty="No agent executions yet"
            />
          </>
        );
      }}
    </AsyncView>
  );
}

function fmtCount(v: unknown): string {
  return v === null || v === undefined ? "—" : String(v);
}
