"""
Ingest historical NFL Draft picks from nflreadpy.

Pulls draft data for all years (2000–2025), maps to our schema,
and upserts into the `prospects` and `draft_picks` tables.
"""

import logging

import pandas as pd

from src.utils.config import POSITION_GROUP_MAP, START_YEAR, END_YEAR
from src.utils.db import get_db_connection, upsert_prospects, upsert_draft_picks
from src.ingestion.combine import generate_player_id

logger = logging.getLogger(__name__)


def ingest_draft_history() -> int:
    """
    Pull NFL Draft picks via nflreadpy and store in the database.

    Returns:
        Number of draft pick records upserted.
    """
    logger.info("Starting draft history ingestion...")

    try:
        import nflreadpy as nfl
    except ImportError:
        logger.error("nflreadpy not installed. Install with: pip install nflreadpy")
        return 0

    # Load draft picks (returns Polars DataFrame)
    logger.info("Loading draft picks from nflverse...")
    draft_raw = nfl.load_draft_picks()

    # Convert Polars -> Pandas
    if hasattr(draft_raw, "to_pandas"):
        draft_df = draft_raw.to_pandas()
    else:
        draft_df = pd.DataFrame(draft_raw)

    logger.info("Raw draft records loaded: %d", len(draft_df))
    logger.debug("Draft columns: %s", list(draft_df.columns))

    # ── Detect columns ────────────────────────────────────────────────

    col_map = _detect_draft_columns(draft_df)

    # Filter to year range
    year_col = col_map.get("season")
    if year_col:
        draft_df[year_col] = pd.to_numeric(draft_df[year_col], errors="coerce")
        draft_df = draft_df[
            (draft_df[year_col] >= START_YEAR) &
            (draft_df[year_col] <= END_YEAR)
        ].copy()
        logger.info("Filtered to %d-%d: %d picks", START_YEAR, END_YEAR, len(draft_df))

    if draft_df.empty:
        logger.warning("No draft data after filtering.")
        return 0

    # ── Generate player IDs & map to schema ───────────────────────────

    name_col = col_map.get("name", "")
    school_col = col_map.get("school", "")
    yr_col = col_map.get("season", "")

    draft_df["player_id"] = draft_df.apply(
        lambda row: generate_player_id(
            str(row.get(name_col, "")),
            str(row.get(school_col, "")) if pd.notna(row.get(school_col)) else None,
            row.get(yr_col),
        ),
        axis=1,
    )

    # Get position info
    pos_col = col_map.get("position", "")
    positions = draft_df.get(pos_col, pd.Series(dtype="str")) if pos_col else pd.Series(dtype="str")

    # Build prospects DataFrame (upsert — won't overwrite combine data)
    prospects_df = pd.DataFrame({
        "player_id": draft_df["player_id"],
        "name": draft_df.get(name_col, pd.Series(dtype="str")),
        "school": draft_df.get(school_col, pd.Series(dtype="str")),
        "position": positions,
        "position_group": positions.map(
            lambda p: POSITION_GROUP_MAP.get(str(p).strip().upper(), None) if pd.notna(p) else None
        ),
        "draft_year": pd.to_numeric(draft_df.get(yr_col, pd.Series(dtype="int")), errors="coerce"),
    })

    # Handle height/weight if available in draft data
    ht_col = col_map.get("height")
    wt_col = col_map.get("weight")
    if ht_col and ht_col in draft_df.columns:
        prospects_df["height_inches"] = pd.to_numeric(draft_df[ht_col], errors="coerce")
    if wt_col and wt_col in draft_df.columns:
        prospects_df["weight_lbs"] = pd.to_numeric(draft_df[wt_col], errors="coerce")

    # Build draft picks DataFrame
    round_col = col_map.get("round", "")
    pick_col = col_map.get("pick", "")
    team_col = col_map.get("team", "")

    picks_df = pd.DataFrame({
        "player_id": draft_df["player_id"],
        "round": pd.to_numeric(draft_df.get(round_col, pd.Series(dtype="int")), errors="coerce"),
        "pick": pd.to_numeric(draft_df.get(pick_col, pd.Series(dtype="int")), errors="coerce"),
        "team": draft_df.get(team_col, pd.Series(dtype="str")),
    })

    # Log summary
    if round_col and round_col in draft_df.columns:
        for rnd in sorted(draft_df[round_col].dropna().unique()):
            count = (draft_df[round_col] == rnd).sum()
            logger.debug("  Round %s: %d picks", rnd, count)

    # ── Upsert to database ────────────────────────────────────────────

    with get_db_connection() as conn:
        n_prospects = upsert_prospects(conn, prospects_df)
        n_picks = upsert_draft_picks(conn, picks_df)

    logger.info(
        "Draft history ingestion complete: %d prospects, %d picks",
        n_prospects, n_picks,
    )
    return n_picks


# =============================================================================
# Helpers
# =============================================================================

def _detect_draft_columns(df: pd.DataFrame) -> dict[str, str]:
    """Auto-detect column name mappings from the raw draft DataFrame."""
    cols = {c.lower(): c for c in df.columns}
    mapping: dict[str, str] = {}

    for key, candidates in {
        "name": ["pfr_player_name", "player_name", "name", "player", "full_name"],
        "school": ["college", "school", "college_name"],
        "position": ["position", "pos"],
        "season": ["season", "draft_year", "year"],
        "round": ["round", "draft_round", "rnd"],
        "pick": ["pick", "overall", "draft_overall", "draft_pick", "ovr"],
        "team": ["team", "tm", "draft_team"],
        "height": ["ht", "height"],
        "weight": ["wt", "weight"],
    }.items():
        for candidate in candidates:
            if candidate in cols:
                mapping[key] = cols[candidate]
                break

    logger.debug("Draft column mapping: %s", mapping)
    return mapping


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_draft_history()
