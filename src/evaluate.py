"""
What it does: Scores whether the right passage was retrieved and which earlier stage lost it.
Why it exists: A miss needs a cause, not only a percentage.
What breaks without it: The benchmark cannot tell parsing from search.
Failure stage: evaluation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.retrieve import dense_retrieve
from src.textmatch import fuzzy_in

THRESHOLD = 90
BORDER_LOW = 80
BORDER_HIGH = 95


def supporting_parts(row: dict[str, str]) -> list[str]:
    text = row.get("supporting_text", "")
    if row.get("qtype") == "multi":
        return [part.strip() for part in text.split(" ||| ") if part.strip()]
    stripped = text.strip()
    return [stripped] if stripped else []


def _best(needle: str, haystacks: list[tuple[str, str]]) -> tuple[float, str, str]:
    best_score = 0.0
    best_label = ""
    best_text = ""
    for label, haystack in haystacks:
        _matched, score = fuzzy_in(needle, haystack, THRESHOLD)
        if score > best_score:
            best_score = score
            best_label = label
            best_text = haystack
    return best_score, best_label, best_text


def _rank_for_part(part: str, retrieved: list[dict[str, Any]]) -> int | None:
    for rank, hit in enumerate(retrieved, start=1):
        matched, _score = fuzzy_in(part, str(hit["text"]), THRESHOLD)
        if matched:
            return rank
    return None


def score_question(
    config: dict[str, Any],
    doc_id: str,
    row: dict[str, str],
    parsed_text: str,
    chunks: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    qid = row["qid"].strip()
    qtype = row["qtype"].strip()
    record: dict[str, Any] = {
        "qid": qid,
        "doc_id": doc_id,
        "config_id": config["config_id"],
        "qtype": qtype,
    }
    if qtype == "unanswerable":
        record["excluded"] = True
        return record, []
    parts = supporting_parts(row)
    retrieved = dense_retrieve(doc_id, config, row["question"])
    chunk_views = [(str(chunk["chunk_id"]), str(chunk["text"])) for chunk in chunks]
    borderlines: list[dict[str, Any]] = []
    ranks: list[int] = []
    missing_from_parsed = False
    missing_from_chunks = False
    for part in parts:
        parsed_score, _parsed_label, _parsed_text = _best(part, [("parsed", parsed_text)])
        chunk_score, chunk_label, chunk_text = _best(part, chunk_views)
        if parsed_score < THRESHOLD:
            missing_from_parsed = True
        if chunk_score < THRESHOLD:
            missing_from_chunks = True
        if BORDER_LOW <= chunk_score <= BORDER_HIGH:
            borderlines.append(
                {
                    "qid": qid,
                    "score": chunk_score,
                    "where": chunk_label,
                    "needle": part,
                    "haystack": chunk_text,
                }
            )
        rank = _rank_for_part(part, retrieved)
        if rank is None:
            ranks.append(0)
        else:
            ranks.append(rank)
    marked: list[dict[str, Any]] = []
    for hit in retrieved:
        is_correct = any(fuzzy_in(part, str(hit["text"]), THRESHOLD)[0] for part in parts)
        marked.append(
            {
                "chunk_id": hit["chunk_id"],
                "page": hit["page_start"],
                "score": round(float(hit["score"]), 4),
                "is_correct": is_correct,
            }
        )
    hit = bool(parts) and all(rank > 0 for rank in ranks)
    reciprocal = 0.0 if not hit else 1.0 / max(ranks)
    if missing_from_parsed:
        failure = "ingestion"
    elif missing_from_chunks:
        failure = "indexing"
    elif not hit:
        failure = "retrieval"
    else:
        failure = "passed_retrieval"
    record.update(
        {
            "retrieved": marked,
            "hit_at_5": hit,
            "reciprocal_rank": reciprocal,
            "failure_stage": failure,
        }
    )
    return record, borderlines


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if not row.get("excluded")]
    count = len(scored)
    hits = sum(1 for row in scored if row.get("hit_at_5"))
    mrr = sum(float(row.get("reciprocal_rank") or 0) for row in scored) / count if count else 0.0
    stages = {"ingestion": 0, "indexing": 0, "retrieval": 0, "passed_retrieval": 0}
    for row in scored:
        stage = str(row.get("failure_stage"))
        if stage in stages:
            stages[stage] += 1
    return {
        "answerable": count,
        "hit_at_5": hits / count if count else 0.0,
        "mrr": mrr,
        **stages,
    }


def attribute_failure(qtype: str, correctness: float | None, retrieval_stage: str, refused: bool) -> str | None:
    """First failing stage. A correct answer, or a correct refusal, has no failure."""
    if qtype == "unanswerable":
        if refused or correctness == 1:
            return None
        return "generation"
    if correctness is None or correctness == 1:
        return None
    if retrieval_stage == "ingestion":
        return "ingestion"
    if retrieval_stage == "indexing":
        return "indexing"
    if retrieval_stage == "retrieval":
        return "retrieval"
    return "generation"


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((percent / 100) * (len(ordered) - 1))
    index = min(max(index, 0), len(ordered) - 1)
    return float(ordered[index])


TOP_KEYS = (
    "generated_at",
    "judge_agreement",
    "fuzzy_threshold",
    "configs",
    "results",
    "winners",
    "failure_examples",
)
RESULT_KEYS = (
    "config_id",
    "doc_id",
    "hit_at_5",
    "mrr",
    "correctness",
    "faithfulness",
    "refusal_accuracy",
    "over_refusals",
    "latency_p50_ms",
    "latency_p95_ms",
    "tokens_per_query",
    "failures_by_stage",
)
STAGE_KEYS = ("ingestion", "indexing", "retrieval", "generation")


def aggregate_document(
    config_id: str,
    doc_id: str,
    retrieval: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    judged: list[dict[str, Any]],
) -> dict[str, Any]:
    by_retrieval = {str(row["qid"]): row for row in retrieval}
    by_answer = {str(row["qid"]): row for row in answers}
    scored = [row for row in judged if str(row["qid"]) in by_retrieval]
    answerable = [row for row in scored if str(row.get("qtype")) != "unanswerable"]
    unanswerable = [row for row in scored if str(row.get("qtype")) == "unanswerable"]
    hit_rows = [by_retrieval[str(row["qid"])] for row in answerable if not by_retrieval[str(row["qid"])].get("excluded")]
    hit_count = len(hit_rows)
    hits = sum(1 for row in hit_rows if row.get("hit_at_5"))
    mrr = sum(float(row.get("reciprocal_rank") or 0) for row in hit_rows) / hit_count if hit_count else 0.0
    graded = [row for row in scored if row.get("judge_error") is not True and row.get("correctness") is not None]
    correctness = sum(float(row["correctness"]) for row in graded) / len(graded) if graded else 0.0
    faithful_rows = [row for row in answerable if isinstance(row.get("faithful"), bool)]
    faithfulness = (
        sum(1 for row in faithful_rows if row["faithful"]) / len(faithful_rows) if faithful_rows else 0.0
    )
    refusal_accuracy = (
        sum(1 for row in unanswerable if float(row.get("correctness") or 0) == 1) / len(unanswerable)
        if unanswerable
        else 0.0
    )
    failures = {name: 0 for name in STAGE_KEYS}
    over_refusals = 0
    for row in scored:
        qid = str(row["qid"])
        retrieval_row = by_retrieval[qid]
        answer = by_answer.get(qid, {})
        stage = attribute_failure(
            str(row.get("qtype")),
            None if row.get("correctness") is None else float(row["correctness"]),
            str(retrieval_row.get("failure_stage") or ""),
            bool(answer.get("refused")),
        )
        if stage in failures:
            failures[stage] += 1
        if stage == "generation" and answer.get("refused") and str(row.get("qtype")) != "unanswerable":
            over_refusals += 1
    latencies = [float(by_answer[str(row["qid"])]["latency_ms"]) for row in scored if str(row["qid"]) in by_answer]
    tokens = [
        int(by_answer[str(row["qid"])]["prompt_tokens"]) + int(by_answer[str(row["qid"])]["completion_tokens"])
        for row in scored
        if str(row["qid"]) in by_answer
    ]
    return {
        "config_id": config_id,
        "doc_id": doc_id,
        "hit_at_5": hits / hit_count if hit_count else 0.0,
        "mrr": mrr,
        "correctness": correctness,
        "faithfulness": faithfulness,
        "refusal_accuracy": refusal_accuracy,
        "over_refusals": over_refusals,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "tokens_per_query": (sum(tokens) / len(tokens)) if tokens else 0.0,
        "failures_by_stage": failures,
    }


def compute_judge_agreement(
    hand_scores_path: Path,
    runs_dir: Path,
) -> tuple[dict[str, int] | None, list[dict[str, Any]]]:
    if not hand_scores_path.is_file():
        return None, []
    judged: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(runs_dir.glob("*__judged.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                judged[(str(row["qid"]), str(row["config_id"]))] = row

    n = 0
    agreed = 0
    disagreements: list[dict[str, Any]] = []
    with hand_scores_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            raw_score = (row.get("my_score") or "").strip()
            if not raw_score:
                continue
            qid = row["qid"].strip()
            cid = row["config_id"].strip()
            my_score = float(raw_score)
            judge_row = judged.get((qid, cid))
            if not judge_row or judge_row.get("judge_error") or judge_row.get("correctness") is None:
                continue
            judge_score = float(judge_row["correctness"])
            n += 1
            if my_score == judge_score:
                agreed += 1
            else:
                disagreements.append(
                    {
                        "qid": qid,
                        "config_id": cid,
                        "my_score": my_score,
                        "judge_score": judge_score,
                        "judge_reason": str(judge_row.get("reason") or ""),
                        "my_note": (row.get("note") or "").strip(),
                    }
                )
    if n == 0:
        return None, []
    return {"n": n, "agreed": agreed}, disagreements


def build_results(
    configs: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    generated_at: str,
    judge_agreement: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "judge_agreement": judge_agreement,
        "fuzzy_threshold": THRESHOLD,
        "configs": [
            {
                "config_id": config["config_id"],
                "stage_changed": config["stage_changed"],
                "description": config["description"],
            }
            for config in configs
        ],
        "results": documents,
        "winners": {},
        "failure_examples": [],
    }


def validate_results(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if set(payload) != set(TOP_KEYS):
        problems.append(f"top-level keys {sorted(payload)} != {list(TOP_KEYS)}")
    agreement = payload.get("judge_agreement")
    if agreement is not None:
        if not isinstance(agreement, dict) or set(agreement) != {"n", "agreed"}:
            problems.append(f"judge_agreement must be null or {{n, agreed}}, got {agreement}")
    if payload.get("winners") != {}:
        problems.append("winners must be empty until Step 10")
    if payload.get("failure_examples") != []:
        problems.append("failure_examples must be empty until Step 10")
    for item in payload.get("results", []):
        if set(item) != set(RESULT_KEYS):
            problems.append(f"result keys {sorted(item)}")
        stages = item.get("failures_by_stage", {})
        if set(stages) != set(STAGE_KEYS):
            problems.append(f"failures_by_stage keys {sorted(stages)}")
    return problems
