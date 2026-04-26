"""
Ingest NFL Combine results from nflreadpy.

Pulls combine data for all years, maps to our schema, and upserts
into the `prospects` and `combine_results` tables.
"""

import logging
import re

import pandas as pd

from src.utils.config import POSITION_GROUP_MAP, START_YEAR, END_YEAR
from src.utils.db import get_db_connection, upsert_prospects, upsert_combine_results

logger = logging.getLogger(__name__)


def generate_player_id(name: str, school: str | None, draft_year: int | None) -> str:
    """
    Generate a deterministic player ID from name + school + year.

    Normalizes to lowercase, strips non-alphanumeric chars, joins with underscores.
    """
    parts: list[str] = []
    for part in [name, school, str(draft_year) if draft_year else None]:
        if part:
            cleaned = re.sub(r"[^a-z0-9]", "", part.lower().strip())
            parts.append(cleaned)
    return "_".join(parts) if parts else "unknown"


def ingest_combine() -> int:
    """
    Pull NFL Combine data via nflreadpy and store in the database.

    Returns:
        Number of combine records upserted.
    """
    logger.info("Starting NFL Combine data ingestion...")

    try:
        import nflreadpy as nfl
    except ImportError:
        logger.error(
            "nflreadpy not installed. Install with: pip install nflreadpy"
        )
        return 0

    # Load combine data (returns Polars DataFrame)
    logger.info("Loading combine data from nflverse...")
    combine_raw = nfl.load_combine()

    # Convert Polars -> Pandas
    if hasattr(combine_raw, "to_pandas"):
        combine_df = combine_raw.to_pandas()
    else:
        combine_df = pd.DataFrame(combine_raw)

    logger.info("Raw combine records loaded: %d", len(combine_df))

    # Debug: log column names
    logger.debug("Combine columns: %s", list(combine_df.columns))

    # Filter to our year range
    if "season" in combine_df.columns:
        year_col = "season"
    elif "draft_year" in combine_df.columns:
        year_col = "draft_year"
    else:
        # Try to find any year-like column
        year_cols = [c for c in combine_df.columns if "year" in c.lower()]
        year_col = year_cols[0] if year_cols else None

    if year_col:
        combine_df[year_col] = pd.to_numeric(combine_df[year_col], errors="coerce")
        combine_df = combine_df[
            (combine_df[year_col] >= START_YEAR) &
            (combine_df[year_col] <= END_YEAR)
        ].copy()
        logger.info("Filtered to %d-%d: %d records", START_YEAR, END_YEAR, len(combine_df))
    else:
        logger.warning("No year column found in combine data. Using all records.")

    if combine_df.empty:
        logger.warning("No combine data after filtering.")
        return 0

    # ── Map columns to our schema ──────────────────────────────────────

    # Detect column names (nflverse uses various naming conventions)
    col_map = _detect_combine_columns(combine_df)

    # Generate player IDs
    combine_df["player_id"] = combine_df.apply(
        lambda row: generate_player_id(
            str(row.get(col_map.get("name", ""), "")),
            str(row.get(col_map.get("school", ""), "")) if pd.notna(row.get(col_map.get("school", ""))) else None,
            row.get(col_map.get("draft_year", ""))
        ),
        axis=1,
    )

    # Build prospects DataFrame
    prospects_df = pd.DataFrame({
        "player_id": combine_df["player_id"],
        "name": combine_df.get(col_map.get("name", ""), pd.Series(dtype="str")),
        "school": combine_df.get(col_map.get("school", ""), pd.Series(dtype="str")),
        "position": combine_df.get(col_map.get("position", ""), pd.Series(dtype="str")),
        "height_inches": _parse_height(combine_df, col_map),
        "weight_lbs": pd.to_numeric(
            combine_df.get(col_map.get("weight", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "draft_year": pd.to_numeric(
            combine_df.get(col_map.get("draft_year", ""), pd.Series(dtype="int")),
            errors="coerce"
        ),
    })

    # Map position groups
    prospects_df["position_group"] = prospects_df["position"].map(
        lambda p: POSITION_GROUP_MAP.get(str(p).strip().upper(), None) if pd.notna(p) else None
    )

    # Build combine results DataFrame
    combine_results_df = pd.DataFrame({
        "player_id": combine_df["player_id"],
        "forty_yard": pd.to_numeric(
            combine_df.get(col_map.get("forty", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "bench_press": pd.to_numeric(
            combine_df.get(col_map.get("bench", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "vertical_jump": pd.to_numeric(
            combine_df.get(col_map.get("vertical", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "broad_jump": pd.to_numeric(
            combine_df.get(col_map.get("broad_jump", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "three_cone": pd.to_numeric(
            combine_df.get(col_map.get("three_cone", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
        "shuttle": pd.to_numeric(
            combine_df.get(col_map.get("shuttle", ""), pd.Series(dtype="float")),
            errors="coerce"
        ),
    })

    # Log missing data summary
    for metric in ["forty_yard", "bench_press", "vertical_jump", "broad_jump",
                   "three_cone", "shuttle"]:
        missing = combine_results_df[metric].isna().sum()
        total = len(combine_results_df)
        if missing > 0:
            logger.info(
                "  %s: %d/%d missing (%.1f%%)",
                metric, missing, total, 100 * missing / total
            )

    # ── Upsert to database ────────────────────────────────────────────

    with get_db_connection() as conn:
        n_prospects = upsert_prospects(conn, prospects_df)
        n_combine = upsert_combine_results(conn, combine_results_df)

    logger.info(
        "Combine ingestion complete: %d prospects, %d combine records",
        n_prospects, n_combine
    )
    return n_combine


# =============================================================================
# Helpers
# =============================================================================

def _detect_combine_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Auto-detect column name mappings from the raw combine DataFrame.

    nflverse column names can vary; this handles common variants.
    """
    cols = {c.lower(): c for c in df.columns}
    mapping: dict[str, str] = {}

    # Name
    for candidate in ["player_name", "name", "player", "full_name"]:
        if candidate in cols:
            mapping["name"] = cols[candidate]
            break

    # School / College
    for candidate in ["school", "college", "college_name"]:
        if candidate in cols:
            mapping["school"] = cols[candidate]
            break

    # Position
    for candidate in ["pos", "position", "position_name"]:
        if candidate in cols:
            mapping["position"] = cols[candidate]
            break

    # Draft year
    for candidate in ["season", "draft_year", "year", "draft_season"]:
        if candidate in cols:
            mapping["draft_year"] = cols[candidate]
            break

    # Height
    for candidate in ["ht", "height", "height_inches"]:
        if candidate in cols:
            mapping["height"] = cols[candidate]
            break

    # Weight
    for candidate in ["wt", "weight", "weight_lbs"]:
        if candidate in cols:
            mapping["weight"] = cols[candidate]
            break

    # 40-yard dash
    for candidate in ["forty", "forty_yard", "40yd", "sprint_40yd"]:
        if candidate in cols:
            mapping["forty"] = cols[candidate]
            break

    # Bench press
    for candidate in ["bench", "bench_press", "bench_reps"]:
        if candidate in cols:
            mapping["bench"] = cols[candidate]
            break

    # Vertical jump
    for candidate in ["vertical", "vertical_jump", "vert"]:
        if candidate in cols:
            mapping["vertical"] = cols[candidate]
            break

    # Broad jump
    for candidate in ["broad_jump", "broad", "broad_jump_in"]:
        if candidate in cols:
            mapping["broad_jump"] = cols[candidate]
            break

    # 3-cone drill
    for candidate in ["three_cone", "cone", "3cone", "three_cone_drill"]:
        if candidate in cols:
            mapping["three_cone"] = cols[candidate]
            break

    # Shuttle
    for candidate in ["shuttle", "short_shuttle", "shuttle_time"]:
        if candidate in cols:
            mapping["shuttle"] = cols[candidate]
            break

    logger.debug("Column mapping: %s", mapping)
    return mapping


def _parse_height(df: pd.DataFrame, col_map: dict[str, str]) -> pd.Series:
    """
    Parse height into inches. Handles formats like:
    - Already numeric (inches)
    - '6-2' or '6\'2"' format → 74 inches
    - Feet-inches string
    """
    col = col_map.get("height", "")
    if not col or col not in df.columns:
        return pd.Series([None] * len(df), dtype="float64")

    raw = df[col]

    def to_inches(val: object) -> float | None:
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            # If already a reasonable inch value
            if val > 12:
                return float(val)
            # Likely feet, convert
            return float(val) * 12
        s = str(val).strip()
        # Try "6-2" or "6'2" format
        match = re.match(r"(\d+)['\-\s](\d+)", s)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            return float(feet * 12 + inches)
        # Try pure numeric
        try:
            v = float(s)
            return v if v > 12 else v * 12
        except ValueError:
            return None

    return raw.apply(to_inches)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_combine()
