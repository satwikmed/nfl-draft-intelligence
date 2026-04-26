"""
Model A: Pro Readiness Score — XGBoost classifier.

Position-specific binary classification: will this prospect become a
"successful" NFL player within 3 seasons?

Outputs probability 0-100 as the Pro Readiness Score.
Generates SHAP values for every prediction.
"""

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report
)

from src.utils.config import (
    MODELED_POSITION_GROUPS, SUCCESS_THRESHOLDS,
    TRAIN_YEARS, VAL_YEARS, PREDICT_YEARS, DATA_DIR,
)
from src.utils.db import query_df, get_db_connection, upsert_predictions
from src.features.builder import get_feature_matrix

logger = logging.getLogger(__name__)

MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)


def train_pro_readiness_models() -> dict[str, dict]:
    """
    Train position-specific XGBoost models for Pro Readiness scoring.

    Returns dict of position group → evaluation metrics.
    """
    logger.info("=" * 60)
    logger.info("TRAINING PRO READINESS MODELS")
    logger.info("=" * 60)

    # Build labels
    labels_df = _build_success_labels()
    logger.info("Built success labels: %d players, %.1f%% success rate",
                len(labels_df), 100 * labels_df["success"].mean())

    results = {}

    for pos_group in MODELED_POSITION_GROUPS:
        logger.info("-" * 40)
        logger.info("Training model for: %s", pos_group)

        try:
            metrics = _train_position_model(pos_group, labels_df)
            if metrics:
                results[pos_group] = metrics
                logger.info("  %s — AUC: %.3f, F1: %.3f",
                           pos_group, metrics.get("auc", 0), metrics.get("f1", 0))
        except Exception as e:
            logger.error("  %s FAILED: %s", pos_group, e, exc_info=True)

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE — %d/%d position models trained",
                len(results), len(MODELED_POSITION_GROUPS))

    return results


def predict_pro_readiness(player_ids: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Generate Pro Readiness Scores for prospects.

    Loads trained models and predicts for specified players (or all).

    Returns:
        DataFrame with player_id, pro_readiness_score.
    """
    logger.info("Generating Pro Readiness predictions...")

    all_predictions = []

    for pos_group in MODELED_POSITION_GROUPS:
        model_path = MODELS_DIR / f"pro_readiness_{pos_group}.pkl"
        if not model_path.exists():
            continue

        with open(model_path, "rb") as f:
            model_data = pickle.load(f)

        model = model_data["model"]
        feature_cols = model_data["features"]

        # Get feature matrix for this position
        feature_matrix = get_feature_matrix(pos_group, min_features=3)
        if feature_matrix.empty:
            continue

        if player_ids:
            feature_matrix = feature_matrix[feature_matrix.index.isin(player_ids)]
            if feature_matrix.empty:
                continue

        # Align features
        available = [c for c in feature_cols if c in feature_matrix.columns]
        if len(available) < 3:
            continue

        X = feature_matrix[available].fillna(0)
        # Add missing columns as zeros
        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0
        X = X[feature_cols]

        # Predict probabilities
        probs = model.predict_proba(X)[:, 1]
        scores = (probs * 100).round(1)

        for pid, score in zip(X.index, scores):
            all_predictions.append({
                "player_id": pid,
                "pro_readiness_score": float(score),
            })

    result = pd.DataFrame(all_predictions)
    if not result.empty:
        # Store in database
        with get_db_connection() as conn:
            # Upsert predictions (just the score part)
            for _, row in result.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO predictions (player_id, pro_readiness_score)
                       VALUES (?, ?)
                       ON CONFLICT(player_id) DO UPDATE SET pro_readiness_score=?""",
                    (row["player_id"], row["pro_readiness_score"], row["pro_readiness_score"])
                )
        logger.info("Stored %d Pro Readiness predictions", len(result))

    return result


