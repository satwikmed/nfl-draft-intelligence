"""
Ingest college football production stats from the CFBD API.

Uses direct HTTP requests to the CollegeFootballData.com API to pull
season-level player stats for FBS programs.

Requires CFBD_API_KEY environment variable.
"""

import logging
import time
from typing import Any

import pandas as pd
import requests

from src.utils.config import CFBD_API_KEY, START_YEAR, END_YEAR
from src.utils.db import get_db_connection, upsert_college_stats, upsert_prospects
from src.ingestion.combine import generate_player_id

logger = logging.getLogger(__name__)

CFBD_BASE_URL = "https://api.collegefootballdata.com"
RATE_LIMIT_DELAY: float = 0.3  # seconds between API calls

# Categories to pull from the CFBD API
STAT_CATEGORIES: list[str] = ["passing", "rushing", "receiving", "defensive"]


def ingest_college_stats() -> int:
    """
    Pull college player stats from CFBD API and store in the database.

    Iterates over years and stat categories, aggregates per player per season,
    then upserts into the database.

    Returns:
        Number of college stat records upserted.
    """
    logger.info("Starting college stats ingestion...")

    if not CFBD_API_KEY:
        logger.warning(
            "CFBD_API_KEY not set. Skipping college stats ingestion. "
            "Get a free key at https://collegefootballdata.com/"
        )
        return 0

    headers = {"Authorization": f"Bearer {CFBD_API_KEY}"}
    total_records = 0

    for year in range(START_YEAR, END_YEAR + 1):
        year_records = _ingest_year(year, headers)
        total_records += year_records
        if year_records > 0:
            logger.info("  Year %d: %d player-season records", year, year_records)
        else:
            logger.debug("  Year %d: 0 records", year)

    logger.info("College stats ingestion complete: %d total records", total_records)
    return total_records


def _ingest_year(year: int, headers: dict[str, str]) -> int:
    """
    Ingest all stat categories for a single year.

    Pulls passing, rushing, receiving, and defensive stats separately,
    then merges them by player into a single row per player-season.
    """
    all_stats: dict[str, dict[str, Any]] = {}  # keyed by player_id

    for category in STAT_CATEGORIES:
        try:
            raw = _api_get_player_stats(year, category, headers)
            if not raw:
                continue

            for entry in raw:
                name = entry.get("player", "")
                team = entry.get("team", "")
                position = entry.get("position", "")
                stat_type = str(entry.get("statType", "")).upper()
                stat_value = entry.get("stat")

                if not name:
                    continue

                pid = generate_player_id(name, team, year)

                if pid not in all_stats:
                    all_stats[pid] = {
                        "player_id": pid,
                        "name": name,
                        "school": team,
                        "position": position,
                        "season": year,
                        "games": None,
                        "passing_yards": None,
                        "passing_tds": None,
                        "interceptions_thrown": None,
                        "completions": None,
                        "pass_attempts": None,
                        "rushing_yards": None,
                        "rushing_tds": None,
                        "rush_attempts": None,
                        "receiving_yards": None,
                        "receiving_tds": None,
                        "receptions": None,
                        "tackles": None,
                        "sacks": None,
                        "interceptions": None,
                        "passes_defended": None,
                        "forced_fumbles": None,
                        "fumble_recoveries": None,
                    }

                _map_stat(all_stats[pid], category, stat_type, stat_value)

        except Exception as e:
            logger.warning("  %s/%d failed: %s", category, year, e)

        time.sleep(RATE_LIMIT_DELAY)

    if not all_stats:
        return 0

    df = pd.DataFrame(list(all_stats.values()))

    # Upsert
    with get_db_connection() as conn:
        # Ensure prospects exist
        prospect_cols = ["player_id", "name", "school", "position"]
        p_df = df[[c for c in prospect_cols if c in df.columns]].drop_duplicates(
            subset=["player_id"]
        )
        upsert_prospects(conn, p_df)
        n = upsert_college_stats(conn, df)

    return n


def _api_get_player_stats(
    year: int, category: str, headers: dict[str, str]
) -> list[dict] | None:
    """Make a single API call to get player season stats."""
    url = f"{CFBD_BASE_URL}/stats/player/season"
    params = {"year": year, "category": category}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.warning("Rate limited. Waiting 5 seconds...")
            time.sleep(5)
            return _api_get_player_stats(year, category, headers)
        logger.warning("HTTP error for %s/%d: %s", category, year, e)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("Request error for %s/%d: %s", category, year, e)
        return None


def _map_stat(record: dict, category: str, stat_type: str, value: Any) -> None:
    """
    Map a CFBD stat entry to our schema columns.

    The CFBD API returns entries like:
        {category: "passing", statType: "YDS", stat: "3500"}
    """
    try:
        val = float(value)
    except (ValueError, TypeError):
        return

    # Normalize stat_type
    st = stat_type.strip().upper()

    mapping = {
        # Passing
        ("passing", "YDS"): "passing_yards",
        ("passing", "TD"): "passing_tds",
        ("passing", "INT"): "interceptions_thrown",
        ("passing", "COMPLETIONS"): "completions",
        ("passing", "ATT"): "pass_attempts",
        # Rushing
        ("rushing", "YDS"): "rushing_yards",
        ("rushing", "TD"): "rushing_tds",
        ("rushing", "CAR"): "rush_attempts",
        ("rushing", "ATT"): "rush_attempts",
        # Receiving
        ("receiving", "YDS"): "receiving_yards",
        ("receiving", "TD"): "receiving_tds",
        ("receiving", "REC"): "receptions",
        # Defensive
        ("defensive", "TOT"): "tackles",
        ("defensive", "TFL"): None,  # tackles for loss — skip
        ("defensive", "SACKS"): "sacks",
        ("defensive", "INT"): "interceptions",
        ("defensive", "PD"): "passes_defended",
        ("defensive", "FF"): "forced_fumbles",
        ("defensive", "FR"): "fumble_recoveries",
    }

    key = (category, st)
    col = mapping.get(key)
    if col:
        record[col] = val


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_college_stats()
