// Stage 50 -- Admin Console v0 API response types (read-only).

export interface Overview {
  generated_at: string;
  active_projects_count: number;
  projects_count: number;
  delivery_packages_count: number;
  ready_for_review_packages_count: number;
  latest_mini_delivery_pilot_status: string | null;
  latest_delivery_package_status: string | null;
  latest_acceptance_gate_decision: string | null;
  latest_acceptance_gate_status: string | null;
  latest_human_acceptance_status: string | null;
  safety_result: string | null;
  production_executed_true_count: number | null;
  delivery_package_ready_for_admin_console: boolean;
  latest_full_regression_status: string | null;
  backup_readiness_gaps: string[];
  backup_production_ready: boolean;
  incidents_summary: Record<string, number>;
  llm_summary: Record<string, number>;
  admin_console: Record<string, boolean>;
}

export interface ProjectRollup {
  project_id: string;
  title: string | null;
  status: string | null;
  project_type: string | null;
  risk_level: string | null;
  autonomy_level: string | null;
  latest_pilot_status: string | null;
  latest_delivery_package_status: string | null;
  human_acceptance_status: string | null;
  readiness_status: string | null;
}

export interface ProjectsResponse {
  count: number;
  projects: ProjectRollup[];
}

export interface ProjectDetail {
  project: Record<string, unknown>;
  rollup: ProjectRollup;
  latest_pilot: Record<string, unknown> | null;
  latest_delivery_package: Record<string, unknown> | null;
}

export interface LatestDeliveryState {
  latest_pilot: Record<string, unknown> | null;
  latest_delivery_package: Record<string, unknown> | null;
  acceptance_gate: Record<string, unknown> | null;
  readiness_snapshot: Record<string, unknown> | null;
  human_acceptance_status: string | null;
  production_executed: boolean;
}

export type SafetySummary = Record<string, unknown>;
export type RegressionSummary = Record<string, unknown>;
