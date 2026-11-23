"""
What it does: Runs retrieval for C2 through C7 and prints the retrieval comparison table across C1-C7.
Why it exists: Compares hit@5, MRR, latency and stage failures before any generation is run.
What breaks without it: We cannot evaluate whether retrieval upgrades actually improve context quality.
Failure stage: retrieval.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from pathlib import Path
from typing import Any

from src.evaluate import summarise
from src.run_benchmark import DOC_FILES, retrieval_path, run_retrieve

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("compare_retrieval")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_all_retrievals() -> None:
    for cfg in ["C2", "C3", "C4", "C5", "C6", "C7"]:
        logger.info("\n" + "=" * 60)
        logger.info("RUNNING RETRIEVAL FOR %s", cfg)
        logger.info("=" * 60)
        run_retrieve(cfg, "all", force=True, limit=None)


def print_comparison_table() -> None:
    logger.info("\n" + "=" * 100)
    logger.info("RAGBENCH RETRIEVAL COMPARISON TABLE (C1 - C7)")
    logger.info("=" * 100)

    header = (
        f"| {'Config':<6} | {'Doc':<14} | {'Hit@5':<7} | {'Δ Hit@5':<9} | {'MRR':<7} | "
        f"{'Δ MRR':<7} | {'Ingest':<6} | {'Index':<6} | {'Retr':<6} | {'Pass':<6} | {'Median Lat (ms)':<15} |"
    )
    separator = (
        f"|{'-'*8}|{'-'*16}|{'-'*9}|{'-'*11}|{'-'*9}|{'-'*9}|{'-'*8}|{'-'*8}|{'-'*8}|{'-'*8}|{'-'*17}|"
    )
    print(header)
    print(separator)

    prev_metrics: dict[str, dict[str, float]] = {}

    for cfg in CONFIGS:
        cfg_latencies: list[float] = []
        for doc_id in DOC_FILES:
            path = retrieval_path(cfg, doc_id)
            rows = read_jsonl(path)
            summary = summarise(rows)
            hit5 = summary["hit_at_5"]
            mrr = summary["mrr"]

            prev = prev_metrics.get(doc_id)
            if prev is not None:
                d_hit = f"{hit5 - prev['hit_at_5']:+.3f}"
                d_mrr = f"{mrr - prev['mrr']:+.3f}"
            else:
                d_hit = "   -   "
                d_mrr = "   -   "

            prev_metrics[doc_id] = {"hit_at_5": hit5, "mrr": mrr}

            lats = [float(r["latency_ms"]) for r in rows if "latency_ms" in r and r.get("latency_ms") is not None]
            cfg_latencies.extend(lats)
            lat_str = f"{statistics.median(lats):.1f}" if lats else "-"

            print(
                f"| {cfg:<6} | {doc_id:<14} | {hit5:<7.3f} | {d_hit:<9} | {mrr:<7.3f} | {d_mrr:<7} | "
                f"{summary['ingestion']:<6} | {summary['indexing']:<6} | {summary['retrieval']:<6} | "
                f"{summary['passed_retrieval']:<6} | {lat_str:<15} |"
            )

    # Also compute aggregate across docs per config
    print(separator)
    print("\n### OVERALL RETRIEVAL SCORECARD PER CONFIG (Across all 54 answerable questions)")
    agg_header = f"| {'Config':<6} | {'Mean Hit@5':<12} | {'Mean MRR':<10} | {'Total Ingest':<12} | {'Total Index':<12} | {'Total Retr':<12} | {'Total Pass':<12} | {'Median Lat (ms)':<15} |"
    agg_sep = f"|{'-'*8}|{'-'*14}|{'-'*12}|{'-'*14}|{'-'*14}|{'-'*14}|{'-'*14}|{'-'*17}|"
    print(agg_header)
    print(agg_sep)

    for cfg in CONFIGS:
        tot_hit = []
        tot_mrr = []
        tot_ing = 0
        tot_ind = 0
        tot_ret = 0
        tot_pas = 0
        all_lats = []
        for doc_id in DOC_FILES:
            path = retrieval_path(cfg, doc_id)
            rows = read_jsonl(path)
            summary = summarise(rows)
            tot_hit.append(summary["hit_at_5"])
            tot_mrr.append(summary["mrr"])
            tot_ing += summary["ingestion"]
            tot_ind += summary["indexing"]
            tot_ret += summary["retrieval"]
            tot_pas += summary["passed_retrieval"]
            all_lats.extend([float(r["latency_ms"]) for r in rows if "latency_ms" in r and r.get("latency_ms") is not None])

        mean_hit = sum(tot_hit) / len(tot_hit) if tot_hit else 0.0
        mean_mrr = sum(tot_mrr) / len(tot_mrr) if tot_mrr else 0.0
        lat_str = f"{statistics.median(all_lats):.1f}" if all_lats else "-"
        print(
            f"| {cfg:<6} | {mean_hit:<12.3f} | {mean_mrr:<10.3f} | {tot_ing:<12} | {tot_ind:<12} | {tot_ret:<12} | {tot_pas:<12} | {lat_str:<15} |"
        )


if __name__ == "__main__":
    run_all_retrievals()
    print_comparison_table()
