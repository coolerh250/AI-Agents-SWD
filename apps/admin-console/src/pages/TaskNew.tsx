// Step 66B.2 -- Create task page (/tasks/new). Calls taskApi.create(); never
// dispatches a workflow -- the backend always returns dispatch_enabled=false,
// and production_effect=true is only ever recorded as a blocked / approval-
// required task, never executed.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TestRoleBanner } from "../tasks/TestRoleBanner";
import { taskApi, TaskApiError } from "../tasks/taskClient";
import {
  FIRST_CLASS_TASK_TYPES,
  TASK_ENVIRONMENTS,
  TASK_PRIORITIES,
  TASK_TYPE_OPTIONS,
} from "../tasks/taskTypes";
import type { TaskCreate, TaskEnvironment, TaskPriority, TaskType } from "../tasks/taskTypes";

export function TaskNew() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("software_delivery");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [environment, setEnvironment] = useState<TaskEnvironment>("test");
  const [productionEffect, setProductionEffect] = useState(false);
  const [owner, setOwner] = useState("");
  const [projectId, setProjectId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const isFirstClass = FIRST_CLASS_TASK_TYPES.has(taskType);

  function buildPayload(initialStatus: "draft" | "submitted"): TaskCreate {
    return {
      title: title.trim(),
      description: description.trim() || undefined,
      task_type: taskType,
      priority,
      environment,
      production_effect: productionEffect,
      owner: owner.trim() || undefined,
      project_id: projectId.trim() || undefined,
      initial_status: initialStatus,
    };
  }

  async function handleSubmit(initialStatus: "draft" | "submitted"): Promise<void> {
    setFieldError(null);
    setError(null);
    if (!title.trim()) {
      setFieldError("Title is required.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await taskApi.create(buildPayload(initialStatus));
      navigate(`/tasks/${created.id}`);
    } catch (e) {
      setError(
        e instanceof TaskApiError ? e.message : e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h2>Create Task</h2>
      <p className="note">
        <Link to="/tasks">&larr; Back to task list</Link>
      </p>
      <TestRoleBanner />
      <div className="task-form">
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Task type
          <select value={taskType} onChange={(e) => setTaskType(e.target.value as TaskType)}>
            {TASK_TYPE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <p className="note">
          {isFirstClass
            ? "software_delivery / documentation / platform_improvement are first-class MVP task types."
            : "This task type is not yet first-class in the MVP. It is accepted into intake / " +
              "planning / documentation flow first (intake_planning_only=true), not the full " +
              "delivery pipeline."}
        </p>
        <label>
          Priority
          <select value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)}>
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
            value={environment}
            onChange={(e) => setEnvironment(e.target.value as TaskEnvironment)}
          >
            {TASK_ENVIRONMENTS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>
        <label>
          Owner (optional)
          <input
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            placeholder="defaults to your actor"
          />
        </label>
        <label>
          Project ID (optional)
          <input value={projectId} onChange={(e) => setProjectId(e.target.value)} />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={productionEffect}
            onChange={(e) => setProductionEffect(e.target.checked)}
          />
          production_effect
        </label>
        {productionEffect && (
          <div className="warn-banner" data-testid="production-effect-warning">
            <strong>Warning: production_effect = true</strong>
            <ul>
              <li>This task will NOT execute or dispatch a workflow.</li>
              <li>It will require approval.</li>
              <li>It will be recorded as blocked / waiting approval, never run.</li>
              <li>No production action is allowed from this UI.</li>
            </ul>
          </div>
        )}
        {fieldError && (
          <div className="error" data-testid="field-error">
            {fieldError}
          </div>
        )}
        {error && (
          <div className="error" data-testid="submit-error">
            {error}
          </div>
        )}
        <div className="form-actions">
          <button disabled={submitting} onClick={() => void handleSubmit("draft")}>
            Create Draft
          </button>
          <button disabled={submitting} onClick={() => void handleSubmit("submitted")}>
            Create and Submit
          </button>
        </div>
      </div>
    </>
  );
}
