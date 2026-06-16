// Stage 52 -- disabled future actions (display-only, never executable).
const DISABLED = [
  "Pause workflow",
  "Resume workflow",
  "Update work item status",
  "Create PR",
  "Merge PR",
  "Deploy",
  "Production backup",
  "Production restore",
];

const TOOLTIP = "Not enabled in Admin Console v1 controlled operator actions.";

export function DisabledFutureActions(): JSX.Element {
  return (
    <div className="disabled-actions" data-testid="disabled-actions">
      <h3>Future capabilities (disabled)</h3>
      <ul>
        {DISABLED.map((label) => (
          <li key={label}>
            <button disabled title={TOOLTIP} aria-disabled="true">
              {label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
