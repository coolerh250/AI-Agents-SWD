import { Link } from "react-router-dom";
import { getAgentExecutions, getOverview, getSafety } from "../api/operations";
import type { Overview } from "../api/types";
import { AsyncView } from "../components/AsyncView";
import { CalmSafetyPosture } from "../components/CalmSafetyPosture";
import { DataCard } from "../components/DataCard";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { taskApi } from "../tasks/taskClient";
import type { Task, TaskListResponse } from "../tasks/taskTypes";
import { display } from "../utils/format";

type Dict = Record<string, unknown>;
type LoadState<T> = { kind: "ready"; data: T } | { kind: "error" };

type OverviewData = {
  overview: Overview;
  decisions: LoadState<TaskListResponse>;
  blocked: LoadState<TaskListResponse>;
  currentWork: LoadState<TaskListResponse>;
  activity: LoadState<Record<string, unknown>>;
  safety: LoadState<Record<string, unknown>>;
};

const TASK_STATUS_LABELS: Partial<Record<Task["status"], string>> = {
  intake_review: "Intake review",
  clarification_needed: "Clarification needed",
  clarification_expired: "Clarification expired",
  approved_for_execution: "Approved for execution",
  running: "In development",
  waiting_approval: "Waiting for approval",
  delivery_ready: "Ready for delivery",
  changes_requested: "Changes requested",
  qa_rerun_requested: "QA rerun requested",
};

async function capture<T>(promise: Promise<T>): Promise<LoadState<T>> {
  try {
    return { kind: "ready", data: await promise };
  } catch {
    return { kind: "error" };
  }
}

const loadOverview = async (): Promise<OverviewData> => {
  const [overview, decisions, blocked, currentWork, activity, safety] = await Promise.all([
    getOverview(),
    capture(taskApi.list({ status: "clarification_needed" })),
    capture(taskApi.list({ status: "blocked" })),
    capture(taskApi.list()),
    capture(getAgentExecutions()),
    capture(getSafety()),
  ]);

  return { overview, decisions, blocked, currentWork, activity, safety };
};

function timestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function recentTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => timestamp(b.updated_at) - timestamp(a.updated_at)).slice(0, 5);
}

export function agentExecutionStatusLabel(status: unknown): string {
  if (status === "completed") return "Completed";
  if (status === "failed") return "Needs review";
  return "Not reported";
}

