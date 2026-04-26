"""
Orchestrator for the full data ingestion pipeline.

Run with: python -m src.ingestion.run_all

Executes all ingestion steps in order:
1. Initialize database schema
2. NFL Combine results (nflreadpy)
3. Draft history (nflreadpy)
4. NFL performance stats (nflreadpy)
5. College production stats (CFBD API)

Each step is idempotent — re-running upserts rather than duplicates.
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from src.utils.config import LOG_FORMAT, LOG_DATE_FORMAT
from src.utils.db import init_db, get_table_counts


def main() -> None:
    """Run the complete data ingestion pipeline."""
    # ── Parse arguments ───────────────────────────────────────────────

    parser = argparse.ArgumentParser(
        description="NFL Draft Intelligence — Data Ingestion Pipeline"
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        choices=["combine", "draft", "nfl", "college"],
        default=[],
        help="Steps to skip (e.g., --skip college)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # ── Configure logging ─────────────────────────────────────────────

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    logger = logging.getLogger("ingestion")

    # ── Header ────────────────────────────────────────────────────────

    logger.info("=" * 70)
    logger.info("NFL DRAFT INTELLIGENCE — DATA INGESTION PIPELINE")
    logger.info("=" * 70)
    logger.info("Started at: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if args.skip:
        logger.info("Skipping steps: %s", args.skip)
    logger.info("-" * 70)

    pipeline_start = time.time()
    results: dict[str, dict] = {}

    # ── Step 0: Initialize database ───────────────────────────────────

    logger.info("Step 0: Initializing database schema...")
    step_start = time.time()
    init_db()
    results["init_db"] = {"time": time.time() - step_start, "records": 0}

    # ── Step 1: Combine data ──────────────────────────────────────────

    if "combine" not in args.skip:
        logger.info("-" * 70)
        logger.info("Step 1: Ingesting NFL Combine results...")
        step_start = time.time()
        try:
            from src.ingestion.combine import ingest_combine
            n = ingest_combine()
            results["combine"] = {"time": time.time() - step_start, "records": n}
        except Exception as e:
            logger.error("Combine ingestion FAILED: %s", e, exc_info=True)
            results["combine"] = {"time": time.time() - step_start, "records": 0, "error": str(e)}
    else:
        logger.info("Step 1: SKIPPED (combine)")

    # ── Step 2: Draft history ─────────────────────────────────────────

    if "draft" not in args.skip:
        logger.info("-" * 70)
        logger.info("Step 2: Ingesting draft history...")
        step_start = time.time()
        try:
            from src.ingestion.draft_history import ingest_draft_history
            n = ingest_draft_history()
            results["draft"] = {"time": time.time() - step_start, "records": n}
        except Exception as e:
            logger.error("Draft history ingestion FAILED: %s", e, exc_info=True)
            results["draft"] = {"time": time.time() - step_start, "records": 0, "error": str(e)}
    else:
        logger.info("Step 2: SKIPPED (draft)")

    # ── Step 3: NFL performance ───────────────────────────────────────

    if "nfl" not in args.skip:
        logger.info("-" * 70)
        logger.info("Step 3: Ingesting NFL performance stats...")
        step_start = time.time()
        try:
            from src.ingestion.nfl_performance import ingest_nfl_performance
            n = ingest_nfl_performance()
            results["nfl"] = {"time": time.time() - step_start, "records": n}
        except Exception as e:
            logger.error("NFL performance ingestion FAILED: %s", e, exc_info=True)
            results["nfl"] = {"time": time.time() - step_start, "records": 0, "error": str(e)}
    else:
        logger.info("Step 3: SKIPPED (nfl)")

    # ── Step 4: College stats ─────────────────────────────────────────

    if "college" not in args.skip:
        logger.info("-" * 70)
        logger.info("Step 4: Ingesting college production stats...")
        step_start = time.time()
        try:
            from src.ingestion.college_stats import ingest_college_stats
            n = ingest_college_stats()
            results["college"] = {"time": time.time() - step_start, "records": n}
        except Exception as e:
            logger.error("College stats ingestion FAILED: %s", e, exc_info=True)
            results["college"] = {"time": time.time() - step_start, "records": 0, "error": str(e)}
    else:
        logger.info("Step 4: SKIPPED (college)")

    # ── Summary ───────────────────────────────────────────────────────

    total_time = time.time() - pipeline_start

    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)

    for step_name, info in results.items():
        status = "✓" if "error" not in info else "✗"
        logger.info(
            "  %s %s: %d records in %.1fs%s",
            status,
            step_name,
            info["records"],
            info["time"],
            f" — ERROR: {info['error']}" if "error" in info else "",
        )

    logger.info("-" * 70)
    logger.info("Total time: %.1fs", total_time)

    # Database table counts
    try:
        counts = get_table_counts()
        logger.info("-" * 70)
        logger.info("DATABASE TABLE COUNTS:")
        for table, count in counts.items():
            logger.info("  %-20s %d rows", table, count)
    except Exception as e:
        logger.warning("Could not read table counts: %s", e)

    logger.info("=" * 70)

    # Exit with error if any step failed
    if any("error" in info for info in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
