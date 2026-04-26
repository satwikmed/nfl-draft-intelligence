import { Prospect, Features, CompsData, NFLPerf, ModelMetrics } from "./types";

export async function fetchStats() {
  const [board, features, nfl, comps, metrics] = await Promise.all([
    fetch("/data/board.json").then((r) => r.json()) as Promise<Prospect[]>,
    fetch("/data/features.json").then((r) => r.json()) as Promise<Features>,
    fetch("/data/nfl_performance.json").then((r) => r.json()) as Promise<Record<string, NFLPerf[]>>,
    fetch("/data/comps.json").then((r) => r.json()) as Promise<CompsData>,
    fetch("/data/model_metrics.json").then((r) => r.json()).catch(() => ({})) as Promise<ModelMetrics>,
  ]);

  return { board, features, nfl, comps, metrics };
}
