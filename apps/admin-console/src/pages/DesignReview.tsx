import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { KeyValueTable } from "../components/KeyValueTable";
import { getLatestDeliveryState } from "../api/operations";

export function DesignReview() {
  return (
    <AsyncView load={getLatestDeliveryState}>
      {(d) =>
        d.latest_pilot ? (
          <>
            <h2>Design Review</h2>
            <p className="note">Latest pilot design-review context (review-only, go/no-go).</p>
            <KeyValueTable data={d.latest_pilot} />
          </>
        ) : (
          <>
            <h2>Design Review</h2>
            <EmptyState message="No design review available yet" />
          </>
        )
      }
    </AsyncView>
  );
}
