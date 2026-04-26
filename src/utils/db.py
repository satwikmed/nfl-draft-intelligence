"""
SQLite database manager for the NFL Draft Intelligence System.

Provides:
- Schema creation (all 7 tables)
- Context-managed connections with auto-commit/rollback
- Upsert helpers for idempotent data loading
- Query utilities
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from src.utils.config import DB_PATH

logger = logging.getLogger(__name__)

# =============================================================================
# Schema DDL
# =============================================================================

SCHEMA_SQL: str = """
-- Prospects: one row per player-draft-year
CREATE TABLE IF NOT EXISTS prospects (
    player_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    school          TEXT,
    position        TEXT,
    position_group  TEXT,
    height_inches   REAL,
    weight_lbs      REAL,
    draft_year      INTEGER
);

-- Combine results: athletic testing metrics
CREATE TABLE IF NOT EXISTS combine_results (
    player_id       TEXT PRIMARY KEY,
    forty_yard      REAL,
    bench_press     INTEGER,
    vertical_jump   REAL,
    broad_jump      REAL,
    three_cone      REAL,
    shuttle         REAL,
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- College stats: season-level production
CREATE TABLE IF NOT EXISTS college_stats (
    player_id           TEXT NOT NULL,
    season              INTEGER NOT NULL,
    games               INTEGER,
    passing_yards       REAL,
    passing_tds         INTEGER,
    interceptions_thrown INTEGER,
    completions         INTEGER,
    pass_attempts       INTEGER,
    rushing_yards       REAL,
    rushing_tds         INTEGER,
    rush_attempts       INTEGER,
    receiving_yards     REAL,
    receiving_tds       INTEGER,
    receptions          INTEGER,
    tackles             REAL,
    sacks               REAL,
    interceptions       INTEGER,
    passes_defended     INTEGER,
    forced_fumbles      INTEGER,
    fumble_recoveries   INTEGER,
    PRIMARY KEY (player_id, season),
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- Draft picks: actual draft outcome
CREATE TABLE IF NOT EXISTS draft_picks (
    player_id   TEXT PRIMARY KEY,
    round       INTEGER,
    pick        INTEGER,
    team        TEXT,
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- NFL performance: post-draft stats by season
CREATE TABLE IF NOT EXISTS nfl_performance (
    player_id           TEXT NOT NULL,
    season              INTEGER NOT NULL,
    games_played        INTEGER,
    games_started       INTEGER,
    passing_yards       REAL,
    passing_tds         INTEGER,
    interceptions_thrown INTEGER,
    rushing_yards       REAL,
    rushing_tds         INTEGER,
    receiving_yards     REAL,
    receiving_tds       INTEGER,
    receptions          INTEGER,
    tackles             REAL,
    sacks               REAL,
    interceptions       INTEGER,
    PRIMARY KEY (player_id, season),
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- Features: computed feature vectors (EAV format)
CREATE TABLE IF NOT EXISTS features (
    player_id       TEXT NOT NULL,
    feature_name    TEXT NOT NULL,
    feature_value   REAL,
    PRIMARY KEY (player_id, feature_name),
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- Predictions: model outputs
CREATE TABLE IF NOT EXISTS predictions (
    player_id               TEXT PRIMARY KEY,
    pro_readiness_score     REAL,
    predicted_career_length REAL,
    comp_1_id               TEXT,
    comp_1_similarity       REAL,
    comp_2_id               TEXT,
    comp_2_similarity       REAL,
    comp_3_id               TEXT,
    comp_3_similarity       REAL,
    FOREIGN KEY (player_id) REFERENCES prospects(player_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prospects_position_group ON prospects(position_group);
CREATE INDEX IF NOT EXISTS idx_prospects_draft_year ON prospects(draft_year);
CREATE INDEX IF NOT EXISTS idx_college_stats_player ON college_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_nfl_performance_player ON nfl_performance(player_id);
CREATE INDEX IF NOT EXISTS idx_features_player ON features(player_id);
"""


# =============================================================================
# Database connection manager
# =============================================================================

@contextmanager
def get_db_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields a SQLite connection.

    Commits on success, rolls back on exception, always closes.

    Args:
        db_path: Override path to database file. Defaults to config DB_PATH.

    Yields:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """
    Create all tables and indexes if they don't exist.

    Safe to call multiple times (idempotent).

    Args:
        db_path: Override path to database file.
    """
    with get_db_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Database initialized at %s", db_path or DB_PATH)


# =============================================================================
# Upsert helpers
# =============================================================================

def upsert_prospects(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Upsert prospect records. Expects columns matching the prospects table.

    Returns the number of rows upserted.
    """
    required = ["player_id", "name"]
    _validate_columns(df, required, "prospects")

    cols = ["player_id", "name", "school", "position", "position_group",
            "height_inches", "weight_lbs", "draft_year"]
    return _upsert(conn, "prospects", df, cols)


def upsert_combine_results(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert combine results. Expects player_id + combine metric columns."""
    cols = ["player_id", "forty_yard", "bench_press", "vertical_jump",
            "broad_jump", "three_cone", "shuttle"]
    return _upsert(conn, "combine_results", df, cols)


def upsert_draft_picks(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert draft pick records."""
    cols = ["player_id", "round", "pick", "team"]
    return _upsert(conn, "draft_picks", df, cols)


def upsert_college_stats(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert college stats. PK is (player_id, season)."""
    cols = ["player_id", "season", "games", "passing_yards", "passing_tds",
            "interceptions_thrown", "completions", "pass_attempts",
            "rushing_yards", "rushing_tds", "rush_attempts",
            "receiving_yards", "receiving_tds", "receptions",
            "tackles", "sacks", "interceptions", "passes_defended",
            "forced_fumbles", "fumble_recoveries"]
    return _upsert(conn, "college_stats", df, cols)


def upsert_nfl_performance(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert NFL performance records. PK is (player_id, season)."""
    cols = ["player_id", "season", "games_played", "games_started",
            "passing_yards", "passing_tds", "interceptions_thrown",
            "rushing_yards", "rushing_tds", "receiving_yards",
            "receiving_tds", "receptions", "tackles", "sacks",
            "interceptions"]
    return _upsert(conn, "nfl_performance", df, cols)


def upsert_features(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert feature values. PK is (player_id, feature_name)."""
    cols = ["player_id", "feature_name", "feature_value"]
    return _upsert(conn, "features", df, cols)


def upsert_predictions(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Upsert model predictions."""
    cols = ["player_id", "pro_readiness_score", "predicted_career_length",
            "comp_1_id", "comp_1_similarity", "comp_2_id",
            "comp_2_similarity", "comp_3_id", "comp_3_similarity"]
    return _upsert(conn, "predictions", df, cols)


# =============================================================================
# Query helpers
# =============================================================================

def query_df(sql: str, params: tuple[Any, ...] | None = None,
             db_path: Path | None = None) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a DataFrame.

    Args:
        sql: SQL query string.
        params: Optional query parameters.
        db_path: Override database path.

    Returns:
        pd.DataFrame with query results.
    """
    with get_db_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_table_counts(db_path: Path | None = None) -> dict[str, int]:
    """Return row counts for all tables."""
    tables = ["prospects", "combine_results", "college_stats",
              "draft_picks", "nfl_performance", "features", "predictions"]
    counts: dict[str, int] = {}
    with get_db_connection(db_path) as conn:
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
    return counts


# =============================================================================
# Internal helpers
# =============================================================================

def _upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame,
            columns: list[str]) -> int:
    """
    Generic INSERT OR REPLACE for a table.

    Only includes columns that exist in both the DataFrame and the column list.
    """
    # Filter to columns that exist in the DataFrame
    available_cols = [c for c in columns if c in df.columns]
    if not available_cols:
        logger.warning("No matching columns for table %s. Skipping.", table)
        return 0

    placeholders = ", ".join(["?"] * len(available_cols))
    col_names = ", ".join(available_cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

    rows = df[available_cols].values.tolist()
    # Convert numpy/pandas types to native Python types
    clean_rows = []
    for row in rows:
        clean_row = []
        for val in row:
            if pd.isna(val):
                clean_row.append(None)
            elif hasattr(val, "item"):
                clean_row.append(val.item())
            else:
                clean_row.append(val)
        clean_rows.append(tuple(clean_row))

    conn.executemany(sql, clean_rows)
    logger.info("Upserted %d rows into %s", len(rows), table)
    return len(rows)


def _validate_columns(df: pd.DataFrame, required: list[str], table: str) -> None:
    """Raise ValueError if required columns are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns for {table}: {missing}. "
            f"Available: {list(df.columns)}"
        )
