// Step 58 -- Admin Console v2 Operational Metrics dashboard.
//
// READ-ONLY operational visibility. There is intentionally NO deploy / ArgoCD sync /
// GitHub PR / external send / production approve / production-ready / connector
// control here. Metrics are visibility only — never a production-readiness or SLA
// signal. Unavailable / stale sources are shown explicitly (not hidden, not faked).
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getMetricsOverview,
  getMetricsDelivery,
  getMetricsWorkItems,
  getMetricsDispatch,
  getMetricsAgents,
  getMetricsWorkflows,
  getMetricsRuntime,
  getMetricsGitops,
  getMetricsSecurity,
  getMetricsApproval,
  getMetricsAudit,
  getMetricsSafety,
  getMetricsFreshness,
} from "../api/operations";

type Dict = Record<string, unknown>;

function Section({ title, load }: { title: string; load: () => Promise<Dict> }): JSX.Element {
  return (
    <section>
      <h3>{title}</h3>
      <AsyncView load={load}>
        {(d) => {
          const data = d as Dict;
          const available = data.available !== false;
          return (
            <>
              {!available ? (
                <p className="note">unavailable / stale — {String(data.reason ?? "no data")}</p>
              ) : null}
              <KeyValueTable data={data} />
            </>
          );
        }}
      </AsyncView>
    </section>
  );
}

export function OperationalMetrics(): JSX.Element {
  return (
    <div className="operational-metrics" data-testid="operational-metrics">
      <h2>Operational Metrics (Admin Console v2, Step 58)</h2>
      <p className="note">
        Read-only operational metrics. Visibility only — NOT production readiness, NOT an SLA/SLO
        guarantee, NOT multi-tenant. Delivery completed is not production approved; security
        baseline PASS is not all-risks-remediated. This dashboard has NO deploy / ArgoCD sync /
        GitHub PR / external send / production approve / production-ready / connector control.
        Unavailable or stale sources are shown explicitly. Claude Code does not decide production
        readiness.
      </p>
      <Section title="Overview" load={getMetricsOverview} />
      <Section title="Delivery" load={getMetricsDelivery} />
      <Section title="Work items" load={getMetricsWorkItems} />
      <Section title="Dispatch" load={getMetricsDispatch} />
      <Section title="Agent execution" load={getMetricsAgents} />
      <Section title="Workflows" load={getMetricsWorkflows} />
      <Section title="Runtime smoke (non-production)" load={getMetricsRuntime} />
      <Section title="ArgoCD manual sync (non-production)" load={getMetricsGitops} />
      <Section title="Security readiness" load={getMetricsSecurity} />
      <Section title="Approval" load={getMetricsApproval} />
      <Section title="Audit" load={getMetricsAudit} />
      <Section title="Safety posture" load={getMetricsSafety} />
      <Section title="Freshness / stale data" load={getMetricsFreshness} />
    </div>
  );
}
