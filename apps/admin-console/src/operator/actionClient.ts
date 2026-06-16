// Stage 52 -- Admin Console v1 operator-action client.
//
// SAFETY: this client exposes ONLY explicit, named, typed action methods. There
// is intentionally no generic verb+URL helper and no arbitrary endpoint /
// command input. Every mutating call:
//   * includes the session cookie via credentials: "same-origin"
//   * sends the CSRF token in the X-CSRF-Token header
//   * sends an Idempotency-Key
// The session token lives only in an HttpOnly cookie -- the browser persists it
// automatically and this client never touches client-side web storage for it.

import { API_BASE } from "../api/client";

const OPS = API_BASE + "/operations";
const ADMIN = OPS + "/admin-console";

let csrfToken = "";

function setCsrf(token: string): void {
  csrfToken = token || "";
}

function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  return (await res.json()) as T;
}

// Single private mutating helper. Not exported; callers use named methods only.
async function post<T>(url: string, body: Record<string, unknown>, idemPrefix: string): Promise<T> {
  const verb = "POST";
  const res = await fetch(url, {
    method: verb,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRF-Token": csrfToken,
      "Idempotency-Key": newIdempotencyKey(idemPrefix),
    },
    body: JSON.stringify(body),
  });
  return (await res.json()) as T;
}

export interface SessionInfo {
  authenticated: boolean;
  identity_key?: string;
  role?: string;
  roles?: string[];
  auth_mode?: string;
  reason?: string;
}

export const operatorActions = {
  session(): Promise<SessionInfo> {
    return getJson<SessionInfo>(`${ADMIN}/auth/session`);
  },
  async refreshCsrf(): Promise<string> {
    const r = await getJson<{ csrf_token?: string }>(`${ADMIN}/auth/csrf`);
    setCsrf(r.csrf_token || "");
    return csrfToken;
  },
  async testLogin(role: string): Promise<SessionInfo & { csrf_token?: string }> {
    const r = await post<SessionInfo & { csrf_token?: string }>(
      `${ADMIN}/auth/test-login`,
      { role },
      "login",
    );
    if (r.csrf_token) setCsrf(r.csrf_token);
    return r;
  },
  logout(): Promise<{ status: string }> {
    return post<{ status: string }>(`${ADMIN}/auth/logout`, {}, "logout");
  },
  catalog(): Promise<unknown> {
    return getJson(`${ADMIN}/operator-actions/catalog`);
  },
  history(limit = 50): Promise<unknown> {
    return getJson(`${ADMIN}/operator-actions?limit=${limit}`);
  },
  addNote(packageId: string, reason: string, noteType = "general"): Promise<unknown> {
    return post(`${OPS}/delivery-packages/${packageId}/operator-review/notes`,
      { reason, note_type: noteType }, "note");
  },
  requestChanges(packageId: string, reason: string): Promise<unknown> {
    return post(`${OPS}/delivery-packages/${packageId}/operator-review/request-changes`,
      { reason }, "reqchg");
  },
  accept(packageId: string, reason: string): Promise<unknown> {
    return post(`${OPS}/delivery-packages/${packageId}/operator-review/accept`,
      { reason }, "accept");
  },
  reject(packageId: string, reason: string): Promise<unknown> {
    return post(`${OPS}/delivery-packages/${packageId}/operator-review/reject`,
      { reason }, "reject");
  },
  issueConfirmation(actionId: string): Promise<{ confirmation_nonce?: string }> {
    return post(`${ADMIN}/operator-actions/${actionId}/confirmation`, {}, "conf");
  },
  confirmAndExecute(actionId: string, nonce: string): Promise<unknown> {
    return post(`${ADMIN}/operator-actions/${actionId}/execute`,
      { confirmation_nonce: nonce }, "exec");
  },
  rerunVerification(scriptKey: string, reason: string, highRiskAck = false): Promise<unknown> {
    return post(`${ADMIN}/verifications/rerun`,
      { script_key: scriptKey, reason, high_risk_ack: highRiskAck }, "rerun");
  },
  runVerification(actionId: string, nonce: string): Promise<unknown> {
    return post(`${ADMIN}/verifications/${actionId}/run`, { confirmation_nonce: nonce }, "run");
  },
  listReruns(): Promise<unknown> {
    return getJson(`${ADMIN}/verifications/reruns`);
  },
};

export { setCsrf };