def _build_success_labels() -> pd.DataFrame:
    """
    Build binary success labels from NFL performance data.

    A player is labeled "successful" if they meet position-specific
    thresholds within their first 3 NFL seasons.
    """
    logger.info("Building success labels...")

    # Get drafted players with NFL performance
    sql = """
        SELECT p.player_id, p.position_group, p.draft_year,
               d.round as draft_round,
               n.season, n.games_played, n.games_started,
               n.passing_yards, n.passing_tds,
               n.rushing_yards, n.rushing_tds,
               n.receiving_yards, n.receiving_tds, n.receptions,
               n.tackles, n.sacks, n.interceptions
        FROM prospects p
        INNER JOIN draft_picks d ON p.player_id = d.player_id
        INNER JOIN nfl_performance n ON p.player_id = n.player_id
        WHERE p.position_group IS NOT NULL
          AND p.draft_year IS NOT NULL
          AND n.season <= p.draft_year + 3
    """
    df = query_df(sql)

    if df.empty:
        logger.warning("No NFL performance data for labeling.")
        return pd.DataFrame(columns=["player_id", "position_group", "draft_year", "success"])

    # Evaluate success per player
    labels = []
    for pid, player_df in df.groupby("player_id"):
        pos = player_df["position_group"].iloc[0]
        draft_year = player_df["draft_year"].iloc[0]
        draft_round = player_df["draft_round"].iloc[0]

        thresholds = SUCCESS_THRESHOLDS.get(pos, {})
        success = _evaluate_success(player_df, thresholds, draft_round)

        labels.append({
            "player_id": pid,
            "position_group": pos,
            "draft_year": draft_year,
            "success": int(success),
        })

    result = pd.DataFrame(labels)
    logger.info("Success labels: %d players, %.1f%% success rate",
                len(result), 100 * result["success"].mean())

    return result


def _evaluate_success(player_df: pd.DataFrame, thresholds: dict, draft_round: float) -> bool:
    """Check if player meets success thresholds in any of their first 3 seasons."""
    
    # Scale expectations based on draft capital (leave games_played threshold static)
    multiplier = 1.0
    if pd.isna(draft_round) or draft_round > 5:
        multiplier = 0.5
    elif draft_round <= 2:
        multiplier = 1.5

    for _, row in player_df.iterrows():
        meets_all = True

        for stat, threshold in thresholds.items():
            col = stat.replace("min_", "")
            val = row.get(col)
            
            # Apply dynamic scaling unless it's games played
            adjusted_threshold = threshold * multiplier if stat != "min_games_played" else threshold
            
            if pd.isna(val) or val < adjusted_threshold:
                meets_all = False
                break

        if meets_all:
            return True

    return False


