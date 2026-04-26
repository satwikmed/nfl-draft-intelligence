"""
Ingest NFL player seasonal performance stats from nflreadpy.

Pulls player-season stats and maps them to the `nfl_performance` table.
Uses GSIS player IDs to match with draft picks data from nflverse.
This data is used to define "success" labels for Model A and
survival targets for Model C.
"""

import logging

import pandas as pd

from src.utils.config import START_YEAR, END_YEAR
from src.utils.db import get_db_connection, upsert_nfl_performance

logger = logging.getLogger(__name__)


def ingest_nfl_performance() -> int:
    """
    Pull NFL seasonal player stats via nflreadpy and store in the database.

    Matches NFL performance to prospects via GSIS ID (the nflverse player
    identifier that links draft_picks.gsis_id ↔ player_stats.player_id).

    Returns:
        Number of NFL performance records upserted.
    """
    logger.info("Starting NFL performance data ingestion...")

    try:
        import nflreadpy as nfl
    except ImportError:
        logger.error("nflreadpy not installed. Install with: pip install nflreadpy")
        return 0

    # ── Build GSIS → player_id lookup from draft_picks ────────────────

    logger.info("Building GSIS ID → player_id mapping from database...")
    with get_db_connection() as conn:
        existing = pd.read_sql_query(
            """
            SELECT p.player_id, p.name, d.round, d.pick
            FROM prospects p
            INNER JOIN draft_picks d ON p.player_id = d.player_id
            """,
            conn,
        )

    # Also load draft picks from nflverse to get gsis_id mapping
    logger.info("Loading draft picks for GSIS ID mapping...")
    draft_raw = nfl.load_draft_picks()
    if hasattr(draft_raw, "to_pandas"):
        draft_df = draft_raw.to_pandas()
    else:
        draft_df = pd.DataFrame(draft_raw)

    # Filter to our year range
    draft_df = draft_df[
        (draft_df["season"] >= START_YEAR) &
        (draft_df["season"] <= END_YEAR)
    ].copy()

    # Build gsis_id → our player_id mapping
    from src.ingestion.combine import generate_player_id

    gsis_to_player_id: dict[str, str] = {}
    for _, row in draft_df.iterrows():
        gsis = str(row.get("gsis_id", ""))
        name = str(row.get("pfr_player_name", ""))
        school = str(row.get("college", ""))
        year = row.get("season")

        if gsis and gsis != "None" and gsis != "nan" and name:
            pid = generate_player_id(name, school if school != "nan" else None, year)
            gsis_to_player_id[gsis] = pid

    logger.info("Built GSIS mapping with %d entries", len(gsis_to_player_id))

    # ── Load player stats ─────────────────────────────────────────────

    seasons = list(range(START_YEAR, END_YEAR + 1))
    logger.info("Loading player stats for seasons %d-%d...", START_YEAR, END_YEAR)

    try:
        stats_raw = nfl.load_player_stats(seasons=seasons)
    except Exception as e:
        logger.error("Failed to load player stats: %s", e)
        logger.info("Retrying in smaller chunks...")
        stats_raw = _load_stats_chunked(nfl, seasons)
        if stats_raw is None:
            return 0

    # Convert Polars -> Pandas
    if hasattr(stats_raw, "to_pandas"):
        stats_df = stats_raw.to_pandas()
    else:
        stats_df = pd.DataFrame(stats_raw)

    logger.info("Raw player stat records loaded: %d", len(stats_df))

    if stats_df.empty:
        logger.warning("No player stats loaded.")
        return 0

    # ── Aggregate to season level ─────────────────────────────────────

    # The data is weekly — aggregate by player + season
    logger.info("Aggregating weekly stats to season level...")

    # Identify columns
    group_cols = ["player_id", "player_name", "player_display_name",
                  "position", "position_group", "season"]
    group_cols = [c for c in group_cols if c in stats_df.columns]

    sum_cols = [
        "completions", "attempts", "passing_yards", "passing_tds",
        "passing_interceptions", "carries", "rushing_yards", "rushing_tds",
        "receptions", "targets", "receiving_yards", "receiving_tds",
        "def_tackles_solo", "def_tackles_with_assist", "def_sacks",
        "def_interceptions", "def_pass_defended", "def_fumbles_forced",
    ]
    sum_cols = [c for c in sum_cols if c in stats_df.columns]

    agg_dict: dict[str, str] = {c: "sum" for c in sum_cols}

    season_df = stats_df.groupby(group_cols, as_index=False).agg(agg_dict)

    # Count games played (number of weeks with data)
    games_count = stats_df.groupby(group_cols).size().reset_index(name="games_played")
    season_df = season_df.merge(games_count, on=group_cols, how="left")

    logger.info("Aggregated to %d season-level records", len(season_df))

    # ── Match to prospects via GSIS ID ────────────────────────────────

    matched_count = 0
    unmatched_count = 0
    records = []

    for _, row in season_df.iterrows():
        gsis_id = str(row.get("player_id", ""))
        our_pid = gsis_to_player_id.get(gsis_id)

        if not our_pid:
            unmatched_count += 1
            continue

        matched_count += 1

        # Compute tackles total
        tackles = 0.0
        if "def_tackles_solo" in row.index and pd.notna(row.get("def_tackles_solo")):
            tackles += float(row["def_tackles_solo"])
        if "def_tackles_with_assist" in row.index and pd.notna(row.get("def_tackles_with_assist")):
            tackles += float(row["def_tackles_with_assist"])

        records.append({
            "player_id": our_pid,
            "season": int(row["season"]),
            "games_played": int(row.get("games_played", 0)) if pd.notna(row.get("games_played")) else None,
            "games_started": None,  # Not available in weekly stats
            "passing_yards": _safe_float(row.get("passing_yards")),
            "passing_tds": _safe_int(row.get("passing_tds")),
            "interceptions_thrown": _safe_int(row.get("passing_interceptions")),
            "rushing_yards": _safe_float(row.get("rushing_yards")),
            "rushing_tds": _safe_int(row.get("rushing_tds")),
            "receiving_yards": _safe_float(row.get("receiving_yards")),
            "receiving_tds": _safe_int(row.get("receiving_tds")),
            "receptions": _safe_int(row.get("receptions")),
            "tackles": tackles if tackles > 0 else None,
            "sacks": _safe_float(row.get("def_sacks")),
            "interceptions": _safe_int(row.get("def_interceptions")),
        })

    logger.info(
        "Matched %d season records to drafted prospects (%d unmatched/undrafted)",
        matched_count, unmatched_count,
    )

    if not records:
        logger.warning("No NFL performance records to upsert.")
        return 0

    perf_df = pd.DataFrame(records)

    # ── Upsert to database ────────────────────────────────────────────

    with get_db_connection() as conn:
        n_perf = upsert_nfl_performance(conn, perf_df)

    logger.info("NFL performance ingestion complete: %d records", n_perf)
    return n_perf


# =============================================================================
# Helpers
# =============================================================================

def _load_stats_chunked(nfl, seasons: list[int]):
    """Load stats in 5-year chunks to avoid memory issues."""
    chunks = []
    for i in range(0, len(seasons), 5):
        chunk_years = seasons[i : i + 5]
        logger.info("  Loading chunk: %s", chunk_years)
        try:
            chunk = nfl.load_player_stats(seasons=chunk_years)
            chunks.append(chunk)
        except Exception as e:
            logger.warning("  Failed for %s: %s", chunk_years, e)

    if not chunks:
        return None

    try:
        import polars as pl
        combined = pl.concat(chunks)
    except Exception:
        dfs = []
        for c in chunks:
            if hasattr(c, "to_pandas"):
                dfs.append(c.to_pandas())
            else:
                dfs.append(pd.DataFrame(c))
        combined = pd.concat(dfs, ignore_index=True)

    return combined


def _safe_float(val) -> float | None:
    """Safely convert to float."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Safely convert to int."""
    f = _safe_float(val)
    return int(f) if f is not None else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_nfl_performance()
