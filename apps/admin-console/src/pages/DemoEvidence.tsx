import { useEffect, useState } from "react";
import { LoadingState } from "../components/LoadingState";
import { EmptyState } from "../components/EmptyState";
import {
  getDeliveryProjects,
  getDeliveryWorkItems,
  getDeliveryWorkItemEvents,
  getAgentExecutions,
  getWorkflows,
  getQaRuns,
  getCodeWorkspaces,
  getSafety,
} from "../api/operations";

type Dict = Record<string, unknown>;

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Table({ rows, cols }: { rows: Dict[]; cols: string[] }) {
  if (!rows || rows.length === 0) return <EmptyState message="No records found" />;
  return (
    <table className="kv">
      <thead>
        <tr>
          {cols.map((c) => (
            <th key={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c) => (
              <td key={c}>{fmt(r[c])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

async function safe(p: Promise<Dict>): Promise<Dict> {
  try {
    return await p;
  } catch {
    return {};
  }
}

// Step 64E.3B -- read-only Demo Evidence dashboard. Surfaces the Step 64D staging
// demo evidence (project + work item, agent executions, workflows, QA/code, audit
// events, safety posture) that the summary/pilot pages did not expose. GET-only.
export function DemoEvidence() {
  const [data, setData] = useState<Dict | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const projectsResp = await safe(getDeliveryProjects());
      const projects = ((projectsResp.projects as Dict[]) || []).slice();
      const first = projects[0] || {};
      const pid = (first.project_id as string) || "";
      const wiResp = pid ? await safe(getDeliveryWorkItems(pid)) : {};
      const workItems = (wiResp.work_items as Dict[]) || [];
      const firstWi = workItems[0] || {};
      const wid = (firstWi.id as string) || "";
      const [events, execs, wfs, qa, code, safety] = await Promise.all([
        wid ? safe(getDeliveryWorkItemEvents(wid)) : Promise.resolve({} as Dict),
        safe(getAgentExecutions()),
        safe(getWorkflows()),
        safe(getQaRuns()),
        safe(getCodeWorkspaces()),
        safe(getSafety()),
      ]);
      if (alive) setData({ projects, workItems, events, execs, wfs, qa, code, safety });
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!data) return <LoadingState />;

  const projects = data.projects as Dict[];
  const workItems = data.workItems as Dict[];
  const events = ((data.events as Dict).events as Dict[]) || [];
  const execs = ((data.execs as Dict).executions as Dict[]) || [];
  const wfs = ((data.wfs as Dict).workflows as Dict[]) || [];
  const qa = ((data.qa as Dict).validation_runs as Dict[]) || [];
  const qaCount = (data.qa as Dict).count;
  const code = ((data.code as Dict).workspaces as Dict[]) || [];
  const safety = data.safety as Dict;
  const prodExec = safety.production_executed_true_count;

  return (
    <div className="demo-evidence" data-testid="demo-evidence">
      <h2>Demo Evidence</h2>
      <p className="note">
        Read-only view of the Step 64D staging demonstration (non-production). Live GitHub /
        Slack / LLM integrations are disabled or mocked; no production action. Governed delivery /
        release evidence is pending operator-session authorization, so a delivery package /
        release candidate may not be present.
      </p>

      <section>
        <h3>Demo Project</h3>
        <Table
          rows={projects}
          cols={["project_id", "project_key", "name", "status", "environment_scope", "production_allowed"]}
        />
      </section>

      <section>
        <h3>Demo Work Items</h3>
        <Table
          rows={workItems}
          cols={["work_item_key", "id", "title", "lifecycle_state", "production_effect"]}
        />
      </section>

      <section>
        <h3>Agent Executions</h3>
        <Table
          rows={execs}
          cols={["agent", "status", "task_id", "started_at", "completed_at"]}
        />
      </section>

      <section>
        <h3>Workflows</h3>
        <Table
          rows={wfs}
          cols={["task_id", "stage", "approval_status", "risk_level", "production_executed"]}
        />
      </section>

      <section>
        <h3>QA Runs {qaCount !== undefined ? `(count: ${fmt(qaCount)})` : ""}</h3>
        <Table rows={qa} cols={["task_id", "status", "workflow_id"]} />
      </section>

      <section>
        <h3>Code Workspaces</h3>
        <Table
          rows={code}
          cols={["workspace_id", "task_id", "status", "execution_mode", "created_at"]}
        />
      </section>

      <section>
        <h3>Audit / Evidence (demo work item)</h3>
        <Table
          rows={events}
          cols={["event_type", "from_state", "to_state", "actor", "role"]}
        />
      </section>

      <section>
        <h3>Safety Posture</h3>
        <p className="note">
          production_executed_true_count: <strong>{fmt(prodExec)}</strong>
        </p>
      </section>
    </div>
  );
}
