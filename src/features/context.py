"""
Context adjustment features.

Computes draft capital context, position value, and
conference tier adjustments for prospect evaluation.
"""

import logging
from typing import Optional

import pandas as pd

from src.utils.db import query_df

logger = logging.getLogger(__name__)

# Conference tier ratings (approximation of historical strength)
CONFERENCE_TIERS: dict[str, int] = {
    # Power conferences (Tier 1)
    "SEC": 1, "Big Ten": 1, "Big 12": 1, "ACC": 1, "Pac-12": 1,
    "Pac-10": 1, "Big East": 1,
    # Strong mid-majors (Tier 2)
    "AAC": 2, "American Athletic": 2, "Mountain West": 2,
    "Conference USA": 2, "C-USA": 2,
    # Mid-majors (Tier 3)
    "Sun Belt": 3, "MAC": 3, "Mid-American": 3,
    # FCS / Other (Tier 4)
    "Big Sky": 4, "CAA": 4, "MVFC": 4, "Missouri Valley": 4,
    "Southland": 4, "Ohio Valley": 4, "FCS": 4,
}

# Conference multipliers for production adjustment
CONFERENCE_MULTIPLIERS: dict[int, float] = {
    1: 1.0,    # Power conference - no adjustment
    2: 0.90,   # Strong mid-major - 10% discount
    3: 0.80,   # Mid-major - 20% discount
    4: 0.70,   # FCS/Other - 30% discount
}


