"""
Model B: Historical Comp Engine — cosine similarity search.

For any prospect, finds the 3 most similar historical players
(same position group), weighted by SHAP feature importance.
"""

import logging
import pickle
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.config import MODELED_POSITION_GROUPS, DATA_DIR
from src.utils.db import query_df, get_db_connection
from src.features.builder import get_feature_matrix

logger = logging.getLogger(__name__)

MODELS_DIR = DATA_DIR / "models"


def find_comps(player_id: str, n_comps: int = 3) -> list[dict]:
    """
    Find the N most similar historical players to a given prospect.

    Uses cosine similarity on the feature vector, weighted by SHAP
    importance from Model A (if available).

    Args:
        player_id: Target player ID.
        n_comps: Number of comparisons to return.

    Returns:
        List of dicts with keys: comp_id, comp_name, similarity,
        matching_features, diverging_features.
    """
    # Get player's position
    player = query_df(
        "SELECT position_group, draft_year, name FROM prospects WHERE player_id = ?",
        (player_id,)
    )
    if player.empty:
        logger.warning("Player %s not found", player_id)
        return []

    pos = player.iloc[0]["position_group"]
    draft_year = player.iloc[0]["draft_year"]
    player_name = player.iloc[0]["name"]

    if not pos:
        logger.warning("No position group for %s", player_id)
        return []

    # Get feature matrix for this position
    feature_matrix = get_feature_matrix(pos, min_features=3)
    if feature_matrix.empty or player_id not in feature_matrix.index:
        logger.warning("No features for %s", player_id)
        return []

    # Load SHAP weights if available
    weights = _load_shap_weights(pos)

    # Prepare feature vectors
    X = feature_matrix.fillna(0).copy()

    # Apply SHAP-based feature weighting
    if weights is not None:
        for col in X.columns:
            if col in weights:
                X[col] *= weights[col]

    # Normalize
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X),
        index=X.index,
        columns=X.columns,
    )

    # Compute cosine similarity
    target_vec = X_scaled.loc[[player_id]].values
    all_vecs = X_scaled.values

    similarities = cosine_similarity(target_vec, all_vecs)[0]

    # Create similarity ranking (exclude self)
    sim_df = pd.DataFrame({
        "player_id": X_scaled.index,
        "similarity": similarities,
    })

    # Exclude self and players from same/later draft year (only compare to historicals)
    sim_df = sim_df[sim_df["player_id"] != player_id]

    # Optionally filter to historical players only
    if pd.notna(draft_year):
        historical_pids = query_df(
            "SELECT player_id FROM prospects WHERE draft_year < ? AND position_group = ?",
            (int(draft_year), pos)
        )["player_id"].tolist()
        sim_df = sim_df[sim_df["player_id"].isin(historical_pids)]

    sim_df = sim_df.sort_values("similarity", ascending=False).head(n_comps)

    # Build comp cards
    comps = []
    raw_features = feature_matrix  # unweighted for comparison

    for _, row in sim_df.iterrows():
        comp_id = row["player_id"]
        similarity = round(float(row["similarity"]) * 100, 1)

        # Get comp player info
        comp_info = query_df(
            "SELECT name, school, draft_year FROM prospects WHERE player_id = ?",
            (comp_id,)
        )
        comp_name = comp_info.iloc[0]["name"] if not comp_info.empty else comp_id

        # Get NFL career summary for the comp
        nfl_summary = _get_nfl_summary(comp_id)

        # Find matching and diverging features
        matching, diverging = _compare_features(
            player_id, comp_id, raw_features
        )

        comps.append({
            "comp_id": comp_id,
            "comp_name": comp_name,
            "similarity": similarity,
            "nfl_summary": nfl_summary,
            "matching_features": matching,
            "diverging_features": diverging,
        })

    return comps


def build_all_comps() -> int:
    """
    Find comps for all drafted prospects and store in predictions table.
    Optimized to pivot matrices once per position group.
    """
    logger.info("Building historical comps for all prospects...")

    n_processed = 0
    with get_db_connection() as conn:
        for pos in MODELED_POSITION_GROUPS:
            logger.info("Processing position: %s", pos)
            
            # Get feature matrix once
            feature_matrix = get_feature_matrix(pos, min_features=3)
            if feature_matrix.empty:
                continue
                
            # Load weights once
            weights = _load_shap_weights(pos)
            
            # Pre-calculate scaled matrix for all players in this pos
            X = feature_matrix.fillna(0).copy()
            if weights is not None:
                for col in X.columns:
                    if col in weights:
                        X[col] *= weights[col]
            
            scaler = StandardScaler()
            try:
                X_scaled = pd.DataFrame(scaler.fit_transform(X), index=X.index, columns=X.columns)
            except Exception:
                continue

            # Get all players for this pos that need comps
            players = query_df(
                "SELECT player_id, draft_year FROM prospects WHERE position_group = ? AND player_id IN (SELECT player_id FROM draft_picks)",
                (pos,)
            )
            
            for _, p_row in players.iterrows():
                pid = p_row["player_id"]
                draft_year = p_row["draft_year"]
                
                if pid not in X_scaled.index:
                    continue
                
                # Similarities
                target_vec = X_scaled.loc[[pid]].values
                all_sims = cosine_similarity(target_vec, X_scaled.values)[0]
                
                sim_df = pd.DataFrame({"pid": X_scaled.index, "sim": all_sims})
                sim_df = sim_df[sim_df["pid"] != pid]
                
                # Historical only
                if pd.notna(draft_year):
                    h_pids = query_df("SELECT player_id FROM prospects WHERE draft_year < ? AND position_group = ?", (int(draft_year), pos))["player_id"].tolist()
                    sim_df = sim_df[sim_df["pid"].isin(h_pids)]
                
                sim_df = sim_df.sort_values("sim", ascending=False).head(3)
                
                if not sim_df.empty:
                    comps = []
                    for _, s_row in sim_df.iterrows():
                        cid = s_row["pid"]
                        c_name = query_df("SELECT name FROM prospects WHERE player_id = ?", (cid,)).iloc[0]["name"]
                        comps.append({"comp_id": cid, "comp_name": c_name, "similarity": round(float(s_row["sim"]) * 100, 1)})
                    
                    _store_comps(pid, comps)
                    n_processed += 1
                    
                if n_processed % 100 == 0:
                    logger.info("  Processed %d players...", n_processed)

    logger.info("Comps complete: %d players processed", n_processed)
    return n_processed


