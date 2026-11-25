"""
What it does: Generates a blind 20-question hand review sheet and empty scoring CSV for Step 9.
Why it exists: Lets the human score 20 model answers without seeing the LLM judge's verdicts.
What breaks without it: Judge agreement cannot be measured without bias.
Failure stage: evaluation.
"""

from __future__ import annotations

import csv
import glob
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "data" / "golden_set.csv"
RUNS_DIR = ROOT / "results" / "runs"
REVIEW_SHEET_PATH = ROOT / "results" / "hand_review_sheet.csv"
HAND_SCORES_PATH = ROOT / "results" / "hand_scores.csv"
SELECTION_PATH = ROOT / "results" / "hand_sample_selection.json"

SEED = 42
DOC_TARGETS = {"annual_report": 7, "fund_doc": 7, "ghg_scope3": 6}
CONFIGS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]


def load_golden() -> dict[str, dict[str, str]]:
    with GOLDEN_PATH.open(newline="", encoding="utf-8-sig") as handle:
        return {
            row["qid"].strip(): row
            for row in csv.DictReader(handle)
            if row.get("qtype", "").strip() != "unanswerable"
        }


def load_pool(golden: dict[str, dict[str, str]]) -> list[dict]:
    answers: dict[tuple[str, str], str] = {}
    for path in sorted(RUNS_DIR.glob("*__answers.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            answers[(str(row["qid"]), str(row["config_id"]))] = str(row["answer"])

    pool: list[dict] = []
    for path in sorted(RUNS_DIR.glob("*__judged.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("qtype") == "unanswerable" or row.get("judge_error"):
                continue
            corr = row.get("correctness")
            if corr is None:
                continue
            qid = str(row["qid"])
            cid = str(row["config_id"])
            if qid not in golden or (qid, cid) not in answers:
                continue
            g = golden[qid]
            pool.append(
                {
                    "qid": qid,
                    "config_id": cid,
                    "doc_id": g["doc_id"].strip(),
                    "qtype": g["qtype"].strip(),
                    "question": g["question"].strip(),
                    "gold_answer": g["gold_answer"].strip(),
                    "supporting_text": g["supporting_text"].strip(),
                    "model_answer": answers[(qid, cid)].strip(),
                    "_judge_below_1": float(corr) < 1.0,
                }
            )
    return pool


def select_sample(pool: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    candidates = list(pool)
    rng.shuffle(candidates)

    selected: list[dict] = []
    used_qids: set[str] = set()
    doc_counts: Counter[str] = Counter()
    cfg_counts: Counter[str] = Counter()
    qtype_counts: Counter[str] = Counter()

    def pick_from(subset: list[dict], limit_total: int) -> None:
        while len(selected) < limit_total:
            best = None
            best_score = (999, 999)
            for item in subset:
                if item["qid"] in used_qids:
                    continue
                if doc_counts[item["doc_id"]] >= DOC_TARGETS[item["doc_id"]]:
                    continue
                score = (cfg_counts[item["config_id"]], qtype_counts[item["qtype"]])
                if score < best_score:
                    best_score = score
                    best = item
            if best is None:
                break
            selected.append(best)
            used_qids.add(best["qid"])
            doc_counts[best["doc_id"]] += 1
            cfg_counts[best["config_id"]] += 1
            qtype_counts[best["qtype"]] += 1

    # First ensure at least 5 items where judge scored < 1.0 (spread across docs)
    below_1 = [item for item in candidates if item["_judge_below_1"]]
    pick_from(below_1, 6)

    # Fill remaining slots up to 20 from the full pool
    pick_from(candidates, 20)

    # Shuffle final list so below-1 items are mixed randomly
    rng.shuffle(selected)
    return selected


def main() -> None:
    golden = load_golden()
    pool = load_pool(golden)
    selected = select_sample(pool, SEED)

    if len(selected) != 20:
        raise SystemExit(f"Expected 20 items, got {len(selected)}")

    below_1_count = sum(1 for item in selected if item["_judge_below_1"])
    if below_1_count < 4:
        raise SystemExit(f"Expected >= 4 items with judge < 1, got {below_1_count}")

    # 1. Write results/hand_review_sheet.csv
    REVIEW_SHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_SHEET_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["qid", "config_id", "question", "gold_answer", "supporting_text", "model_answer"],
        )
        writer.writeheader()
        for item in selected:
            writer.writerow(
                {
                    "qid": item["qid"],
                    "config_id": item["config_id"],
                    "question": item["question"],
                    "gold_answer": item["gold_answer"],
                    "supporting_text": item["supporting_text"],
                    "model_answer": item["model_answer"],
                }
            )

    # 2. Write results/hand_scores.csv
    with HAND_SCORES_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["qid", "config_id", "my_score", "note"])
        writer.writeheader()
        for item in selected:
            writer.writerow(
                {
                    "qid": item["qid"],
                    "config_id": item["config_id"],
                    "my_score": "",
                    "note": "",
                }
            )

    # 3. Write results/hand_sample_selection.json (no judge info stored)
    audit = {
        "seed": SEED,
        "count": len(selected),
        "pairs": [{"qid": item["qid"], "config_id": item["config_id"]} for item in selected],
    }
    SELECTION_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    # Print blind summary only
    print(f"Generated {len(selected)} blind review items (seed={SEED}).")
    print("Per document:", dict(Counter(item["doc_id"] for item in selected)))
    print("Per config:  ", dict(sorted(Counter(item["config_id"] for item in selected).items())))
    print("Per qtype:   ", dict(Counter(item["qtype"] for item in selected)))
    print(f"Includes >= 4 judge<1 items: YES ({below_1_count} included, identities hidden)")
    print(f"Created: {REVIEW_SHEET_PATH.relative_to(ROOT)}")
    print(f"Created: {HAND_SCORES_PATH.relative_to(ROOT)}")
    print(f"Created: {SELECTION_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