def compute_context_features(player_ids: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Compute context adjustment features for prospects.

    Features:
    - Draft position context (round, pick, draft capital value)
    - Conference tier
    - Conference production multiplier
    - Years from draft (for career progression context)

    Returns:
        DataFrame with columns: player_id, feature_name, feature_value
    """
    logger.info("Computing context features...")

    # Load prospect + draft data
    sql = """
        SELECT p.player_id, p.name, p.position_group, p.school,
               p.draft_year, p.height_inches, p.weight_lbs,
               d.round, d.pick, d.team
        FROM prospects p
        LEFT JOIN draft_picks d ON p.player_id = d.player_id
        WHERE p.position_group IS NOT NULL
    """
    if player_ids:
        placeholders = ",".join(["?"] * len(player_ids))
        sql += f" AND p.player_id IN ({placeholders})"
        df = query_df(sql, tuple(player_ids))
    else:
        df = query_df(sql)

    if df.empty:
        logger.warning("No prospect data for context features.")
        return pd.DataFrame(columns=["player_id", "feature_name", "feature_value"])

    all_features: list[dict] = []

    for _, row in df.iterrows():
        pid = row["player_id"]

        # Draft capital value (based on Jimmy Johnson trade chart approximation)
        draft_round = row.get("round")
        draft_pick = row.get("pick")

        if pd.notna(draft_round):
            all_features.append({
                "player_id": pid,
                "feature_name": "draft_round",
                "feature_value": float(draft_round),
            })

        if pd.notna(draft_pick):
            all_features.append({
                "player_id": pid,
                "feature_name": "draft_pick",
                "feature_value": float(draft_pick),
            })

            # Draft capital value (higher = more valuable pick)
            capital = _draft_capital_value(int(draft_pick))
            all_features.append({
                "player_id": pid,
                "feature_name": "draft_capital_value",
                "feature_value": round(capital, 2),
            })

        # Conference tier
        school = str(row.get("school", ""))
        conf_tier = _get_conference_tier(school)
        if conf_tier:
            all_features.append({
                "player_id": pid,
                "feature_name": "conference_tier",
                "feature_value": float(conf_tier),
            })

            multiplier = CONFERENCE_MULTIPLIERS.get(conf_tier, 0.85)
            all_features.append({
                "player_id": pid,
                "feature_name": "conference_multiplier",
                "feature_value": multiplier,
            })

    result = pd.DataFrame(all_features)
    logger.info("Computed %d context features for %d players",
                len(result), df["player_id"].nunique())
    return result


def _draft_capital_value(pick: int) -> float:
    """
    Approximate draft capital value using exponential decay.

    Pick 1 ≈ 100, Pick 32 ≈ 50, Pick 64 ≈ 25, Pick 256 ≈ 2.
    """
    if pick <= 0:
        return 0.0
    return 100.0 * (0.98 ** (pick - 1))


def _get_conference_tier(school: str) -> Optional[int]:
    """
    Look up conference tier for a school.

    Uses hardcoded mappings for major schools. Returns None if unknown.
    """
    # Major school → conference mapping
    school_conferences: dict[str, str] = {
        # SEC
        "Alabama": "SEC", "Auburn": "SEC", "Florida": "SEC",
        "Georgia": "SEC", "LSU": "SEC", "Tennessee": "SEC",
        "Texas A&M": "SEC", "South Carolina": "SEC", "Kentucky": "SEC",
        "Mississippi State": "SEC", "Ole Miss": "SEC", "Missouri": "SEC",
        "Arkansas": "SEC", "Vanderbilt": "SEC", "Oklahoma": "SEC",
        "Texas": "SEC",
        # Big Ten
        "Ohio State": "Big Ten", "Michigan": "Big Ten", "Penn State": "Big Ten",
        "Wisconsin": "Big Ten", "Iowa": "Big Ten", "Minnesota": "Big Ten",
        "Nebraska": "Big Ten", "Purdue": "Big Ten", "Indiana": "Big Ten",
        "Illinois": "Big Ten", "Northwestern": "Big Ten", "Michigan State": "Big Ten",
        "Maryland": "Big Ten", "Rutgers": "Big Ten", "Oregon": "Big Ten",
        "USC": "Big Ten", "UCLA": "Big Ten", "Washington": "Big Ten",
        # Big 12
        "Baylor": "Big 12", "Iowa State": "Big 12", "Kansas": "Big 12",
        "Kansas State": "Big 12", "Oklahoma State": "Big 12",
        "TCU": "Big 12", "Texas Tech": "Big 12", "West Virginia": "Big 12",
        "BYU": "Big 12", "Cincinnati": "Big 12", "Houston": "Big 12",
        "UCF": "Big 12", "Colorado": "Big 12", "Arizona": "Big 12",
        "Arizona State": "Big 12", "Utah": "Big 12",
        # ACC
        "Clemson": "ACC", "Florida State": "ACC", "Miami": "ACC",
        "North Carolina": "ACC", "NC State": "ACC", "Virginia": "ACC",
        "Virginia Tech": "ACC", "Duke": "ACC", "Wake Forest": "ACC",
        "Pittsburgh": "ACC", "Boston College": "ACC", "Syracuse": "ACC",
        "Louisville": "ACC", "Georgia Tech": "ACC",
        "Stanford": "ACC", "California": "ACC", "SMU": "ACC",
        # Pac-12 (historical)
        "Washington State": "Pac-12", "Oregon State": "Pac-12",
        # AAC
        "Memphis": "AAC", "Tulane": "AAC", "East Carolina": "AAC",
        "Navy": "AAC", "Temple": "AAC", "Tulsa": "AAC",
        "South Florida": "AAC",
        # Mountain West
        "Boise State": "Mountain West", "San Diego State": "Mountain West",
        "Fresno State": "Mountain West", "Air Force": "Mountain West",
        "Colorado State": "Mountain West", "Wyoming": "Mountain West",
        "Nevada": "Mountain West", "UNLV": "Mountain West",
        "New Mexico": "Mountain West", "San Jose State": "Mountain West",
        "Hawaii": "Mountain West",
        # Sun Belt
        "Appalachian State": "Sun Belt", "Coastal Carolina": "Sun Belt",
        "Louisiana": "Sun Belt", "Troy": "Sun Belt",
        "Georgia Southern": "Sun Belt", "Arkansas State": "Sun Belt",
        "South Alabama": "Sun Belt",
        # MAC
        "Northern Illinois": "MAC", "Toledo": "MAC", "Western Michigan": "MAC",
        "Central Michigan": "MAC", "Eastern Michigan": "MAC",
        "Bowling Green": "MAC", "Ball State": "MAC", "Kent State": "MAC",
        "Ohio": "MAC", "Miami (OH)": "MAC", "Akron": "MAC", "Buffalo": "MAC",
        # Independents
        "Notre Dame": "ACC",  # treat as power conf
        "Army": "AAC",
        "Liberty": "C-USA",
    }

    conf = school_conferences.get(school)
    if conf:
        return CONFERENCE_TIERS.get(conf, 3)

    # Default: try to infer from school name
    return 3  # default to tier 3 (mid-major)
