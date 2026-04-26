"""
Model C: Career Survival Analysis.

Uses the lifelines library to model career duration:
- Kaplan-Meier survival curves by position group and draft round
- Cox proportional hazards model for individual predictions

Handles right-censoring for active players.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.config import MODELED_POSITION_GROUPS, END_YEAR
from src.utils.db import query_df, get_db_connection
from src.features.builder import get_feature_matrix

logger = logging.getLogger(__name__)


def build_survival_data() -> pd.DataFrame:
    """
    Build the survival dataset from NFL performance data.

    Each player gets:
    - duration: number of NFL seasons played
    - event: 1 if career ended (no data after last season), 0 if right-censored

    Returns:
        DataFrame with player_id, position_group, draft_round, duration, event.
    """
    logger.info("Building survival dataset...")

    sql = """
        SELECT p.player_id, p.position_group, p.draft_year,
               d.round as draft_round,
               n.season, n.games_played
        FROM prospects p
        INNER JOIN draft_picks d ON p.player_id = d.player_id
        INNER JOIN nfl_performance n ON p.player_id = n.player_id
        WHERE p.position_group IS NOT NULL
          AND p.draft_year IS NOT NULL
    """
    df = query_df(sql)

    if df.empty:
        logger.warning("No data for survival analysis.")
        return pd.DataFrame()

    # Compute career duration per player
    survival_records = []
    most_recent_season = END_YEAR

    for pid, player_df in df.groupby("player_id"):
        pos = player_df["position_group"].iloc[0]
        draft_year = player_df["draft_year"].iloc[0]
        draft_round = player_df["draft_round"].iloc[0]

        seasons_played = player_df["season"].nunique()
        last_season = player_df["season"].max()

        # Right-censoring: if last active season is recent, player might still be active
        if last_season >= most_recent_season - 1:
            event = 0  # right-censored (likely still active)
        else:
            event = 1  # career ended

        survival_records.append({
            "player_id": pid,
            "position_group": pos,
            "draft_year": draft_year,
            "draft_round": int(draft_round) if pd.notna(draft_round) else None,
            "duration": seasons_played,
            "last_season": last_season,
            "event": event,
        })

    result = pd.DataFrame(survival_records)
    logger.info("Survival dataset: %d players, %.1f%% censored",
                len(result), 100 * (1 - result["event"].mean()))

    return result


def fit_kaplan_meier() -> dict:
    """
    Fit Kaplan-Meier survival curves by position group and draft round.

    Returns dict of fitted KM estimators.
    """
    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        logger.error("lifelines not installed. Install with: pip install lifelines")
        return {}

    survival_df = build_survival_data()
    if survival_df.empty:
        return {}

    km_results: dict = {}

    # Overall KM curve
    kmf = KaplanMeierFitter()
    kmf.fit(survival_df["duration"], event_observed=survival_df["event"],
            label="All Players")
    km_results["overall"] = {
        "median_survival": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else None,
        "survival_function": kmf.survival_function_.to_dict(),
    }
    logger.info("Overall median career: %.1f seasons", kmf.median_survival_time_)

    # By position group
    for pos in MODELED_POSITION_GROUPS:
        pos_df = survival_df[survival_df["position_group"] == pos]
        if len(pos_df) < 10:
            continue

        kmf = KaplanMeierFitter()
        kmf.fit(pos_df["duration"], event_observed=pos_df["event"],
                label=pos)
        km_results[f"pos_{pos}"] = {
            "median_survival": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else None,
            "n_players": len(pos_df),
        }
        logger.info("  %s: median %.1f seasons (n=%d)",
                    pos, kmf.median_survival_time_, len(pos_df))

    # By draft round
    for rnd in range(1, 8):
        rnd_df = survival_df[survival_df["draft_round"] == rnd]
        if len(rnd_df) < 10:
            continue

        kmf = KaplanMeierFitter()
        kmf.fit(rnd_df["duration"], event_observed=rnd_df["event"],
                label=f"Round {rnd}")
        km_results[f"round_{rnd}"] = {
            "median_survival": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else None,
            "n_players": len(rnd_df),
        }

    return km_results


def fit_cox_model() -> dict:
    """
    Fit Cox proportional hazards model using pre-draft features.

    Returns dict with model summary and predictions.
    """
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        logger.error("lifelines not installed")
        return {}

    logger.info("Fitting Cox PH model...")

    survival_df = build_survival_data()
    if survival_df.empty:
        return {}

    # Get features for survived players
    all_features = []
    for pos in MODELED_POSITION_GROUPS:
        fm = get_feature_matrix(pos, min_features=3)
        if not fm.empty:
            fm["position_group_code"] = MODELED_POSITION_GROUPS.index(pos)
            all_features.append(fm)

    if not all_features:
        logger.warning("No features for Cox model.")
        return {}

    feature_df = pd.concat(all_features)

    # Join with survival data
    common = survival_df.set_index("player_id").index.intersection(feature_df.index)
    if len(common) < 50:
        logger.warning("Too few players with both features and survival data: %d", len(common))
        return {}

    surv = survival_df.set_index("player_id").loc[common]
    feats = feature_df.loc[common].fillna(0)

    # Select a subset of meaningful features for Cox model
    cox_features = []
    for col in feats.columns:
        if feats[col].std() > 0:
            cox_features.append(col)

    # Limit to top 15 features by variance
    var_series = feats[cox_features].var().sort_values(ascending=False)
    cox_features = var_series.head(15).index.tolist()

    # Build Cox dataframe
    cox_df = feats[cox_features].copy()
    cox_df["duration"] = surv["duration"].values
    cox_df["event"] = surv["event"].values

    # Remove any constant columns
    cox_df = cox_df.loc[:, cox_df.nunique() > 1]

    # Fit model
    cph = CoxPHFitter(penalizer=0.1)
    try:
        cph.fit(cox_df, duration_col="duration", event_col="event")
    except Exception as e:
        logger.error("Cox model fit failed: %s", e)
        return {}

    logger.info("Cox model fitted. Concordance: %.3f", cph.concordance_index_)

    # Generate predictions for all players
    predictions = []
    pred_df = cox_df.drop(columns=["duration", "event"])

    median_survival = cph.predict_median(pred_df)
    for pid, median in zip(common, median_survival):
        if np.isfinite(median):
            predictions.append({
                "player_id": pid,
                "predicted_career_length": round(float(median), 1),
            })

    # Store predictions
    if predictions:
        with get_db_connection() as conn:
            for pred in predictions:
                conn.execute(
                    """UPDATE predictions
                       SET predicted_career_length = ?
                       WHERE player_id = ?""",
                    (pred["predicted_career_length"], pred["player_id"])
                )
        logger.info("Stored %d career length predictions", len(predictions))

    return {
        "concordance": float(cph.concordance_index_),
        "n_players": len(common),
        "n_predictions": len(predictions),
    }


def get_survival_curve(player_id: str) -> dict | None:
    """
    Get individual survival curve for a player.

    Returns dict with survival probabilities at each time point.
    """
    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        return None

    # Get player info
    player = query_df(
        """SELECT p.position_group, d.round as draft_round
           FROM prospects p
           INNER JOIN draft_picks d ON p.player_id = d.player_id
           WHERE p.player_id = ?""",
        (player_id,)
    )

    if player.empty:
        return None

    pos = player.iloc[0]["position_group"]
    draft_round = player.iloc[0]["draft_round"]

    # Build survival curve from similar players
    survival_df = build_survival_data()
    similar = survival_df[
        (survival_df["position_group"] == pos)
    ]

    if len(similar) < 10:
        return None

    kmf = KaplanMeierFitter()
    kmf.fit(similar["duration"], event_observed=similar["event"])

    # Build curve data
    curve = {}
    for t in range(1, 21):
        prob = float(kmf.predict(t))
        curve[t] = round(prob, 4)

    return {
        "player_id": player_id,
        "position_group": pos,
        "draft_round": int(draft_round) if pd.notna(draft_round) else None,
        "survival_curve": curve,
        "median_career": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else None,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # Fit models
    km_results = fit_kaplan_meier()
    cox_results = fit_cox_model()

    if cox_results:
        logger.info("Cox concordance: %.3f", cox_results.get("concordance", 0))
