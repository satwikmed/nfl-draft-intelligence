"""
Feature builder: orchestrates all feature modules and stores results.

Computes the full feature vector (30-50 features) per prospect
and writes to the features table in the database.
"""

import logging
from typing import Optional

import pandas as pd

from src.features.athletic import compute_athletic_features
from src.features.production import compute_production_features
from src.features.context import compute_context_features
from src.utils.db import get_db_connection, upsert_features, query_df

logger = logging.getLogger(__name__)


def build_all_features(player_ids: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Compute and store all features for prospects.

    Orchestrates athletic, production, and context feature modules,
    combines results, and upserts to the features table.

    Args:
        player_ids: Optional list of specific player IDs. If None, all.

    Returns:
        Combined DataFrame of all features (EAV format).
    """
    logger.info("=" * 60)
    logger.info("BUILDING FEATURE VECTORS")
    logger.info("=" * 60)

    all_dfs: list[pd.DataFrame] = []

    # 1. Athletic features
    logger.info("--- Athletic Features ---")
    try:
        athletic_df = compute_athletic_features(player_ids)
        if not athletic_df.empty:
            all_dfs.append(athletic_df)
            logger.info("Athletic features: %d entries for %d players",
                        len(athletic_df), athletic_df["player_id"].nunique())
    except Exception as e:
        logger.error("Athletic features FAILED: %s", e, exc_info=True)

    # 2. Production features
    logger.info("--- Production Features ---")
    try:
        production_df = compute_production_features(player_ids)
        if not production_df.empty:
            all_dfs.append(production_df)
            logger.info("Production features: %d entries for %d players",
                        len(production_df), production_df["player_id"].nunique())
    except Exception as e:
        logger.error("Production features FAILED: %s", e, exc_info=True)

    # 3. Context features
    logger.info("--- Context Features ---")
    try:
        context_df = compute_context_features(player_ids)
        if not context_df.empty:
            all_dfs.append(context_df)
            logger.info("Context features: %d entries for %d players",
                        len(context_df), context_df["player_id"].nunique())
    except Exception as e:
        logger.error("Context features FAILED: %s", e, exc_info=True)

    # Combine all
    if not all_dfs:
        logger.warning("No features computed.")
        return pd.DataFrame(columns=["player_id", "feature_name", "feature_value"])

    combined = pd.concat(all_dfs, ignore_index=True)

    # Deduplicate: if same player + feature appears multiple times, keep last
    combined = combined.drop_duplicates(
        subset=["player_id", "feature_name"], keep="last"
    )

    logger.info("-" * 60)
    logger.info("TOTAL: %d features for %d unique players",
                len(combined), combined["player_id"].nunique())

    # Feature count per player summary
    feature_counts = combined.groupby("player_id").size()
    logger.info("Features per player: min=%d, median=%d, max=%d",
                feature_counts.min(), feature_counts.median(), feature_counts.max())

    # Store in database
    logger.info("Writing features to database...")
    with get_db_connection() as conn:
        n = upsert_features(conn, combined)
    logger.info("Stored %d feature entries", n)

    return combined


def get_feature_matrix(position_group: Optional[str] = None,
                       min_features: int = 5) -> pd.DataFrame:
    """
    Load features from DB and pivot into a wide-format matrix.

    Each row is a player, each column is a feature.

    Args:
        position_group: Filter to specific position group.
        min_features: Minimum features required per player.

    Returns:
        Wide DataFrame with player_id as index, feature names as columns.
    """
    sql = """
        SELECT f.player_id, f.feature_name, f.feature_value,
               p.position_group, p.draft_year
        FROM features f
        INNER JOIN prospects p ON f.player_id = p.player_id
        WHERE p.position_group IS NOT NULL
    """
    params: list = []
    if position_group:
        sql += " AND p.position_group = ?"
        params.append(position_group)

    df = query_df(sql, tuple(params) if params else None)

    if df.empty:
        return pd.DataFrame()

    # Pivot to wide format
    wide = df.pivot_table(
        index="player_id",
        columns="feature_name",
        values="feature_value",
        aggfunc="first",
    )

    # Filter to players with enough features
    feature_count = wide.notna().sum(axis=1)
    wide = wide[feature_count >= min_features]

    logger.info(
        "Feature matrix: %d players × %d features (pos=%s)",
        len(wide), len(wide.columns), position_group or "ALL",
    )
    return wide


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    build_all_features()
