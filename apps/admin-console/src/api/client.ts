// Stage 50 -- read-only typed fetch wrapper for the Admin Console v0.
//
// SAFETY: this client exposes GET only. There is intentionally NO post / put /
// patch / delete method anywhere, so the console can never trigger a write /
// operator action. The read-only guard test asserts this invariant.

export const API_BASE: string = (
  (import.meta as { env?: Record<string, string> }).env?.VITE_OPERATIONS_API_BASE_URL || ""
).replace(/\/$/, "");

export class ApiError extends Error {
  code: number;
  constructor(message: string, code: number) {
    super(message);
    this.code = code;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (res.status === 404) throw new ApiError("not_available", 404);
  if (!res.ok) throw new ApiError("http_" + res.status, res.status);
  return (await res.json()) as T;
}

// The only HTTP verb this client supports is GET.
export const SUPPORTED_METHODS = ["GET"] as const;
