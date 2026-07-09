// Step 66B.2 -- TypeScript types mirroring shared/sdk/tasks/models.py (Step 66B.1).

export const TASK_TYPES = [
  "software_delivery",
  "documentation",
  "platform_improvement",
  "research",
  "it_operations",
  "security_review",
  "incident_analysis",
  "data_knowledge_analysis",
  "business_process_automation",
  "other",
] as const;

export type TaskType = (typeof TASK_TYPES)[number];

// MVP first-class task types (Step 66A.2 D2/D6). Anything else is accepted but
// routed to intake / planning / documentation first (intake_planning_only=true).
export const FIRST_CLASS_TASK_TYPES: ReadonlySet<string> = new Set([
  "software_delivery",
  "documentation",
  "platform_improvement",
]);

export const TASK_TYPE_OPTIONS: { value: TaskType; label: string }[] = TASK_TYPES.map((t) => ({
  value: t,
  label: t.replace(/_/g, " "),
}));

export type TaskPriority = "low" | "medium" | "high" | "critical";
export const TASK_PRIORITIES: TaskPriority[] = ["low", "medium", "high", "critical"];

export const TASK_STATUSES = [
  "draft",
  "submitted",
  "intake_review",
  "clarification_needed",
  "clarification_expired",
  "approved_for_execution",
  "running",
  "waiting_approval",
  "blocked",
  "failed",
  "delivery_ready",
  "changes_requested",
  "qa_rerun_requested",
  "accepted",
  "rejected",
  "archived",
  "canceled",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export type TaskEnvironment = "test" | "staging";
export const TASK_ENVIRONMENTS: TaskEnvironment[] = ["test", "staging"];

export interface TaskCreate {
  title: string;
  description?: string;
  task_type: TaskType;
  priority?: TaskPriority;
  owner?: string;
  project_id?: string;
  environment?: TaskEnvironment;
  production_effect?: boolean;
  requires_approval?: boolean;
  initial_status?: "draft" | "submitted";
  metadata?: Record<string, unknown>;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  task_type: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  created_by: string;
  owner: string | null;
  project_id: string | null;
  environment: string;
  production_effect: boolean;
  requires_approval: boolean;
  clarification_status: string;
  delivery_status: string;
  intake_planning_only: boolean;
  correlation_id: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface TaskListFilters {
  status?: string;
  task_type?: string;
  owner?: string;
  created_by?: string;
  priority?: string;
  environment?: string;
}

export interface TaskListResponse {
  tasks: Task[];
  count: number;
}
