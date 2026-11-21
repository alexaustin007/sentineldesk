import example from "../../../contracts/metrics.example.json";
import type { Metrics } from "../types/metrics";
import { parseMetrics } from "./validateMetrics";

export type MetricsSource = "live" | "sample";
export interface LoadedMetrics {
  metrics: Metrics;
  source: MetricsSource;
}

/**
 * Fetches /metrics.json (eval output copied into ui/public/ or served by the backend).
 * If it isn't served (404, or the dev server's HTML fallback), falls back to the bundled
 * example and marks it as sample data. A file that IS served but is malformed throws.
 */
export async function loadMetrics(signal?: AbortSignal): Promise<LoadedMetrics> {
  let res: Response | null = null;
  try {
    res = await fetch("/metrics.json", { cache: "no-store", signal });
  } catch (e) {
    if (signal?.aborted) throw e;
  }
  const isJson = res?.ok && (res.headers.get("content-type") ?? "").includes("json");
  if (!res || !isJson) return { metrics: parseMetrics(example), source: "sample" };
  const raw: unknown = await res.json().catch(() => "not json");
  const metrics = parseMetrics(raw);
  return { metrics, source: metrics.sample ? "sample" : "live" };
}
