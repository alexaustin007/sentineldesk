import type { TriageResponse } from "../types/triage";

export type RunState =
  | { kind: "idle" }
  | { kind: "loading"; startedAt: number }
  | { kind: "success"; res: TriageResponse; runId: number }
  | { kind: "error"; code: string; message: string; elapsedMs: number }
  | { kind: "timeout"; elapsedMs: number };