def _train_position_model(pos_group: str, labels_df: pd.DataFrame) -> dict | None:
    """Train a single position-specific XGBoost model."""
    try:
        import xgboost as xgb
    except ImportError:
        logger.error("xgboost not installed")
        return None

    # Get feature matrix for this position
    feature_matrix = get_feature_matrix(pos_group, min_features=3)
    if feature_matrix.empty:
        logger.warning("  No features for %s", pos_group)
        return None

    # Get labels for this position
    pos_labels = labels_df[labels_df["position_group"] == pos_group].copy()
    if pos_labels.empty:
        logger.warning("  No labels for %s", pos_group)
        return None

    # Join features with labels
    pos_labels = pos_labels.set_index("player_id")
    common = feature_matrix.index.intersection(pos_labels.index)

    if len(common) < 20:
        logger.warning("  Too few labeled samples for %s: %d", pos_group, len(common))
        return None

    X = feature_matrix.loc[common].copy()
    y = pos_labels.loc[common, "success"].values
    draft_years = pos_labels.loc[common, "draft_year"].values

    # Split: train on TRAIN_YEARS, validate on VAL_YEARS
    train_mask = np.isin(draft_years, TRAIN_YEARS)
    val_mask = np.isin(draft_years, VAL_YEARS)

    if train_mask.sum() < 10:
        # Fall back to random split
        logger.info("  Using cross-validation split (not enough year-based data)")
        train_mask = np.ones(len(X), dtype=bool)
        val_mask = np.zeros(len(X), dtype=bool)

    # Fill NaN with 0 for XGBoost
    X = X.fillna(0)
    feature_cols = list(X.columns)

    X_train = X[train_mask].values
    y_train = y[train_mask]

    # Handle class imbalance
    n_pos = y_train.sum()
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)

    logger.info("  Train: %d samples (%d success, %d fail)",
                len(X_train), n_pos, n_neg)

    # XGBoost parameters
    params = {
        "max_depth": 4,
        "learning_rate": 0.05,
        "n_estimators": 200,
        "scale_pos_weight": scale_pos_weight,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "random_state": 42,
        "use_label_encoder": False,
        "verbosity": 0,
    }

    model = xgb.XGBClassifier(**params)

    # Cross-validation on training data
    if len(X_train) >= 30:
        cv = StratifiedKFold(n_splits=min(5, len(X_train) // 5), shuffle=True, random_state=42)
        cv_aucs = []
        for train_idx, test_idx in cv.split(X_train, y_train):
            model.fit(X_train[train_idx], y_train[train_idx])
            probs = model.predict_proba(X_train[test_idx])[:, 1]
            try:
                auc = roc_auc_score(y_train[test_idx], probs)
                cv_aucs.append(auc)
            except ValueError:
                pass

        if cv_aucs:
            logger.info("  CV AUC: %.3f ± %.3f", np.mean(cv_aucs), np.std(cv_aucs))

    # Train final model on all training data
    model.fit(X_train, y_train)

    # Evaluate on validation set if available
    metrics: dict = {"n_train": len(X_train)}

    if val_mask.sum() >= 5:
        X_val = X[val_mask].values
        y_val = y[val_mask]
        val_probs = model.predict_proba(X_val)[:, 1]
        val_preds = (val_probs >= 0.5).astype(int)

        try:
            metrics["auc"] = float(roc_auc_score(y_val, val_probs))
        except ValueError:
            metrics["auc"] = 0.0

        metrics["accuracy"] = float(accuracy_score(y_val, val_preds))
        metrics["f1"] = float(f1_score(y_val, val_preds, zero_division=0))
        metrics["precision"] = float(precision_score(y_val, val_preds, zero_division=0))
        metrics["recall"] = float(recall_score(y_val, val_preds, zero_division=0))

        logger.info("  Val: AUC=%.3f, Acc=%.3f, F1=%.3f",
                    metrics["auc"], metrics["accuracy"], metrics["f1"])
    else:
        # Use CV metrics
        metrics["auc"] = float(np.mean(cv_aucs)) if cv_aucs else 0.0
        metrics["f1"] = 0.0

    # Save model
    model_data = {
        "model": model,
        "features": feature_cols,
        "position_group": pos_group,
        "metrics": metrics,
    }

    model_path = MODELS_DIR / f"pro_readiness_{pos_group}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    logger.info("  Saved model to %s", model_path)
    return metrics


def get_shap_values(player_id: str) -> dict | None:
    """
    Generate SHAP explanations for a single player's Pro Readiness Score.

    Returns dict with feature importances and the player's score breakdown.
    """
    try:
        import shap
    except ImportError:
        logger.warning("shap not installed")
        return None

    # Get player's position group
    p = query_df(
        "SELECT position_group FROM prospects WHERE player_id = ?",
        (player_id,)
    )
    if p.empty:
        return None

    pos = p.iloc[0]["position_group"]
    model_path = MODELS_DIR / f"pro_readiness_{pos}.pkl"
    if not model_path.exists():
        return None

    with open(model_path, "rb") as f:
        model_data = pickle.load(f)

    model = model_data["model"]
    feature_cols = model_data["features"]

    # Get features for this player
    feature_matrix = get_feature_matrix(pos, min_features=3)
    if player_id not in feature_matrix.index:
        return None

    X = feature_matrix.loc[[player_id]][feature_cols].fillna(0)
    for col in feature_cols:
        if col not in X.columns:
            X[col] = 0
    X = X[feature_cols]

    # Compute SHAP values
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X)

    # Build explanation dict
    if isinstance(shap_vals, list):
        sv = shap_vals[1][0]  # class 1 (success) SHAP values
    else:
        sv = shap_vals[0]

    explanation = {
        "player_id": player_id,
        "position_group": pos,
        "base_value": float(explainer.expected_value[1]) if isinstance(explainer.expected_value, np.ndarray) else float(explainer.expected_value),
        "features": {},
    }

    for feat, val, sv_val in zip(feature_cols, X.iloc[0].values, sv):
        explanation["features"][feat] = {
            "value": float(val),
            "shap_value": float(sv_val),
        }

    # Sort by absolute SHAP importance
    explanation["top_features"] = sorted(
        explanation["features"].items(),
        key=lambda x: abs(x[1]["shap_value"]),
        reverse=True,
    )[:10]

    return explanation


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    results = train_pro_readiness_models()
    if results:
        predictions = predict_pro_readiness()
        logger.info("Generated %d predictions", len(predictions))
