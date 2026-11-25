"""
What it does: Runs generation, judging, and aggregation sequentially for C3 through C7.
Why it exists: Completes the full benchmark ladder across all 7 configs and 3 documents.
What breaks without it: We cannot compare the full ladder or determine the winning configuration.
Failure stage: evaluation.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from src.run_benchmark import run_aggregate, run_generate, run_judge

ROOT = Path(__file__).resolve().parents[1]
REMAINING_CONFIGS = ["C3", "C4", "C5", "C6", "C7"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_benchmarks")


def main() -> None:
    total_start = time.perf_counter()
    logger.info("Starting automated benchmark run for configs: %s", REMAINING_CONFIGS)

    for cfg in REMAINING_CONFIGS:
        cfg_start = time.perf_counter()
        logger.info("\n" + "=" * 70)
        logger.info(">>> BEGIN CONFIG %s <<<", cfg)
        logger.info("=" * 70)

        # Stage 1: Generate answers
        logger.info("[%s] 1/3 Generating answers...", cfg)
        run_generate(cfg, "all", force=False, limit=None, calls_per_minute=6.0)

        # Stage 2: Judge answers
        logger.info("[%s] 2/3 Judging answers...", cfg)
        run_judge(cfg, "all", force=False, limit=None)

        # Stage 3: Aggregate into results.json
        logger.info("[%s] 3/3 Aggregating results...", cfg)
        run_aggregate(cfg, "all")

        elapsed_min = (time.perf_counter() - cfg_start) / 60.0
        logger.info("[%s] Completed in %.1f minutes", cfg, elapsed_min)

    total_min = (time.perf_counter() - total_start) / 60.0
    logger.info("\n" + "=" * 70)
    logger.info("ALL CONFIGS C3-C7 COMPLETED in %.1f minutes!", total_min)
    logger.info("=" * 70)

    # Print final summary of results.json
    results_path = ROOT / "results" / "results.json"
    if results_path.is_file():
        data = json.loads(results_path.read_text(encoding="utf-8"))
        logger.info("Final results.json summary:")
        logger.info("Configs evaluated: %s", [c["config_id"] for c in data.get("configs", [])])
        logger.info("Total result rows: %d (expected 21)", len(data.get("results", [])))


if __name__ == "__main__":
    main()
