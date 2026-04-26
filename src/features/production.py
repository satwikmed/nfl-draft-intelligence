"""
Production metrics from college stats.

Computes dominator rating, breakout age, career trajectory,
final season stats, and efficiency metrics for each prospect.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.db import query_df

logger = logging.getLogger(__name__)


def compute_production_features(player_ids: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Compute college production features for all prospects with college stats.

    Features:
    - Dominator rating (share of team production)
    - Breakout age / breakout season
    - Final season production (peak stats)
    - Career trajectory (slope of regression)
    - Efficiency metrics (YPC, YPR, completion %, passer rating)
    - Total career production

    Returns:
        DataFrame with columns: player_id, feature_name, feature_value
    """
    logger.info("Computing production features...")

    # Load college stats with prospect info
    # Don't filter by position_group since CFBD records may not have it
    sql = """
        SELECT p.player_id, p.name, p.position_group, p.position, p.draft_year,
               cs.season, cs.games,
               cs.passing_yards, cs.passing_tds, cs.completions, cs.pass_attempts,
               cs.interceptions_thrown,
               cs.rushing_yards, cs.rushing_tds, cs.rush_attempts,
               cs.receiving_yards, cs.receiving_tds, cs.receptions,
               cs.tackles, cs.sacks, cs.interceptions,
               cs.passes_defended, cs.forced_fumbles
        FROM prospects p
        INNER JOIN college_stats cs ON p.player_id = cs.player_id
    """
    if player_ids:
        placeholders = ",".join(["?"] * len(player_ids))
        sql += f" WHERE p.player_id IN ({placeholders})"
        df = query_df(sql, tuple(player_ids))
    else:
        df = query_df(sql)

    if df.empty:
        logger.warning("No college stats found for production features.")
        return pd.DataFrame(columns=["player_id", "feature_name", "feature_value"])

    logger.info("Computing production features from %d season records", len(df))

    all_features: list[dict] = []

    # Process per player
    for pid, player_df in df.groupby("player_id"):
        pos = player_df["position_group"].iloc[0]
        # If position_group is missing, infer from raw position or stats
        if pd.isna(pos) or pos is None:
            raw_pos = player_df["position"].iloc[0]
            pos = _infer_position_group(raw_pos, player_df)
        draft_year = player_df["draft_year"].iloc[0]

        # Sort by season
        player_df = player_df.sort_values("season")

        # Final season stats
        _compute_final_season(str(pid), player_df, pos, all_features)

        # Career totals
        _compute_career_totals(str(pid), player_df, pos, all_features)

        # Career trajectory (production slope)
        _compute_trajectory(str(pid), player_df, pos, all_features)

        # Efficiency metrics
        _compute_efficiency(str(pid), player_df, pos, all_features)

        # Number of college seasons
        all_features.append({
            "player_id": pid,
            "feature_name": "college_seasons",
            "feature_value": len(player_df),
        })

        # Total games
        total_games = player_df["games"].sum()
        if pd.notna(total_games) and total_games > 0:
            all_features.append({
                "player_id": pid,
                "feature_name": "college_total_games",
                "feature_value": int(total_games),
            })

    result = pd.DataFrame(all_features)
    logger.info("Computed %d production features for %d players",
                len(result), df["player_id"].nunique())
    return result


def _compute_final_season(pid: str, player_df: pd.DataFrame, pos: str,
                          features: list[dict]) -> None:
    """Extract final college season stats as features."""
    final = player_df.iloc[-1]

    # Position-relevant final season stats
    stat_map = {
        "QB": [("passing_yards", "final_passing_yards"),
               ("passing_tds", "final_passing_tds"),
               ("interceptions_thrown", "final_ints_thrown"),
               ("rushing_yards", "final_rushing_yards")],
        "RB": [("rushing_yards", "final_rushing_yards"),
               ("rushing_tds", "final_rushing_tds"),
               ("receiving_yards", "final_receiving_yards"),
               ("receptions", "final_receptions")],
        "WR": [("receiving_yards", "final_receiving_yards"),
               ("receiving_tds", "final_receiving_tds"),
               ("receptions", "final_receptions"),
               ("rushing_yards", "final_rushing_yards")],
        "TE": [("receiving_yards", "final_receiving_yards"),
               ("receiving_tds", "final_receiving_tds"),
               ("receptions", "final_receptions")],
        "DL": [("tackles", "final_tackles"), ("sacks", "final_sacks"),
               ("forced_fumbles", "final_forced_fumbles")],
        "LB": [("tackles", "final_tackles"), ("sacks", "final_sacks"),
               ("interceptions", "final_interceptions")],
        "DB": [("tackles", "final_tackles"), ("interceptions", "final_interceptions"),
               ("passes_defended", "final_passes_defended")],
    }

    for src_col, feat_name in stat_map.get(pos, []):
        val = final.get(src_col)
        if pd.notna(val):
            features.append({
                "player_id": pid,
                "feature_name": feat_name,
                "feature_value": float(val),
            })


