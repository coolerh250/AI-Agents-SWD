import { AsyncView } from "../components/AsyncView";
import { DataCard } from "../components/DataCard";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { StatusBadge } from "../components/StatusBadge";
import { getLatestDeliveryState } from "../api/operations";

export function DeliveryPackage() {
  return (
    <AsyncView load={getLatestDeliveryState}>
      {(d) =>
        d.latest_delivery_package ? (
          <>
            <h2>Delivery Package / Acceptance Gate</h2>
            <div className="grid">
              <DataCard label="Package status">
                <StatusBadge value={(d.latest_delivery_package as Record<string, unknown>).status} />
              </DataCard>
              <DataCard label="Gate status">
                <StatusBadge value={(d.acceptance_gate as Record<string, unknown> | null)?.status} />
              </DataCard>
              <DataCard label="Gate decision">
                <StatusBadge
                  value={(d.acceptance_gate as Record<string, unknown> | null)?.decision}
                />
              </DataCard>
              <DataCard label="Human acceptance">
                <StatusBadge value={d.human_acceptance_status} />
              </DataCard>
              <DataCard label="Readiness">
                <StatusBadge
                  value={(d.readiness_snapshot as Record<string, unknown> | null)?.readiness_status}
                />
              </DataCard>
            </div>
            <p className="note">
              Accept / reject / request-changes are a future Admin Console v1 feature and are
              disabled here.
            </p>
            <h3>Acceptance gate</h3>
            <KeyValueTable data={d.acceptance_gate} />
            <h3>Readiness snapshot</h3>
            <KeyValueTable data={d.readiness_snapshot} />
          </>
        ) : (
          <>
            <h2>Delivery Package / Acceptance Gate</h2>
            <EmptyState message="No delivery package yet" />
          </>
        )
      }
    </AsyncView>
  );
}
