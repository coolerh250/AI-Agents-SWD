// Step 66B.2 -- Task list page (/tasks). Reads via taskApi.list(); never
// dispatches a workflow. Filter changes remount <AsyncView> (via key) to
// re-fetch, since AsyncView only loads once per mount.
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { StatusBadge } from "../components/StatusBadge";
import { TestRoleBanner } from "../tasks/TestRoleBanner";
import { taskApi } from "../tasks/taskClient";
import {
  TASK_PRIORITIES,
  TASK_STATUSES,
  TASK_TYPE_OPTIONS,
  TASK_ENVIRONMENTS,
} from "../tasks/taskTypes";
import type { Task, TaskListFilters } from "../tasks/taskTypes";

export function TaskList() {
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<TaskListFilters>(() => {
    const status = searchParams.get("status");
    return status && TASK_STATUSES.some((candidate) => candidate === status) ? { status } : {};
  });
  const filterKey = JSON.stringify(filters);

  function setFilter(key: keyof TaskListFilters, value: string): void {
    setFilters((prev) => ({ ...prev, [key]: value || undefined }));
  }

  return (
    <>
      <h2>Tasks</h2>
      <p className="note">
        Operator task assignment (Step 66B). No workflow dispatch occurs from this page.
      </p>
      <TestRoleBanner />
      <div className="filters">
        <label>
          Status
          <select value={filters.status || ""} onChange={(e) => setFilter("status", e.target.value)}>
            <option value="">(any)</option>
            {TASK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Task type
          <select
            value={filters.task_type || ""}
            onChange={(e) => setFilter("task_type", e.target.value)}
          >
            <option value="">(any)</option>
            {TASK_TYPE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select
            value={filters.priority || ""}
            onChange={(e) => setFilter("priority", e.target.value)}
          >
            <option value="">(any)</option>
            {TASK_PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Environment
          <select
            value={filters.environment || ""}
            onChange={(e) => setFilter("environment", e.target.value)}
          >
            <option value="">(any)</option>
            {TASK_ENVIRONMENTS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>
        <label>
          Owner
          <input value={filters.owner || ""} onChange={(e) => setFilter("owner", e.target.value)} />
        </label>
        <label>
          Created by
          <input
            value={filters.created_by || ""}
            onChange={(e) => setFilter("created_by", e.target.value)}
          />
        </label>
      </div>
      <p>
        <Link to="/tasks/new">+ Create task</Link>
      </p>
      <AsyncView key={filterKey} load={() => taskApi.list(filters)}>
        {(d) => <TaskTable tasks={d.tasks} />}
      </AsyncView>
    </>
  );
}

function TaskTable({ tasks }: { tasks: Task[] }) {
  if (!tasks.length) return <div className="empty">No tasks yet</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Status</th>
          <th>Priority</th>
          <th>Owner / Created by</th>
          <th>Environment</th>
          <th>Production effect</th>
          <th>Requires approval</th>
          <th>Created</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => (
          <tr key={t.id}>
            <td>
              <Link to={`/tasks/${t.id}`}>{t.title}</Link>
            </td>
            <td>{t.task_type}</td>
            <td>
              <StatusBadge value={t.status} />
            </td>
            <td>{t.priority}</td>
            <td>{t.owner || t.created_by}</td>
            <td>{t.environment}</td>
            <td>
              <StatusBadge value={t.production_effect} />
            </td>
            <td>
              <StatusBadge value={t.requires_approval} />
            </td>
            <td>{t.created_at}</td>
            <td>{t.updated_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
