// Step 66B.2 -- TEST-ONLY role simulation for the Task Assignment UI.
//
// This is NOT a production identity model. The backend (Step 66B.1) has no real
// identity/auth model yet -- it is a documented, fail-closed test-only header
// gate (TASK_API_TEST_AUTH_ENABLED + X-Task-Actor/X-Task-Role). This module
// stores only a plain actor label + role name in localStorage so those two
// headers can be set from the browser -- nothing secret and nothing that
// authenticates on its own. See docs/test/step66b2-task-assignment-ui-safety-record.md.

export const TASK_ROLES = [
  "requester",
  "pm_engineering_lead",
  "reviewer_approver",
  "platform_admin",
  "agent_operator",
  "security_compliance_reviewer",
] as const;

export type TaskRole = (typeof TASK_ROLES)[number];

// Step 66B.3 -- readable labels for the RBAC role dropdown (safety UX hardening).
export const TASK_ROLE_LABELS: Record<TaskRole, string> = {
  requester: "Requester",
  pm_engineering_lead: "PM / Engineering Lead",
  reviewer_approver: "Reviewer / Approver",
  platform_admin: "Platform Admin",
  agent_operator: "Agent Operator",
  security_compliance_reviewer: "Security / Compliance Reviewer",
};

const STORAGE_KEY = "aiagents.taskApi.testRole.v1";
const DEFAULT_ACTOR = "test-operator";
// Least-privilege default (documented): Requester can only create/view/submit
// its own tasks. Switch roles via the banner to exercise other capabilities.
const DEFAULT_ROLE: TaskRole = "requester";

export interface TestIdentity {
  actor: string;
  role: TaskRole;
}

function isTaskRole(value: unknown): value is TaskRole {
  return typeof value === "string" && (TASK_ROLES as readonly string[]).includes(value);
}

function safeParse(raw: string | null): TestIdentity | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<TestIdentity>;
    if (typeof parsed.actor === "string" && parsed.actor.trim() && isTaskRole(parsed.role)) {
      return { actor: parsed.actor, role: parsed.role };
    }
  } catch {
    // malformed storage -- fall through to the default identity
  }
  return null;
}

export function defaultTestIdentity(): TestIdentity {
  return { actor: DEFAULT_ACTOR, role: DEFAULT_ROLE };
}

export function getTestRole(): TestIdentity {
  try {
    return safeParse(window.localStorage.getItem(STORAGE_KEY)) || defaultTestIdentity();
  } catch {
    return defaultTestIdentity();
  }
}

export function setTestRole(identity: TestIdentity): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
  } catch {
    // ignore storage failures (private browsing, quota, etc.) -- the in-memory
    // value set by the caller still applies to the next request
  }
}
