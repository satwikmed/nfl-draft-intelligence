"""Export database data to JSON for the web dashboard."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.db import query_df

OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)

# 1. Big Board — top prospects by year
board = query_df("""
    SELECT p.player_id, p.name, p.school, p.position, p.position_group,
           p.draft_year, p.height_inches, p.weight_lbs,
           d.round as draft_round, d.pick as draft_pick, d.team,
           pred.pro_readiness_score,
           pred.predicted_career_length,
           c.forty_yard, c.bench_press, c.vertical_jump,
           c.broad_jump, c.three_cone, c.shuttle
    FROM prospects p
    INNER JOIN draft_picks d ON p.player_id = d.player_id
    LEFT JOIN predictions pred ON p.player_id = pred.player_id
    LEFT JOIN combine_results c ON p.player_id = c.player_id
    WHERE p.position_group IS NOT NULL
      AND pred.pro_readiness_score IS NOT NULL
    ORDER BY pred.pro_readiness_score DESC
""")
board_json = board.head(5000).replace({float('nan'): None}).to_dict(orient="records")
(OUT / "board.json").write_text(json.dumps(board_json))
print(f"Board: {len(board_json)} records")

# 2. Percentile features for radar charts
feats = query_df("""
    SELECT f.player_id, f.feature_name, f.feature_value
    FROM features f
    WHERE f.feature_name LIKE '%_percentile'
       OR f.feature_name IN ('athletic_composite','speed_score','bmi',
                             'draft_capital_value','college_seasons')
""")
feat_dict = {}
for _, r in feats.iterrows():
    pid = r["player_id"]
    if pid not in feat_dict:
        feat_dict[pid] = {}
    val = r["feature_value"]
    if val is not None and str(val) != 'nan':
        feat_dict[pid][r["feature_name"]] = round(float(val), 2)
    else:
        feat_dict[pid][r["feature_name"]] = None

(OUT / "features.json").write_text(json.dumps(feat_dict))
print(f"Features: {len(feat_dict)} players")

# 3. NFL performance for career charts
nfl = query_df("""
    SELECT n.player_id, n.season, n.games_played,
           n.passing_yards, n.passing_tds, n.interceptions_thrown,
           n.rushing_yards, n.rushing_tds,
           n.receiving_yards, n.receiving_tds, n.receptions,
           n.tackles, n.sacks, n.interceptions
    FROM nfl_performance n
    INNER JOIN draft_picks d ON n.player_id = d.player_id
    ORDER BY n.player_id, n.season
""")
nfl_dict = {}
for pid, group in nfl.groupby("player_id"):
    nfl_dict[pid] = group.replace({float('nan'): None}).to_dict(orient="records")
(OUT / "nfl_performance.json").write_text(json.dumps(nfl_dict))
print(f"NFL Performance: {len(nfl_dict)} players")

# 4. Comp data
comps = query_df("""
    SELECT pred.player_id,
           pred.comp_1_id, pred.comp_1_similarity,
           pred.comp_2_id, pred.comp_2_similarity,
           pred.comp_3_id, pred.comp_3_similarity,
           p1.name as comp_1_name, p2.name as comp_2_name, p3.name as comp_3_name
    FROM predictions pred
    LEFT JOIN prospects p1 ON pred.comp_1_id = p1.player_id
    LEFT JOIN prospects p2 ON pred.comp_2_id = p2.player_id
    LEFT JOIN prospects p3 ON pred.comp_3_id = p3.player_id
    WHERE pred.comp_1_id IS NOT NULL
""")
comp_dict = {}
for _, r in comps.iterrows():
    c_list = []
    for i in range(1, 4):
        cid = r[f"comp_{i}_id"]
        if cid:
            c_list.append({"id": cid, "name": r[f"comp_{i}_name"], "sim": float(r[f"comp_{i}_similarity"])})
    comp_dict[r["player_id"]] = {"comps": c_list}
(OUT / "comps.json").write_text(json.dumps(comp_dict))
print(f"Comps: {len(comp_dict)} players")

# 5. Stats summary
stats = query_df("""
    SELECT p.position_group,
           COUNT(*) as total,
           AVG(pred.pro_readiness_score) as avg_score,
           MIN(pred.pro_readiness_score) as min_score,
           MAX(pred.pro_readiness_score) as max_score,
           AVG(pred.predicted_career_length) as avg_career
    FROM predictions pred
    INNER JOIN prospects p ON pred.player_id = p.player_id
    WHERE p.position_group IS NOT NULL AND pred.pro_readiness_score IS NOT NULL
    GROUP BY p.position_group
""")
stats_json = stats.replace({float('nan'): None}).to_dict(orient="records")
(OUT / "stats.json").write_text(json.dumps(stats_json))
print(f"Stats: {len(stats)} position groups")
print("Done!")
# 6. Model Validation Metrics
import pickle
MODELS_DIR = PROJECT_ROOT = Path(__file__).resolve().parent.parent / "data" / "models"
model_metrics = {}
if MODELS_DIR.exists():
    for model_path in MODELS_DIR.glob("pro_readiness_*.pkl"):
        pos = model_path.stem.split("_")[-1]
        try:
            with open(model_path, "rb") as f:
                model_data = pickle.load(f)
                if "metrics" in model_data:
                    m = model_data["metrics"]
                    import math
                    # Clean NaNs to None for valid JSON
                    m = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in m.items()}
                    model_metrics[pos] = m
        except Exception as e:
            pass

(OUT / "model_metrics.json").write_text(json.dumps(model_metrics))
print(f"Model Metrics: {len(model_metrics)} positions")

print("Done!")