def _compute_career_totals(pid: str, player_df: pd.DataFrame, pos: str,
                           features: list[dict]) -> None:
    """Compute career total production."""
    totals = {
        "QB": ["passing_yards", "passing_tds", "interceptions_thrown", "rushing_yards"],
        "RB": ["rushing_yards", "rushing_tds", "receiving_yards", "receptions"],
        "WR": ["receiving_yards", "receiving_tds", "receptions"],
        "TE": ["receiving_yards", "receiving_tds", "receptions"],
        "DL": ["tackles", "sacks", "forced_fumbles"],
        "LB": ["tackles", "sacks", "interceptions"],
        "DB": ["tackles", "interceptions", "passes_defended"],
        "OL": [],
    }

    for col in totals.get(pos, []):
        total = player_df[col].sum()
        if pd.notna(total) and total > 0:
            features.append({
                "player_id": pid,
                "feature_name": f"career_{col}",
                "feature_value": float(total),
            })


def _compute_trajectory(pid: str, player_df: pd.DataFrame, pos: str,
                        features: list[dict]) -> None:
    """
    Compute career trajectory as slope of linear regression over seasons.

    Positive slope = improving production. Negative = declining.
    """
    if len(player_df) < 2:
        return

    # Choose the primary production metric by position
    primary_stat = {
        "QB": "passing_yards",
        "RB": "rushing_yards",
        "WR": "receiving_yards",
        "TE": "receiving_yards",
        "DL": "sacks",
        "LB": "tackles",
        "DB": "tackles",
        "OL": None,
    }.get(pos)

    if not primary_stat:
        return

    seasons = player_df["season"].values
    values = player_df[primary_stat].values

    # Remove NaN
    mask = ~pd.isna(values)
    if mask.sum() < 2:
        return

    seasons_clean = seasons[mask].astype(float)
    values_clean = values[mask].astype(float)

    # Simple linear regression
    try:
        slope, intercept = np.polyfit(seasons_clean, values_clean, 1)
        features.append({
            "player_id": pid,
            "feature_name": "production_trajectory_slope",
            "feature_value": round(float(slope), 2),
        })

        # Normalized slope (relative to mean production)
        mean_val = np.mean(values_clean)
        if mean_val > 0:
            norm_slope = slope / mean_val
            features.append({
                "player_id": pid,
                "feature_name": "production_trajectory_norm",
                "feature_value": round(float(norm_slope), 4),
            })
    except (np.linalg.LinAlgError, ValueError):
        pass


