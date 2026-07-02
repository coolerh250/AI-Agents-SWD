import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import { getQaRuns, getCodeWorkspaces } from "../api/operations";

type Dict = Record<string, unknown>;

const loadQaCode = () =>
  Promise.all([getQaRuns(), getCodeWorkspaces()]).then(([qa, code]) => ({ qa, code }));

// Step 64E.4B -- formal QA / Code product page. Surfaces QA validation runs
// (/operations/qa/runs) and code workspace/output summaries
// (/operations/code/workspaces). GET-only; raw generated code is never shown --
// only shaped workspace/run summary fields.
export function QaCode() {
  return (
    <AsyncView load={loadQaCode}>
      {({ qa, code }) => {
        const qaRuns = ((qa as Dict).validation_runs as Dict[]) || [];
        const qaCount = (qa as Dict).count;
        const workspaces = ((code as Dict).workspaces as Dict[]) || [];
        const codeCount = (code as Dict).count;
        return (
          <>
            <h2>QA / Code</h2>
            <p className="note">
              Read-only QA and code evidence for the staging demonstration (non-production). No raw
              generated code is displayed; summaries only. If a source reports a count without
              per-row detail, the count is still shown.
            </p>
            <section>
              <h3>QA Runs (count: {fmtCount(qaCount)})</h3>
              <EvidenceTable
                rows={qaRuns}
                cols={["task_id", "status", "final_result", "workflow_id"]}
                empty="No QA runs yet"
              />
            </section>
            <section>
              <h3>Code Workspaces (count: {fmtCount(codeCount)})</h3>
              <EvidenceTable
                rows={workspaces}
                cols={["workspace_id", "task_id", "status", "execution_mode", "created_at"]}
                empty="No code workspaces yet"
              />
            </section>
          </>
        );
      }}
    </AsyncView>
  );
}

function fmtCount(v: unknown): string {
  return v === null || v === undefined ? "—" : String(v);
}
