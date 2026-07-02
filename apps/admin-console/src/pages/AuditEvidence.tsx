import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import {
  getDeliveryProjects,
  getDeliveryWorkItems,
  getDeliveryWorkItemEvents,
} from "../api/operations";

type Dict = Record<string, unknown>;

// Resolves the demo work item (first delivery project -> first work item) and
// loads its audit event trail. All GET-only reads.
async function loadAudit(): Promise<{ workItem: Dict; events: Dict[] }> {
  const projects = ((await getDeliveryProjects()) as Dict).projects as Dict[] | undefined;
  const pid = (projects && projects[0] ? (projects[0].project_id as string) : "") || "";
  const workItems = pid
    ? (((await getDeliveryWorkItems(pid)) as Dict).work_items as Dict[] | undefined) || []
    : [];
  const workItem = workItems[0] || {};
  const wid = (workItem.id as string) || "";
  const events = wid
    ? (((await getDeliveryWorkItemEvents(wid)) as Dict).events as Dict[] | undefined) || []
    : [];
  return { workItem, events };
}

// Step 64E.4B -- formal Audit / Evidence product page. Surfaces the demo work
// item's audit event trail (work_item_created and any subsequent transitions)
// from /operations/delivery/work-items/{id}/events. GET-only.
export function AuditEvidence() {
  return (
    <AsyncView load={loadAudit}>
      {({ workItem, events }) => (
        <>
          <h2>Audit / Evidence</h2>
          <p className="note">
            Read-only audit trail for the staging demonstration work item (non-production).
            production_executed=false; no production action.
          </p>
          <p className="note">
            Work item: {fmtCell(workItem.work_item_key)} — {fmtCell(workItem.title)} · events:{" "}
            {events.length}
          </p>
          <EvidenceTable
            rows={events}
            cols={["event_type", "from_state", "to_state", "actor", "role", "created_at"]}
            empty="No audit events yet"
          />
        </>
      )}
    </AsyncView>
  );
}

function fmtCell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}
