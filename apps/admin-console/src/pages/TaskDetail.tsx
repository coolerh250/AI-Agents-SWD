// Step 66B.2 -- Task detail page (/tasks/:taskId).
// Step 66B.3 -- GET /tasks/{id} now also returns dispatch_enabled (hardening: the
// value is data-driven from the API, not hardcoded); a concise safety panel
// summarizes environment/production_effect/requires_approval/dispatch_enabled/
// external_actions_enabled/production_executed for at-a-glance review.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { StatusBadge } from "../components/StatusBadge";
import { TestRoleBanner } from "../tasks/TestRoleBanner";
import { taskApi, TaskApiError } from "../tasks/taskClient";
import type { Task } from "../tasks/taskTypes";

export function TaskDetail() {
  const { taskId = "" } = useParams();
  const [refreshKey, setRefreshKey] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(): Promise<void> {
    setSubmitError(null);
    setSubmitting(true);
    try {
      await taskApi.submit(taskId);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setSubmitError(
        e instanceof TaskApiError ? e.message : e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h2>Task Detail</h2>
      <p className="note">
        <Link to="/tasks">&larr; Back to task list</Link>
      </p>
      <p className="note">
        No workflow dispatch occurs in Step 66B.2. This is task assignment UI foundation only.
      </p>
      <p className="note">
        <Link to={`/tasks/${taskId}/workroom`} data-testid="open-workroom-link">
          Open Workroom
        </Link>
      </p>
      <TestRoleBanner />
      <AsyncView key={refreshKey} load={() => taskApi.get(taskId)}>
        {(task: Task) => (
          <>
            <KeyValueTable data={task as unknown as Record<string, unknown>} />
            <div className="safety-panel" data-testid="safety-panel">
              <h3>Safety</h3>
              <ul>
                <li>
                  Environment: <strong>{task.environment}</strong>
                </li>
                <li>
                  production_effect: <StatusBadge value={task.production_effect} />
                </li>
                <li>
                  requires_approval: <StatusBadge value={task.requires_approval} />
                </li>
                <li>
                  dispatch_enabled: <StatusBadge value={task.dispatch_enabled ?? false} />
                </li>
                <li>
                  external_actions_enabled: <StatusBadge value={false} />
                </li>
                <li>
                  production_executed: <StatusBadge value={false} />
                </li>
              </ul>
            </div>
            <p className="note" data-testid="dispatch-enabled-note">
              dispatch_enabled: <StatusBadge value={task.dispatch_enabled ?? false} /> (no workflow
              dispatch occurs in this stage)
            </p>
            {task.production_effect && (
              <div className="warn-banner" data-testid="production-effect-warning">
                <strong>production_effect = true</strong> — this task requires approval, is
                blocked / approval-required, and will not be dispatched. No production action occurs.
              </div>
            )}
            {task.status === "draft" && (
              <button disabled={submitting} onClick={() => void handleSubmit()} data-testid="submit-draft">
                Submit Draft
              </button>
            )}
            {submitError && (
              <div className="error" data-testid="submit-error">
                {submitError}
              </div>
            )}
          </>
        )}
      </AsyncView>
    </>
  );
}
