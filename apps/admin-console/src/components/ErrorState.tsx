import { ApiError } from "../api/client";

export function ErrorState({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.code === 404) {
    return <div className="empty">Not available in this environment</div>;
  }
  const msg = error instanceof Error ? error.message : "error";
  return <div className="error">Unable to load data ({msg})</div>;
}
