import { AsyncView } from "../components/AsyncView";
import { DataCard } from "../components/DataCard";
import { StatusBadge } from "../components/StatusBadge";
import { getOverview } from "../api/operations";
import { display } from "../utils/format";

export function ExecutiveOverview() {
  return (
    <AsyncView load={getOverview}>
      {(d) => (
        <>
          <h2>Executive Overview</h2>
          <div className="grid">
            <DataCard label="Active projects">{display(d.active_projects_count)}</DataCard>
            <DataCard label="Delivery packages">{display(d.delivery_packages_count)}</DataCard>
            <DataCard label="Ready for review">
              {display(d.ready_for_review_packages_count)}
            </DataCard>
            <DataCard label="Latest pilot">
              <StatusBadge value={d.latest_mini_delivery_pilot_status} />
            </DataCard>
            <DataCard label="Latest package">
              <StatusBadge value={d.latest_delivery_package_status} />
            </DataCard>
            <DataCard label="Acceptance gate">
              <StatusBadge value={d.latest_acceptance_gate_decision} />
            </DataCard>
            <DataCard label="Human acceptance">
              <StatusBadge value={d.latest_human_acceptance_status} />
            </DataCard>
            <DataCard label="Safety">
              <StatusBadge value={d.safety_result} />
            </DataCard>
            <DataCard label="Production executed">
              <StatusBadge value={d.production_executed_true_count} />
            </DataCard>
            <DataCard label="Full regression">
              <StatusBadge value={d.latest_full_regression_status} />
            </DataCard>
            <DataCard label="Ready for admin console">
              <StatusBadge value={d.delivery_package_ready_for_admin_console} />
            </DataCard>
            <DataCard label="Backup gaps">{display(d.backup_readiness_gaps)}</DataCard>
          </div>
          <p className="note">Operator actions are disabled in Admin Console v0.</p>
        </>
      )}
    </AsyncView>
  );
}
