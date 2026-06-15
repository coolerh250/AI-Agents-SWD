// Stage 50 -- secret / chain-of-thought redaction for the Admin Console v0.

export const SECRET_KEY_FRAGMENTS = [
  "token",
  "secret",
  "password",
  "api_key",
  "apikey",
  "hmac",
  "private_key",
  "webhook",
];

export const FORBIDDEN_KEY_FRAGMENTS = ["chain_of_thought", "raw_prompt", "transcript"];

const REDACTED = "***REDACTED***";

export function isSecretKey(key: string): boolean {
  const k = key.toLowerCase();
  return SECRET_KEY_FRAGMENTS.some((s) => k.includes(s));
}

export function isForbiddenKey(key: string): boolean {
  const k = key.toLowerCase();
  return FORBIDDEN_KEY_FRAGMENTS.some((f) => k.includes(f));
}

// Deep-redact secret-like values and strip chain-of-thought keys entirely.
export function redact<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((v) => redact(v)) as unknown as T;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (isForbiddenKey(k)) continue;
      if (isSecretKey(k)) {
        out[k] = REDACTED;
        continue;
      }
      out[k] = redact(v);
    }
    return out as unknown as T;
  }
  return value;
}
