export interface Prospect {
  player_id: string;
  name: string;
  school: string;
  position_group: string;
  pro_readiness_score: number;
  draft_year?: number;
  draft_round?: number;
  draft_pick?: number;
  team?: string;
  predicted_career_length?: number;
  height_inches?: number;
  weight_lbs?: number;
  forty_yard?: number;
  bench_press?: number;
  vertical_jump?: number;
  broad_jump?: number;
  three_cone?: number;
  shuttle?: number;
}

export interface Features {
  [key: string]: {
    [feature: string]: number;
  };
}

export interface Comp {
  comp_id: string;
  name: string;
  sim: number;
}

export interface CompsData {
  [key: string]: {
    comps: Comp[];
  };
}

export interface NFLPerf {
  player_id: string;
  season: number;
  passing_yards?: number;
  rushing_yards?: number;
  receiving_yards?: number;
}

export interface ModelMetrics {
  [pos: string]: {
    auc: number;
    f1: number;
    accuracy: number;
    n_train: number;
  };
}

export interface WidgetConfig {
  id: string;
  type: "SCATTER" | "BAR" | "KPI";
  positionGroup: string;
  xMetricName: string;
  yMetricName: string; // Only used for Scatter
}