def _load_shap_weights(pos_group: str) -> dict[str, float] | None:
    """Load SHAP feature importance weights from Model A."""
    model_path = MODELS_DIR / f"pro_readiness_{pos_group}.pkl"
    if not model_path.exists():
        return None

    try:
        with open(model_path, "rb") as f:
            model_data = pickle.load(f)

        model = model_data["model"]
        feature_cols = model_data["features"]

        # Use built-in feature importance as proxy for SHAP
        importances = model.feature_importances_
        weights = {}
        for feat, imp in zip(feature_cols, importances):
            weights[feat] = max(imp, 0.01)  # minimum weight of 0.01

        return weights
    except Exception:
        return None


def _get_nfl_summary(player_id: str) -> dict:
    """Get a brief NFL career summary for a historical comp."""
    nfl = query_df(
        """SELECT season, games_played, games_started,
                  passing_yards, passing_tds, rushing_yards, rushing_tds,
                  receiving_yards, receiving_tds, receptions,
                  tackles, sacks, interceptions
           FROM nfl_performance WHERE player_id = ?
           ORDER BY season""",
        (player_id,)
    )

    if nfl.empty:
        return {"seasons": 0, "summary": "No NFL data available"}

    summary = {
        "seasons": len(nfl),
        "total_games": int(nfl["games_played"].sum()) if nfl["games_played"].notna().any() else 0,
    }

    # Add relevant career totals
    for col in ["passing_yards", "rushing_yards", "receiving_yards",
                "tackles", "sacks"]:
        total = nfl[col].sum()
        if pd.notna(total) and total > 0:
            summary[f"career_{col}"] = int(total)

    return summary


def _compare_features(target_id: str, comp_id: str,
                      feature_matrix: pd.DataFrame) -> tuple[list, list]:
    """Find features where target and comp overlap vs. diverge."""
    if target_id not in feature_matrix.index or comp_id not in feature_matrix.index:
        return [], []

    target = feature_matrix.loc[target_id]
    comp = feature_matrix.loc[comp_id]

    matching = []
    diverging = []

    for feat in feature_matrix.columns:
        t_val = target.get(feat)
        c_val = comp.get(feat)

        if pd.isna(t_val) or pd.isna(c_val):
            continue

        # Compare relative to column std
        col_std = feature_matrix[feat].std()
        if col_std == 0:
            continue

        diff = abs(t_val - c_val) / col_std

        entry = {
            "feature": feat,
            "target_value": round(float(t_val), 2),
            "comp_value": round(float(c_val), 2),
        }

        if diff < 0.5:
            matching.append(entry)
        elif diff > 1.5:
            diverging.append(entry)

    # Return top 5 each
    return matching[:5], diverging[:5]


def _store_comps(player_id: str, comps: list[dict]) -> None:
    """Store comp results in the predictions table."""
    with get_db_connection() as conn:
        update_data = {"player_id": player_id}
        for i, comp in enumerate(comps[:3], 1):
            update_data[f"comp_{i}_id"] = comp["comp_id"]
            update_data[f"comp_{i}_similarity"] = comp["similarity"]

        # Build dynamic UPDATE
        set_clauses = []
        values = []
        for key, val in update_data.items():
            if key != "player_id":
                set_clauses.append(f"{key} = ?")
                values.append(val)

        values.append(player_id)

        conn.execute(
            f"""INSERT INTO predictions (player_id, {', '.join(k for k in update_data if k != 'player_id')})
                VALUES (?, {', '.join('?' for _ in set_clauses)})
                ON CONFLICT(player_id) DO UPDATE SET {', '.join(set_clauses)}""",
            [player_id] + values[:-1] + values[:-1]
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Build all comps
    build_all_comps()
    
    # Test with a known player
    comps = find_comps("patrickmahomes_texastech_2017")
    for comp in comps:
        logger.info("Comp: %s (%.1f%% similar)", comp["comp_name"], comp["similarity"])
