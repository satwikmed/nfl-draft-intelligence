"""
Configuration constants for the NFL Draft Intelligence System.

Centralizes paths, year ranges, position mappings, and other
settings used across all modules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_RAW_DIR: Path = DATA_DIR / "raw"
DATA_PROCESSED_DIR: Path = DATA_DIR / "processed"
DB_PATH: Path = DATA_DIR / "nfl_draft.db"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
DATA_RAW_DIR.mkdir(exist_ok=True)
DATA_PROCESSED_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------
CFBD_API_KEY: str = os.getenv("CFBD_API_KEY", "")

# ---------------------------------------------------------------------------
# Year ranges
# ---------------------------------------------------------------------------
START_YEAR: int = 2000
END_YEAR: int = 2025
ALL_YEARS: list[int] = list(range(START_YEAR, END_YEAR + 1))

# Training / validation / prediction splits
TRAIN_END_YEAR: int = 2021
VAL_YEARS: list[int] = [2022, 2023]
PREDICT_YEARS: list[int] = [2024, 2025]
TRAIN_YEARS: list[int] = list(range(START_YEAR, TRAIN_END_YEAR + 1))

# ---------------------------------------------------------------------------
# Position mappings
# ---------------------------------------------------------------------------
# Map raw positions → position groups used for modeling
POSITION_GROUP_MAP: dict[str, str] = {
    # Quarterbacks
    "QB": "QB",
    # Running Backs
    "RB": "RB", "FB": "RB", "HB": "RB",
    # Wide Receivers
    "WR": "WR",
    # Tight Ends
    "TE": "TE",
    # Offensive Line
    "OT": "OL", "OG": "OL", "C": "OL", "OL": "OL", "G": "OL", "T": "OL",
    # Defensive Line
    "DE": "DL", "DT": "DL", "DL": "DL", "NT": "DL",
    # Linebackers
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    # Defensive Backs
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB", "SAF": "DB",
    # Special Teams (mapped but typically excluded from models)
    "K": "K", "P": "P", "LS": "LS",
}

MODELED_POSITION_GROUPS: list[str] = [
    "QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"
]

# ---------------------------------------------------------------------------
# Success thresholds for Pro Readiness labeling (Layer 3)
# "Success" = meeting threshold within first 3 NFL seasons
# Calibrated to produce ~35-40% success rate historically
# ---------------------------------------------------------------------------
SUCCESS_THRESHOLDS: dict[str, dict[str, float]] = {
    "QB": {"min_games_played": 10, "min_passing_yards": 2000},
    "RB": {"min_games_played": 10, "min_rushing_yards": 400},
    "WR": {"min_games_played": 10, "min_receiving_yards": 400},
    "TE": {"min_games_played": 10, "min_receiving_yards": 200},
    "OL": {"min_games_played": 12},
    "DL": {"min_games_played": 10, "min_sacks": 2.0},
    "LB": {"min_games_played": 10, "min_tackles": 30},
    "DB": {"min_games_played": 10, "min_tackles": 20},
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
