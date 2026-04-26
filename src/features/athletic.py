"""
Athletic profile features from NFL Combine data.

Computes position-adjusted percentiles, composite scores, and
speed scores for each prospect's athletic measurables.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from src.utils.config import MODELED_POSITION_GROUPS
from src.utils.db import query_df

logger = logging.getLogger(__name__)

# Combine metrics and whether higher is better
COMBINE_METRICS: dict[str, bool] = {
    "forty_yard": False,      # lower is better
    "bench_press": True,      # higher is better
    "vertical_jump": True,    # higher is better
    "broad_jump": True,       # higher is better
    "three_cone": False,      # lower is better
    "shuttle": False,         # lower is better
}

# Weights for athletic composite score (position-agnostic defaults)
COMPOSITE_WEIGHTS: dict[str, float] = {
    "forty_yard": 0.25,
    "bench_press": 0.10,
    "vertical_jump": 0.15,
    "broad_jump": 0.15,
    "three_cone": 0.20,
    "shuttle": 0.15,
}


def compute_athletic_features(player_ids: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Compute athletic profile features for all prospects with combine data.

    Features computed:
    - Positional percentile for each combine metric
    - Athletic composite z-score (position-adjusted)
    - Speed score: (weight * 200) / (forty^4)
    - Height-adjusted speed score (for WR/TE)
    - Relative Athletic Score (RAS) approximation

    Args:
        player_ids: Optional list of player IDs to compute for.
                   If None, computes for all prospects with combine data.

    Returns:
        DataFrame with columns: player_id, feature_name, feature_value
    """
    logger.info("Computing athletic features...")

    # Load combine data joined with prospect info
    sql = """
        SELECT p.player_id, p.name, p.position_group,
               p.height_inches, p.weight_lbs, p.draft_year,
               c.forty_yard, c.bench_press, c.vertical_jump,
               c.broad_jump, c.three_cone, c.shuttle
        FROM prospects p
        INNER JOIN combine_results c ON p.player_id = c.player_id
        WHERE p.position_group IS NOT NULL
    """
    if player_ids:
        placeholders = ",".join(["?"] * len(player_ids))
        sql += f" AND p.player_id IN ({placeholders})"
        df = query_df(sql, tuple(player_ids))
    else:
        df = query_df(sql)

    if df.empty:
        logger.warning("No combine data found for athletic features.")
        return pd.DataFrame(columns=["player_id", "feature_name", "feature_value"])

    logger.info("Computing athletic features for %d prospects", len(df))

    all_features: list[dict] = []

    # Compute features per position group so percentiles are position-relative
    for pos_group in MODELED_POSITION_GROUPS:
        pos_df = df[df["position_group"] == pos_group].copy()
        if pos_df.empty:
            continue

        logger.debug("  %s: %d prospects", pos_group, len(pos_df))

        # 1. Positional percentiles for each metric
        for metric, higher_is_better in COMBINE_METRICS.items():
            valid = pos_df[metric].dropna()
            if len(valid) < 5:
                continue

            for idx, row in pos_df.iterrows():
                val = row[metric]
                if pd.isna(val):
                    continue

                if higher_is_better:
                    pctile = scipy_stats.percentileofscore(valid, val, kind="rank")
                else:
                    # For metrics where lower is better, invert percentile
                    pctile = 100.0 - scipy_stats.percentileofscore(valid, val, kind="rank")

                all_features.append({
                    "player_id": row["player_id"],
                    "feature_name": f"{metric}_percentile",
                    "feature_value": round(pctile, 2),
                })

        # 2. Athletic composite z-score
        _compute_composite(pos_df, all_features)

        # 3. Speed score: (weight * 200) / (forty^4)
        _compute_speed_score(pos_df, pos_group, all_features)

        # 4. BMI and size metrics
        _compute_size_metrics(pos_df, all_features)

    result = pd.DataFrame(all_features)
    logger.info("Computed %d athletic features", len(result))
    return result


def _compute_composite(pos_df: pd.DataFrame, features: list[dict]) -> None:
    """Compute position-adjusted athletic composite z-score."""
    for _, row in pos_df.iterrows():
        z_scores = []
        weights = []

        for metric, higher_is_better in COMBINE_METRICS.items():
            val = row[metric]
            if pd.isna(val):
                continue

            valid = pos_df[metric].dropna()
            if len(valid) < 5:
                continue

            mean = valid.mean()
            std = valid.std()
            if std == 0:
                continue

            z = (val - mean) / std
            if not higher_is_better:
                z = -z  # flip so higher z = better

            z_scores.append(z)
            weights.append(COMPOSITE_WEIGHTS.get(metric, 0.15))

        if z_scores:
            # Weighted average z-score
            composite = np.average(z_scores, weights=weights)
            features.append({
                "player_id": row["player_id"],
                "feature_name": "athletic_composite",
                "feature_value": round(float(composite), 4),
            })

            # Number of combine drills completed
            features.append({
                "player_id": row["player_id"],
                "feature_name": "combine_drills_completed",
                "feature_value": len(z_scores),
            })


def _compute_speed_score(pos_df: pd.DataFrame, pos_group: str,
                         features: list[dict]) -> None:
    """
    Compute speed score: (weight * 200) / (forty^4).

    Rewards heavy players who run fast. More meaningful for WR/TE/RB.
    """
    for _, row in pos_df.iterrows():
        weight = row["weight_lbs"]
        forty = row["forty_yard"]

        if pd.isna(weight) or pd.isna(forty) or forty <= 0:
            continue

        speed_score = (weight * 200.0) / (forty ** 4)

        features.append({
            "player_id": row["player_id"],
            "feature_name": "speed_score",
            "feature_value": round(speed_score, 2),
        })

        # Height-adjusted speed score for WR/TE
        if pos_group in ("WR", "TE") and not pd.isna(row["height_inches"]):
            ht = row["height_inches"]
            if ht > 0:
                ht_adj_speed = speed_score * (ht / 72.0)  # normalize to 6'0"
                features.append({
                    "player_id": row["player_id"],
                    "feature_name": "height_adj_speed_score",
                    "feature_value": round(ht_adj_speed, 2),
                })


def _compute_size_metrics(pos_df: pd.DataFrame, features: list[dict]) -> None:
    """Compute BMI and other size-related features."""
    for _, row in pos_df.iterrows():
        ht = row["height_inches"]
        wt = row["weight_lbs"]

        if pd.isna(ht) or pd.isna(wt) or ht <= 0:
            continue

        # BMI (using inches and pounds)
        bmi = (wt * 703.0) / (ht ** 2)
        features.append({
            "player_id": row["player_id"],
            "feature_name": "bmi",
            "feature_value": round(bmi, 2),
        })

        # Height in inches (raw)
        features.append({
            "player_id": row["player_id"],
            "feature_name": "height_inches",
            "feature_value": round(ht, 1),
        })

        # Weight
        features.append({
            "player_id": row["player_id"],
            "feature_name": "weight_lbs",
            "feature_value": round(wt, 1),
        })
