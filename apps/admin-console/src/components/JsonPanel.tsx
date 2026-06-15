import { redact } from "../utils/safety";

// Always redacts before rendering raw JSON, so secrets / chain-of-thought
// never reach the DOM.
export function JsonPanel({ data }: { data: unknown }) {
  return <pre>{JSON.stringify(redact(data), null, 2)}</pre>;
}
