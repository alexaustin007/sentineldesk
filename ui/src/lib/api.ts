import { pickMock } from "../mocks";
import type { TriageErrorBody, TriageRequest, TriageResponse } from "../types/triage";

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
export const TIMEOUT_MS = 30_000;

export class TriageError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

/** `?mock=error` / `?mock=timeout` force the failure states in mock mode. */
function mockOverride(): string | null {
  return new URLSearchParams(window.location.search).get("mock");
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const id = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(id);
      reject(signal.reason);
    });
  });
}

async function mockTriage(req: TriageRequest, signal: AbortSignal): Promise<TriageResponse> {
  const mode = mockOverride();
  if (mode === "timeout") await wait(TIMEOUT_MS * 2, signal);
  await wait(1000 + Math.random() * 1000, signal);
  if (mode === "error") throw new TriageError("UPSTREAM_UNAVAILABLE", "The generator service did not respond (mock error).");
  return structuredClone(pickMock(req));
}

async function liveTriage(req: TriageRequest, signal: AbortSignal): Promise<TriageResponse> {
  let res: Response;
  try {
    res = await fetch("/api/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (e) {
    if (signal.aborted) throw signal.reason;
    throw new TriageError("NETWORK", "Could not reach the triage API.");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as TriageErrorBody | null;
    throw new TriageError(body?.error?.code ?? `HTTP_${res.status}`, body?.error?.message ?? res.statusText ?? "Request failed");
  }
  return (await res.json()) as TriageResponse;
}

export class TimeoutError extends Error {}

/** Runs one triage with a 30 s timeout. `outer` lets the caller cancel. */
export async function triage(req: TriageRequest, outer?: AbortSignal): Promise<TriageResponse> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(new TimeoutError("timeout")), TIMEOUT_MS);
  outer?.addEventListener("abort", () => ctrl.abort(outer.reason));
  try {
    return await (USE_MOCK ? mockTriage : liveTriage)(req, ctrl.signal);
  } finally {
    clearTimeout(timer);
  }
}