function taskStatusLabel(status: Task["status"]): string {
  const mapped = TASK_STATUS_LABELS[status];
  if (mapped) return mapped;
  const readable = status.replace(/_/g, " ");
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

function relativeTime(value: unknown): string {
  if (typeof value !== "string") return "Time not reported";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "Time not reported";
  const minutes = Math.max(0, Math.floor((Date.now() - parsed) / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function taskCount(state: LoadState<TaskListResponse>): number | null {
  if (state.kind === "error") return null;
  if (typeof state.data.count === "number") return state.data.count;
  return Array.isArray(state.data.tasks) ? state.data.tasks.length : null;
}

function AttentionItem({
  title,
  state,
  activeCopy,
  clearCopy,
  to,
}: {
  title: string;
  state: LoadState<TaskListResponse>;
  activeCopy: string;
  clearCopy: string;
  to: string;
}) {
  const count = taskCount(state);
  const content = (
    <>
      <span className="overview-item-title">{title}</span>
      {count === null ? (
        <span className="overview-item-copy">This information isn't available for your role right now.</span>
      ) : count > 0 ? (
        <span className="overview-attention-count">
          <strong>{count}</strong> {activeCopy}
        </span>
      ) : (
        <span className="overview-item-copy">{clearCopy}</span>
      )}
    </>
  );

  if (count !== null && count > 0) {
    return (
      <Link className="overview-attention-item is-active" to={to}>
        {content}
      </Link>
    );
  }
  return <div className="overview-attention-item is-clear">{content}</div>;
}

function PlaceholderItem({ title, children }: { title: string; children: string }) {
  return (
    <article className="overview-placeholder">
      <h4>{title}</h4>
      <p>{children}</p>
    </article>
  );
}

function Metrics({ data }: { data: Overview }) {
  return (
    <details className="overview-metrics">
      <summary>Platform &amp; delivery metrics</summary>
      <div className="grid overview-metrics-grid">
        <DataCard label="Active projects">{display(data.active_projects_count)}</DataCard>
        <DataCard label="Delivery packages">{display(data.delivery_packages_count)}</DataCard>
        <DataCard label="Ready for review packages">
          {display(data.ready_for_review_packages_count)}
        </DataCard>
        <DataCard label="Latest pilot">
          <StatusBadge value={data.latest_mini_delivery_pilot_status} />
        </DataCard>
        <DataCard label="Latest package">
          <StatusBadge value={data.latest_delivery_package_status} />
        </DataCard>
        <DataCard label="Acceptance gate">
          <StatusBadge value={data.latest_acceptance_gate_decision} />
        </DataCard>
        <DataCard label="Human acceptance">
          <StatusBadge value={data.latest_human_acceptance_status} />
        </DataCard>
        <DataCard label="Safety">
          <StatusBadge value={data.safety_result} />
        </DataCard>
        <DataCard label="Production executed">
          <StatusBadge value={data.production_executed_true_count} />
        </DataCard>
        <DataCard label="Full regression">
          <StatusBadge value={data.latest_full_regression_status} />
        </DataCard>
        <DataCard label="Ready for admin console">
          <StatusBadge value={data.delivery_package_ready_for_admin_console} />
        </DataCard>
        <DataCard label="Backup gaps">{display(data.backup_readiness_gaps)}</DataCard>
      </div>
    </details>
  );
}

export function ExecutiveOverview() {
  return (
    <AsyncView load={loadOverview}>
      {({ overview, decisions, blocked, currentWork, activity, safety }) => {
        const tasks =
          currentWork.kind === "ready" && Array.isArray(currentWork.data.tasks)
            ? recentTasks(currentWork.data.tasks)
            : [];
        const executions =
          activity.kind === "ready" && Array.isArray(activity.data.executions)
            ? (activity.data.executions as Dict[]).slice(0, 5)
            : [];

        return (
          <div className="overview-page">
            <header className="overview-page-header">
              <h2>Overview</h2>
              <p>See what your AI team needs from you and where work stands.</p>
            </header>

            <section className="overview-section" data-testid="needs-attention">
              <h3>Needs your attention</h3>
              <div className="overview-attention-grid">
                <AttentionItem
                  title="Decisions waiting"
                  state={decisions}
                  activeCopy="agents waiting on your answer"
                  clearCopy="You're all caught up."
                  to="/tasks?status=clarification_needed"
                />
                <AttentionItem
                  title="Blocked tasks"
                  state={blocked}
                  activeCopy="waiting on an input"
                  clearCopy="Nothing blocked."
                  to="/tasks?status=blocked"
                />
                <PlaceholderItem title="Deliveries to review">
                  Not yet available. Requires Step 66D. No workflow action available from this screen.
                </PlaceholderItem>
                <PlaceholderItem title="Approvals queue">
                  Not yet available. Requires Step 66D. No workflow action available from this screen.
                </PlaceholderItem>
              </div>
            </section>

            <section className="overview-section" data-testid="ai-team-activity">
              <h3>AI team activity</h3>
              {activity.kind === "error" ? (
                <EmptyState message="This information isn't available for your role right now." />
              ) : executions.length === 0 ? (
                <EmptyState message="No recent agent runs." />
              ) : (
                <ul className="overview-rows">
                  {executions.map((execution, index) => {
                    const occurredAt =
                      execution.completed_at || execution.started_at || execution.created_at;
                    return (
                      <li key={String(execution.id || `${execution.agent || "agent"}-${index}`)}>
                        <span className="overview-row-main">
                          <strong>{String(execution.agent || "Agent not reported")}</strong>
                          <span>{agentExecutionStatusLabel(execution.status)}</span>
                        </span>
                        <time
                          dateTime={typeof occurredAt === "string" ? occurredAt : undefined}
                          title={typeof occurredAt === "string" ? occurredAt : undefined}
                        >
                          {relativeTime(occurredAt)}
                        </time>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="overview-section" data-testid="current-work">
              <h3>Current work</h3>
              {currentWork.kind === "error" ? (
                <EmptyState message="This information isn't available for your role right now." />
              ) : tasks.length === 0 ? (
                <EmptyState message="No tasks yet. Assign your first piece of work to the AI team." />
              ) : (
                <ul className="overview-rows">
                  {tasks.map((task) => (
                    <li key={task.id}>
                      <Link className="overview-row-main" to={`/tasks/${encodeURIComponent(task.id)}`}>
                        <strong>{task.title}</strong>
                        <span>{taskStatusLabel(task.status)}</span>
                      </Link>
                      <time dateTime={task.updated_at || undefined} title={task.updated_at || undefined}>
                        {relativeTime(task.updated_at)}
                      </time>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="overview-section overview-posture" data-testid="system-posture">
              <div className="overview-section-heading">
                <h3>System posture</h3>
                <Link to="/safety">View Safety</Link>
              </div>
              {safety.kind === "ready" ? (
                <CalmSafetyPosture data={safety.data} compact showDetails={false} />
              ) : (
                <EmptyState message="Safety status isn't available right now. View Safety for full evidence." />
              )}
            </section>

            <Metrics data={overview} />

            <section className="overview-section" data-testid="future-capabilities">
              <h3>Future capabilities</h3>
              <div className="overview-placeholder-grid">
                <PlaceholderItem title="Delivery Review">
                  Not yet available. Requires Step 66D. No workflow action available from this screen.
                </PlaceholderItem>
                <PlaceholderItem title="Reminder / Expiry">
                  Not yet available. Requires Step 66C.4. No workflow action available from this screen.
                </PlaceholderItem>
                <PlaceholderItem title="Notifications / Action Center">
                  Future. No workflow action available from this screen.
                </PlaceholderItem>
                <PlaceholderItem title="Pipeline view">
                  Future (read-only only). No workflow action available from this screen.
                </PlaceholderItem>
              </div>
            </section>
          </div>
        );
      }}
    </AsyncView>
  );
}