def _compute_efficiency(pid: str, player_df: pd.DataFrame, pos: str,
                        features: list[dict]) -> None:
    """Compute position-specific efficiency metrics from career data."""
    # Aggregate career totals for efficiency calculations
    totals = player_df.sum(numeric_only=True)

    if pos == "QB":
        # Completion percentage
        completions = totals.get("completions", 0)
        attempts = totals.get("pass_attempts", 0)
        if pd.notna(attempts) and attempts > 20:
            comp_pct = (completions / attempts) * 100.0
            features.append({
                "player_id": pid,
                "feature_name": "career_completion_pct",
                "feature_value": round(float(comp_pct), 2),
            })

            # Yards per attempt
            pass_yds = totals.get("passing_yards", 0)
            if pd.notna(pass_yds):
                ypa = pass_yds / attempts
                features.append({
                    "player_id": pid,
                    "feature_name": "career_yards_per_attempt",
                    "feature_value": round(float(ypa), 2),
                })

            # TD/INT ratio
            tds = totals.get("passing_tds", 0)
            ints = totals.get("interceptions_thrown", 0)
            if pd.notna(tds) and pd.notna(ints) and ints > 0:
                td_int = tds / ints
                features.append({
                    "player_id": pid,
                    "feature_name": "career_td_int_ratio",
                    "feature_value": round(float(td_int), 2),
                })

            # Simplified passer rating
            _compute_passer_rating(pid, totals, features)

    elif pos == "RB":
        # Yards per carry
        rush_yds = totals.get("rushing_yards", 0)
        carries = totals.get("rush_attempts", 0)
        if pd.notna(carries) and carries > 20:
            ypc = rush_yds / carries
            features.append({
                "player_id": pid,
                "feature_name": "career_yards_per_carry",
                "feature_value": round(float(ypc), 2),
            })

        # Receiving yards per reception
        rec_yds = totals.get("receiving_yards", 0)
        recs = totals.get("receptions", 0)
        if pd.notna(recs) and recs > 5:
            ypr = rec_yds / recs
            features.append({
                "player_id": pid,
                "feature_name": "career_yards_per_reception",
                "feature_value": round(float(ypr), 2),
            })

    elif pos in ("WR", "TE"):
        # Yards per reception
        rec_yds = totals.get("receiving_yards", 0)
        recs = totals.get("receptions", 0)
        if pd.notna(recs) and recs > 10:
            ypr = rec_yds / recs
            features.append({
                "player_id": pid,
                "feature_name": "career_yards_per_reception",
                "feature_value": round(float(ypr), 2),
            })

        # TD per reception
        rec_tds = totals.get("receiving_tds", 0)
        if pd.notna(recs) and recs > 10 and pd.notna(rec_tds):
            td_per_rec = rec_tds / recs
            features.append({
                "player_id": pid,
                "feature_name": "career_td_per_reception",
                "feature_value": round(float(td_per_rec), 4),
            })


def _compute_passer_rating(pid: str, totals: pd.Series, features: list[dict]) -> None:
    """Compute NCAA passer rating approximation."""
    att = totals.get("pass_attempts", 0)
    comp = totals.get("completions", 0)
    yds = totals.get("passing_yards", 0)
    tds = totals.get("passing_tds", 0)
    ints = totals.get("interceptions_thrown", 0)

    if not pd.notna(att) or att < 20:
        return

    try:
        a = max(0, min(((comp / att) - 0.3) * 5, 2.375))
        b = max(0, min(((yds / att) - 3) * 0.25, 2.375))
        c = max(0, min((tds / att) * 20, 2.375))
        d = max(0, min(2.375 - ((ints / att) * 25), 2.375))
        rating = ((a + b + c + d) / 6.0) * 100.0

        features.append({
            "player_id": pid,
            "feature_name": "career_passer_rating",
            "feature_value": round(float(rating), 2),
        })
    except (ZeroDivisionError, ValueError):
        pass


def _infer_position_group(raw_position, player_df: pd.DataFrame) -> str:
    """
    Infer position group from raw position string or stats patterns.

    Used when position_group is NULL (common for CFBD-sourced prospects).
    """
    from src.utils.config import POSITION_GROUP_MAP

    # Try raw position mapping first
    if pd.notna(raw_position) and raw_position:
        mapped = POSITION_GROUP_MAP.get(str(raw_position).strip().upper())
        if mapped:
            return mapped

    # Infer from stats patterns
    totals = player_df.sum(numeric_only=True)
    pass_yds = totals.get("passing_yards", 0) or 0
    rush_yds = totals.get("rushing_yards", 0) or 0
    rec_yds = totals.get("receiving_yards", 0) or 0
    tackles = totals.get("tackles", 0) or 0
    sacks = totals.get("sacks", 0) or 0

    if pass_yds > 500:
        return "QB"
    elif rec_yds > rush_yds and rec_yds > 100:
        return "WR"
    elif rush_yds > 100:
        return "RB"
    elif tackles > 10 and sacks > 1:
        return "DL"
    elif tackles > 10:
        return "LB"
    else:
        return "DB"  # default fallback

