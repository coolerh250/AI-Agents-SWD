// Step 66B.2 -- Task detail page (/tasks/:taskId). dispatch_enabled is always
// rendered as a static false: GET /tasks/{id} does not return that field (only
// create/submit do), and it is true system-wide in Step 66B.2 regardless -- no
// workflow dispatch path exists anywhere in this stage.
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
      <TestRoleBanner />
      <AsyncView key={refreshKey} load={() => taskApi.get(taskId)}>
        {(task: Task) => (
          <>
            <KeyValueTable data={task as unknown as Record<string, unknown>} />
            <p className="note" data-testid="dispatch-enabled-note">
              dispatch_enabled: <StatusBadge value={false} /> (no workflow dispatch occurs in this
              stage)
            </p>
            {task.production_effect && (
              <div className="warn-banner" data-testid="production-effect-warning">
                <strong>production_effect = true</strong> — this task requires approval and will not
                be dispatched.
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
