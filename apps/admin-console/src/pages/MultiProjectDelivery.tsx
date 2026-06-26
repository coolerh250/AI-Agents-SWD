// Step 57 -- Admin Console multi-project delivery & work-item dispatch view.
//
// Read views + project/work-item-domain mutations only (create project, create work
// item, dispatch). Every mutation requires a reason and goes through the operator
// session + CSRF + server-side audit. There is intentionally NO production deploy,
// GitHub PR, ArgoCD sync, external send, production approve, or production-ready
// control here. A production_effect work item cannot be dispatched (server routes it
// to waiting_approval).
import { useEffect, useState } from "react";
import { SessionBanner } from "../operator/SessionBanner";
import { operatorActions } from "../operator/actionClient";
import {
  getDeliveryProjects,
  getDeliveryWorkItems,
  getProjectDeliveryState,
  getDeliveryWorkItemEvents,
} from "../api/operations";

type Dict = Record<string, unknown>;

export function MultiProjectDelivery(): JSX.Element {
  const [projects, setProjects] = useState<Dict[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [workItems, setWorkItems] = useState<Dict[]>([]);
  const [deliveryState, setDeliveryState] = useState<string>("");
  const [events, setEvents] = useState<Dict[]>([]);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");

  async function loadProjects(): Promise<void> {
    const r = (await getDeliveryProjects()) as { projects?: Dict[] };
    setProjects(r.projects || []);
  }
  async function loadItems(pid: string): Promise<void> {
    setSelected(pid);
    const r = (await getDeliveryWorkItems(pid)) as { work_items?: Dict[] };
    setWorkItems(r.work_items || []);
    const ds = (await getProjectDeliveryState(pid)) as Dict;
    setDeliveryState(String(ds.delivery_state ?? ""));
  }
  useEffect(() => {
    void loadProjects();
  }, []);

  async function onCreateProject(): Promise<void> {
    if (!name || !reason) {
      setMsg("name and reason required");
      return;
    }
    const r = (await operatorActions.createProject(name, reason)) as Dict;
    setMsg(`project: ${String(r.status)}`);
    setName("");
    await loadProjects();
  }
  async function onCreateWorkItem(): Promise<void> {
    if (!selected || !title || !reason) {
      setMsg("project, title and reason required");
      return;
    }
    const r = (await operatorActions.createWorkItem(selected, title, reason)) as Dict;
    setMsg(`work item: ${String(r.status)}`);
    setTitle("");
    await loadItems(selected);
  }
  async function onDispatch(wid: string): Promise<void> {
    if (!reason) {
      setMsg("reason required to dispatch");
      return;
    }
    const r = (await operatorActions.dispatchWorkItem(wid, reason)) as Dict;
    setMsg(`dispatch: ${String(r.status)}`);
    await loadItems(selected);
    const ev = (await getDeliveryWorkItemEvents(wid)) as { events?: Dict[] };
    setEvents(ev.events || []);
  }

  return (
    <div className="multi-project-delivery" data-testid="multi-project-delivery">
      <h2>Multi-project Delivery &amp; Work-item Dispatch (Step 57)</h2>
      <p className="note">
        Non-production multi-project delivery and work-item dispatch. Mutations require a
        reason and are audited; dispatch never triggers GitHub write, ArgoCD sync, external
        notification send, or any production action. A production_effect work item is routed to
        waiting_approval (never dispatched directly). This view has NO production deploy / GitHub
        PR / ArgoCD sync / external send / production approve / production-ready control. Claude
        Code does not decide production readiness.
      </p>
      <SessionBanner />
      <p className="note">{msg}</p>

      <section>
        <h3>Reason (required for all mutations)</h3>
        <input
          aria-label="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="reason"
        />
      </section>

      <section>
        <h3>Create project</h3>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="project name" />
        <button onClick={() => void onCreateProject()}>Create project</button>
      </section>

      <section>
        <h3>Projects</h3>
        <ul>
          {projects.map((p) => (
            <li key={String(p.project_id)}>
              <button onClick={() => void loadItems(String(p.project_id))}>
                {String(p.project_key)} — {String(p.name)} [{String(p.registry_status)}]
              </button>
            </li>
          ))}
        </ul>
      </section>

      {selected ? (
        <>
          <section>
            <h3>Project delivery state</h3>
            <p>{deliveryState || "not_started"} (production_ready: false)</p>
          </section>
          <section>
            <h3>Create work item</h3>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="title" />
            <button onClick={() => void onCreateWorkItem()}>Create work item</button>
          </section>
          <section>
            <h3>Work items</h3>
            <table>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Title</th>
                  <th>Lifecycle</th>
                  <th>Agent</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {workItems.map((w) => (
                  <tr key={String(w.id)}>
                    <td>{String(w.work_item_key)}</td>
                    <td>{String(w.title)}</td>
                    <td>{String(w.lifecycle_state)}</td>
                    <td>{String(w.assigned_agent ?? "")}</td>
                    <td>
                      <button onClick={() => void onDispatch(String(w.id))}>Dispatch</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section>
            <h3>Work item event timeline</h3>
            <ul>
              {events.map((ev) => (
                <li key={String(ev.id)}>
                  {String(ev.event_type)}: {String(ev.from_state)} → {String(ev.to_state)}
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
    </div>
  );
}
