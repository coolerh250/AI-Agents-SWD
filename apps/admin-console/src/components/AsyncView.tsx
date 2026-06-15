import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";

// Runs a read-only loader once and renders loading / error / content states.
export function AsyncView<T>({
  load,
  children,
}: {
  load: () => Promise<T>;
  children: (data: T) => ReactNode;
}) {
  const [state, setState] = useState<{ status: "loading" | "ok" | "error"; data?: T; error?: unknown }>(
    { status: "loading" },
  );
  useEffect(() => {
    let alive = true;
    load()
      .then((data) => alive && setState({ status: "ok", data }))
      .catch((error) => alive && setState({ status: "error", error }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") return <ErrorState error={state.error} />;
  return <>{children(state.data as T)}</>;
}
