type SafetyTone = "safe" | "attention" | "unavailable";

type EvidenceField = {
  field: string;
  label: string;
};

const BOOLEAN_OFF = "Off";
const BOOLEAN_ON = "On";

export const SAFETY_EVIDENCE_FIELDS: EvidenceField[] = [
  { field: "production_executed_true_count", label: "Production action count" },
  { field: "workflow_production_executed_true_count", label: "Workflow production count" },
  { field: "dispatch_enabled", label: "Workflow dispatch" },
  { field: "resume_dispatch_enabled", label: "Workflow resume" },
  { field: "task_api_workflow_dispatch_enabled", label: "Task API dispatch" },
  { field: "task_workroom_resume_dispatch_enabled", label: "Workroom resume" },
  { field: "github_external_write_enabled", label: "GitHub write integration" },
  { field: "discord_external_send_enabled", label: "Discord send integration" },
  { field: "llm_external_call_enabled", label: "LLM external call" },
  { field: "production_delegation_allowed", label: "Production delegation" },
  { field: "approval_required", label: "Approval required" },
  { field: "requires_approval", label: "Requires approval" },
  { field: "result", label: "Endpoint result" },
  { field: "last_checked", label: "Last checked" },
];

const AUTOMATION_FIELDS = [
  "dispatch_enabled",
  "resume_dispatch_enabled",
  "task_api_workflow_dispatch_enabled",
  "task_workroom_resume_dispatch_enabled",
] as const;

const EXTERNAL_FIELDS = [
  "github_external_write_enabled",
  "discord_external_send_enabled",
  "llm_external_call_enabled",
] as const;

const PRODUCTION_COUNT_FIELDS = [
  "production_executed_true_count",
  "workflow_production_executed_true_count",
] as const;

function hasField(data: Record<string, unknown>, field: string): boolean {
  return Object.prototype.hasOwnProperty.call(data, field);
}

function boolState(data: Record<string, unknown>, field: string): boolean | null {
  if (!hasField(data, field)) return null;
  const value = data[field];
  return typeof value === "boolean" ? value : null;
}

function numberState(data: Record<string, unknown>, field: string): number | null {
  if (!hasField(data, field)) return null;
  const value = data[field];
  return typeof value === "number" ? value : null;
}

function allBooleans(data: Record<string, unknown>, fields: readonly string[], value: boolean) {
  return fields.every((field) => boolState(data, field) === value);
}

function anyBooleans(data: Record<string, unknown>, fields: readonly string[], value: boolean) {
  return fields.some((field) => boolState(data, field) === value);
}

function allNumbers(data: Record<string, unknown>, fields: readonly string[], value: number) {
  return fields.every((field) => numberState(data, field) === value);
}

function anyPositiveNumber(data: Record<string, unknown>, fields: readonly string[]) {
  return fields.some((field) => {
    const value = numberState(data, field);
    return value !== null && value > 0;
  });
}

export function formatSafetyValue(data: Record<string, unknown>, field: string): string {
  if (!hasField(data, field)) return "not reported";
  const value = data[field];
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "not reported";
  return String(value);
}

function factFromBooleanGroup(
  label: string,
  data: Record<string, unknown>,
  fields: readonly string[],
  offCopy: string,
  onCopy: string,
): string {
  if (allBooleans(data, fields, false)) return `${label}: ${offCopy}`;
  if (anyBooleans(data, fields, true)) return `${label}: ${onCopy}`;
  return `${label}: not reported`;
}

function productionFact(data: Record<string, unknown>): string {
  if (allNumbers(data, PRODUCTION_COUNT_FIELDS, 0)) return "No production actions have run";
  if (anyPositiveNumber(data, PRODUCTION_COUNT_FIELDS)) return "Production actions are reported";
  return "Production action evidence: not reported";
}

function approvalFact(data: Record<string, unknown>): string {
  const required = boolState(data, "approval_required");
  const requiresApproval = boolState(data, "requires_approval");
  if (required === true || requiresApproval === true) {
    return "Human approval is required before anything runs";
  }
  if (required === false && requiresApproval === false) return "No approval needed for this context";
  if (required === false || requiresApproval === false) return "Approval requirement: partially reported";
  return "Approval requirement: not reported";
}

export function getCalmSafetyPosture(data: Record<string, unknown>) {
  const automationOff = allBooleans(data, AUTOMATION_FIELDS, false);
  const externalOff = allBooleans(data, EXTERNAL_FIELDS, false);
  const noProduction = allNumbers(data, PRODUCTION_COUNT_FIELDS, 0);
  const approvalRequired =
    boolState(data, "approval_required") === true || boolState(data, "requires_approval") === true;
  const hasEnabledRisk =
    anyBooleans(data, AUTOMATION_FIELDS, true) ||
    anyBooleans(data, EXTERNAL_FIELDS, true) ||
    anyPositiveNumber(data, PRODUCTION_COUNT_FIELDS) ||
    boolState(data, "production_delegation_allowed") === true;
  const endpointResult = hasField(data, "result") ? String(data.result) : null;
  const resultWarns = endpointResult !== null && endpointResult !== "safe";

  let tone: SafetyTone = "unavailable";
  let title = "Safety status unavailable - check system evidence.";

  if (hasEnabledRisk || approvalRequired || resultWarns) {
    tone = "attention";
    title = approvalRequired
      ? "Attention needed - items are awaiting approval."
      : "Attention needed - review safety evidence.";
  } else if (automationOff && externalOff && noProduction) {
    tone = "safe";
    title = "Safe - no automated or production actions will run.";
  }

  return {
    tone,
    label: tone === "safe" ? "Safe" : tone === "attention" ? "Attention" : "Unavailable",
    title,
    facts: [
      productionFact(data),
      factFromBooleanGroup(
        "Automated workflow dispatch",
        data,
        AUTOMATION_FIELDS,
        BOOLEAN_OFF,
        BOOLEAN_ON,
      ),
      factFromBooleanGroup("External integrations", data, EXTERNAL_FIELDS, BOOLEAN_OFF, BOOLEAN_ON),
      factFromBooleanGroup(
        "Production delegation",
        data,
        ["production_delegation_allowed"],
        "Disabled",
        "Enabled",
      ),
      approvalFact(data),
    ],
  };
}

export function CalmSafetyPosture({
  data,
  compact = false,
}: {
  data: Record<string, unknown>;
  compact?: boolean;
}) {
  const posture = getCalmSafetyPosture(data);

  return (
    <div className={`calm-safety calm-safety-${posture.tone}`} data-testid="calm-safety-posture">
      <div className="calm-safety-summary">
        <span className={`badge safety-posture-badge safety-posture-${posture.tone}`}>
          {posture.label}
        </span>
        <span className="calm-safety-title">{posture.title}</span>
      </div>
      {!compact && (
        <ul className="calm-safety-facts" aria-label="Safety facts">
          {posture.facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
      <details className="calm-safety-details">
        <summary>Evidence / details</summary>
        <dl className="calm-safety-evidence">
          {SAFETY_EVIDENCE_FIELDS.map(({ field, label }) => (
            <div key={field} className="calm-safety-evidence-row">
              <dt>
                {label}
                <span className="calm-safety-field"> {field}</span>
              </dt>
              <dd>{formatSafetyValue(data, field)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
