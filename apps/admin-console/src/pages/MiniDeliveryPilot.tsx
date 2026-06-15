import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getLatestDeliveryState } from "../api/operations";

export function MiniDeliveryPilot() {
  return (
    <AsyncView load={getLatestDeliveryState}>
      {(d) =>
        d.latest_pilot ? (
          <>
            <h2>Mini Delivery Pilot</h2>
            <KeyValueTable data={d.latest_pilot} />
          </>
        ) : (
          <>
            <h2>Mini Delivery Pilot</h2>
            <EmptyState message="No mini delivery pilot yet" />
          </>
        )
      }
    </AsyncView>
  );
}
