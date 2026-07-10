// Step 66B.2 -- visible banner for the test-only role simulation (testRole.ts).
// Selecting an actor/role here persists a non-secret {actor, role} label that
// every taskApi call reads at request time -- see taskClient.ts. This is NOT
// production auth and has no production-mode equivalent.
import { useState } from "react";
import { TASK_ROLES, TASK_ROLE_LABELS, getTestRole, setTestRole } from "./testRole";
import type { TaskRole } from "./testRole";

export function TestRoleBanner(): JSX.Element {
  const initial = getTestRole();
  const [actor, setActor] = useState(initial.actor);
  const [role, setRole] = useState<TaskRole>(initial.role);

  function apply(nextActor: string, nextRole: TaskRole): void {
    setTestRole({ actor: nextActor, role: nextRole });
    setActor(nextActor);
    setRole(nextRole);
  }

  return (
    <div className="test-role-banner" data-testid="test-role-banner">
      <strong>Test role simulation active</strong> — not production auth. Applies to the next
      request; reload to re-apply to an already-loaded page.{" "}
      <label>
        Actor
        <input value={actor} onChange={(e) => apply(e.target.value, role)} />
      </label>{" "}
      <label>
        Role
        <select value={role} onChange={(e) => apply(actor, e.target.value as TaskRole)}>
          {TASK_ROLES.map((r) => (
            <option key={r} value={r}>
              {TASK_ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </label>{" "}
      <span data-testid="current-identity" className="current-identity">
        Current: <strong>{actor}</strong> as <strong>{TASK_ROLE_LABELS[role]}</strong>
      </span>
    </div>
  );
}
