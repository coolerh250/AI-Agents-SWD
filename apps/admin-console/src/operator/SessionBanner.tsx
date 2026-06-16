// Stage 52 -- operator session / identity banner.
import { useEffect, useState } from "react";
import { operatorActions, SessionInfo } from "./actionClient";

const ROLES = ["viewer", "reviewer", "operator", "platform_admin"];

export function SessionBanner(): JSX.Element {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [role, setRole] = useState("operator");

  async function refresh(): Promise<void> {
    const s = await operatorActions.session();
    setSession(s);
    if (s.authenticated) await operatorActions.refreshCsrf();
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function login(): Promise<void> {
    await operatorActions.testLogin(role);
    await refresh();
  }
  async function logout(): Promise<void> {
    await operatorActions.logout();
    await refresh();
  }

  return (
    <div className="session-banner" data-testid="session-banner">
      {session?.authenticated ? (
        <span>
          Signed in: <strong>{session.identity_key}</strong> (role: {session.role}) — auth:{" "}
          {session.auth_mode} <button onClick={() => void logout()}>Logout</button>
        </span>
      ) : (
        <span>
          Not signed in.{" "}
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>{" "}
          <button onClick={() => void login()}>Test login</button>
          {session?.reason ? <em> ({session.reason})</em> : null}
        </span>
      )}
    </div>
  );
}
