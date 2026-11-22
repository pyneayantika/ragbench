"""
What it does: Command-line entry point that runs one stage for one config and one document.
Why it exists: One command must reproduce a run from the config file.
What breaks without it: Runs become one-off scripts and the numbers cannot be repeated.
Failure stage: none (reproducibility).
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import logging
import sys
import time
from pathlib import Path

from src.chunk import chunk_document, get_tokenizer, token_count
from src.config import load_config
from src.evaluate import aggregate_document, build_results, score_question, summarise, validate_results
from src.generate import CALLS_PER_MINUTE, generate_answer
from src.judge import confirm_judge_model, judge_answer, score_unanswerable
from src.index import index_document
from src.ingest import DOC_FILES, ingest_document
from src.retrieve import dense_retrieve

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "data" / "golden_set.csv"

logger = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one RAGBench stage.")
    parser.add_argument("--config", required=True, help="Config id, for example C1")
    parser.add_argument("--doc", required=True, help="annual_report, fund_doc, ghg_scope3, or all")
    parser.add_argument("--stage", required=True, help="Pipeline stage to run")
    parser.add_argument("--force", action="store_true", help="Ignore the cache and rebuild")
    parser.add_argument("--limit", type=int, default=None, help="Max questions for retrieve and generate")
    parser.add_argument("--calls-per-minute", type=float, default=CALLS_PER_MINUTE, help="Groq pace for generate")
    return parser.parse_args(argv)


def selected_docs(name: str) -> list[str]:
    if name == "all":
        return list(DOC_FILES)
    if name not in DOC_FILES:
        known = ", ".join(DOC_FILES)
        raise SystemExit(f"Unknown --doc {name}. Known: {known}, all")
    return [name]


def page_stats(pages: list[dict[str, object]]) -> tuple[int, int, int]:
    characters = 0
    empty = 0
    for page in pages:
        text = page.get("text")
        content = text if isinstance(text, str) else ""
        characters += len(content)
        if not content.strip():
            empty += 1
    return len(pages), characters, empty


def chunk_report(config_id: str, doc_id: str, config: dict, chunks: list[dict], cache_hit: bool) -> None:
    tokenizer = get_tokenizer(str(config["embedding_model"]))
    lengths = [token_count(tokenizer, str(chunk["embed_text"])) for chunk in chunks]
    over = sum(1 for length in lengths if length > int(config["chunking"]["max_tokens"]))
    headed = sum(1 for chunk in chunks if str(chunk.get("section_heading") or "").strip())
    share = (headed / len(chunks)) if chunks else 0.0
    mean = (sum(lengths) / len(lengths)) if lengths else 0.0
    logger.info(
        "%s  %s  %d  %d  %.1f  %d  %.2f  %d  %s",
        config_id,
        doc_id,
        len(chunks),
        min(lengths) if lengths else 0,
        mean,
        max(lengths) if lengths else 0,
        share,
        over,
        "hit" if cache_hit else "miss",
    )
    if config_id.upper() == "C3":
        for chunk in chunks[:2]:
            logger.info("sample %s %s: %s", doc_id, chunk["chunk_id"], str(chunk["text"])[:300])
    if config_id.upper() == "C7" and chunks:
        sample = chunks[0]
        logger.info("C7 text starts: %s", str(sample["text"])[:180])
        logger.info("C7 embed_text starts: %s", str(sample["embed_text"])[:180])


def run_ingest(config_id: str, doc_name: str, force: bool) -> None:
    config = load_config(config_id)
    parsing = str(config["parsing"])
    logger.info("doc_id  mode  pages  total_characters  empty_pages  seconds  cache")
    logger.info("config  doc  chunks  min  mean  max  heading_share  over_256  cache")
    for doc_id in selected_docs(doc_name):
        started = time.perf_counter()
        pages, page_hit = ingest_document(doc_id, parsing, force=False)
        elapsed = time.perf_counter() - started
        count, characters, empty = page_stats(pages)
        logger.info(
            "%s  %s  %d  %d  %d  %.2f  %s",
            doc_id,
            parsing,
            count,
            characters,
            empty,
            elapsed,
            "hit" if page_hit else "miss",
        )
        chunks, chunk_hit = chunk_document(doc_id, config, pages, force=force)
        chunk_report(config["config_id"], doc_id, config, chunks, chunk_hit)


class _MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_ram_mb() -> str:
    counters = _MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    reader = ctypes.windll.psapi.GetProcessMemoryInfo
    reader.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    reader.restype = ctypes.c_int
    ok = reader(handle, ctypes.byref(counters), counters.cb)
    if not ok:
        return "unavailable"
    return f"{counters.PeakWorkingSetSize / (1024 * 1024):.0f} MB"


def preview_questions(config: dict, doc_id: str, limit: int) -> None:
    with GOLDEN_PATH.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("doc_id") == doc_id]
    for row in rows[:limit]:
        qid = row["qid"]
        page_raw = row.get("source_page", "").strip()
        hits = dense_retrieve(doc_id, config, row["question"])
        source_page = int(page_raw) if page_raw.isdigit() else None
        found = source_page is not None and any(
            hit["page_start"] <= source_page <= hit["page_end"] for hit in hits
        )
        logger.info("%s source_page=%s in_top5=%s", qid, page_raw or "-", "yes" if found else "no")
        for rank, hit in enumerate(hits, start=1):
            snippet = " ".join(str(hit["text"]).split())[:120]
            logger.info("  %d p%s %.3f %s", rank, hit["page_start"], hit["score"], snippet)


def run_index(config_id: str, doc_name: str, force: bool, limit: int | None) -> None:
    config = load_config(config_id)
    for doc_id in selected_docs(doc_name):
        pages, _page_hit = ingest_document(doc_id, str(config["parsing"]), force=False)
        chunks, _chunk_hit = chunk_document(doc_id, config, pages, force=False)
        outcome = index_document(doc_id, config, chunks, force=force)
        logger.info(
            "%s %s model=%s chunks=%d collection=%s embed_seconds=%.2f total_seconds=%.2f chroma=%s bm25=%s",
            config["config_id"],
            doc_id,
            outcome["model"],
            outcome["count"],
            outcome["collection"],
            outcome["embed_seconds"],
            outcome["seconds"],
            "hit" if outcome["chroma_hit"] else "miss",
            "hit" if outcome["bm25_hit"] else "miss",
        )
        if limit:
            preview_questions(config, doc_id, limit)
    logger.info("peak process RAM %s", peak_ram_mb())


def retrieval_path(config_id: str, doc_id: str) -> Path:
    return ROOT / "results" / "runs" / f"{config_id}__{doc_id}__retrieval.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def golden_rows(doc_id: str) -> list[dict[str, str]]:
    with GOLDEN_PATH.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if row.get("doc_id") == doc_id]


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_retrieve(config_id: str, doc_name: str, force: bool, limit: int | None) -> None:
    config = load_config(config_id)
    if str(config["retrieval"]["mode"]) != "dense":
        raise SystemExit("The retrieve stage in this step only runs dense configs.")
    borderlines: list[dict] = []
    for doc_id in selected_docs(doc_name):
        pages, _page_hit = ingest_document(doc_id, str(config["parsing"]), force=False)
        parsed_text = "\n".join(str(page.get("text") or "") for page in pages)
        chunks, _chunk_hit = chunk_document(doc_id, config, pages, force=False)
        index_document(doc_id, config, chunks, force=False)
        path = retrieval_path(config["config_id"], doc_id)
        if force and path.is_file():
            path.unlink()
        done = {str(row.get("qid")) for row in read_jsonl(path)}
        pending = [row for row in golden_rows(doc_id) if row["qid"].strip() not in done]
        if limit is not None:
            pending = pending[:limit]
        for row in pending:
            record, found = score_question(config, doc_id, row, parsed_text, chunks)
            append_jsonl(path, record)
            borderlines.extend(found)
        summary = summarise(read_jsonl(path))
        logger.info(
            "%s %s answerable=%d hit@5=%.3f mrr=%.3f ingestion=%d indexing=%d retrieval=%d passed_retrieval=%d",
            config["config_id"],
            doc_id,
            summary["answerable"],
            summary["hit_at_5"],
            summary["mrr"],
            summary["ingestion"],
            summary["indexing"],
            summary["retrieval"],
            summary["passed_retrieval"],
        )
    borderlines.sort(key=lambda item: abs(float(item["score"]) - 90))
    logger.info("borderline matches shown=%d collected=%d", min(5, len(borderlines)), len(borderlines))
    for item in borderlines[:5]:
        haystack = " ".join(str(item["haystack"]).split())
        logger.info(
            "border qid=%s score=%.1f where=%s\nNEEDLE: %s\nHAYSTACK: %s",
            item["qid"],
            item["score"],
            item["where"],
            " ".join(str(item["needle"]).split()),
            haystack[:800],
        )
    logger.info("peak process RAM %s", peak_ram_mb())


def answers_path(config_id: str, doc_id: str) -> Path:
    return ROOT / "results" / "runs" / f"{config_id}__{doc_id}__answers.jsonl"


def run_generate(config_id: str, doc_name: str, force: bool, limit: int | None, calls_per_minute: float) -> None:
    config = load_config(config_id)
    for doc_id in selected_docs(doc_name):
        path = retrieval_path(config["config_id"], doc_id)
        if not path.is_file():
            raise SystemExit(f"Missing retrieval file {path.relative_to(ROOT)}. Run --stage retrieve first.")
        pages, _page_hit = ingest_document(doc_id, str(config["parsing"]), force=False)
        chunks, _chunk_hit = chunk_document(doc_id, config, pages, force=False)
        by_id = {str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks}
        questions = {row["qid"].strip(): row["question"] for row in golden_rows(doc_id)}
        out = answers_path(config["config_id"], doc_id)
        if force and out.is_file():
            out.unlink()
        done = {str(row.get("qid")) for row in read_jsonl(out)}
        pending = [row for row in read_jsonl(path) if str(row.get("qid")) not in done]
        if limit is not None:
            pending = pending[:limit]
        for row in pending:
            qid = str(row["qid"])
            passages: list[tuple[int, str]] = []
            for hit in row.get("retrieved") or []:
                chunk_id = str(hit["chunk_id"])
                if chunk_id not in by_id:
                    raise SystemExit(f"{qid} retrieved {chunk_id}, which is not in the chunk cache.")
                passages.append((int(hit["page"]), by_id[chunk_id]))
            result = generate_answer(questions[qid], doc_id, passages, calls_per_minute)
            result.update({"qid": qid, "doc_id": doc_id, "config_id": config["config_id"], "qtype": row.get("qtype")})
            append_jsonl(out, result)
            logger.info(
                "%s refused=%s prompt_tokens=%s completion_tokens=%s reasoning_tokens=%s latency_ms=%s",
                qid,
                result["refused"],
                result["prompt_tokens"],
                result["completion_tokens"],
                result["reasoning_tokens"],
                result["latency_ms"],
            )
            logger.info("Q: %s", questions[qid])
            logger.info("A: %s", result["answer"])
        logger.info("%s %s answers_written=%d", config["config_id"], doc_id, len(read_jsonl(out)))


def judged_path(config_id: str, doc_id: str) -> Path:
    return ROOT / "results" / "runs" / f"{config_id}__{doc_id}__judged.jsonl"


def run_judge(config_id: str, doc_name: str, force: bool, limit: int | None) -> None:
    from src.settings import JUDGE_LIMITS_SOURCE, JUDGE_MODEL, JUDGE_RPD, JUDGE_TPM, JUDGE_TPD

    config = load_config(config_id)
    docs = selected_docs(doc_name)
    planned = 0
    for doc_id in docs:
        retrieval = read_jsonl(retrieval_path(config["config_id"], doc_id))
        done = set() if force else {str(row.get("qid")) for row in read_jsonl(judged_path(config["config_id"], doc_id))}
        pending = [row for row in retrieval if str(row.get("qid")) not in done]
        if limit is not None:
            pending = pending[:limit]
        planned += sum(1 for row in pending if row.get("qtype") != "unanswerable")
    assumed_tokens = 1500
    cap = int(JUDGE_TPM * 0.75)
    logger.info(
        "Judge model %s. Limits from %s: TPM=%s, RPD=%s, TPD=%s. RPM was not supplied.",
        JUDGE_MODEL,
        JUDGE_LIMITS_SOURCE,
        JUDGE_TPM,
        JUDGE_RPD,
        JUDGE_TPD,
    )
    logger.info(
        "This run: %d judge calls. At %d tokens/call and a %d token/minute cap, about %.1f minutes.",
        planned,
        assumed_tokens,
        cap,
        planned * assumed_tokens / cap,
    )
    logger.info("A full C1 judge later is 54 calls (6 unanswerable questions are skipped). About %.1f minutes.", 54 * assumed_tokens / cap)
    confirm_judge_model()
    for doc_id in docs:
        retrieval_file = retrieval_path(config["config_id"], doc_id)
        answer_file = answers_path(config["config_id"], doc_id)
        if not retrieval_file.is_file() or not answer_file.is_file():
            raise SystemExit(f"Missing retrieval or answers for {doc_id}.")
        pages, _page_hit = ingest_document(doc_id, str(config["parsing"]), force=False)
        chunks, _chunk_hit = chunk_document(doc_id, config, pages, force=False)
        by_id = {str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks}
        golden = {row["qid"].strip(): row for row in golden_rows(doc_id)}
        answers = {str(row["qid"]): row for row in read_jsonl(answer_file)}
        out = judged_path(config["config_id"], doc_id)
        if force and out.is_file():
            out.unlink()
        done = {str(row.get("qid")) for row in read_jsonl(out)}
        pending = [row for row in read_jsonl(retrieval_file) if str(row.get("qid")) not in done]
        if limit is not None:
            pending = pending[:limit]
        for row in pending:
            qid = str(row["qid"])
            answer = answers[qid]["answer"]
            if row.get("qtype") == "unanswerable":
                record = score_unanswerable(answer)
            else:
                passages = []
                for hit in row.get("retrieved") or []:
                    passages.append(f"[{doc_id} p.{hit['page']}]\n{by_id[str(hit['chunk_id'])]}")
                record = judge_answer(
                    golden[qid]["question"],
                    golden[qid]["gold_answer"],
                    "\n\n".join(passages),
                    answer,
                )
            record.update({"qid": qid, "doc_id": doc_id, "config_id": config["config_id"], "qtype": row.get("qtype")})
            append_jsonl(out, record)
            logger.info(
                "%s correctness=%s faithful=%s judge_error=%s reason=%s",
                qid,
                record.get("correctness"),
                record.get("faithful"),
                record.get("judge_error"),
                record.get("reason"),
            )
        logger.info("%s %s judged_rows=%d", config["config_id"], doc_id, len(read_jsonl(out)))


def run_aggregate(config_id: str, doc_name: str) -> None:
    from datetime import datetime, timezone

    config = load_config(config_id)
    documents = []
    for doc_id in selected_docs(doc_name):
        judged = read_jsonl(judged_path(config["config_id"], doc_id))
        if not judged:
            continue
        documents.append(
            aggregate_document(
                config["config_id"],
                doc_id,
                read_jsonl(retrieval_path(config["config_id"], doc_id)),
                read_jsonl(answers_path(config["config_id"], doc_id)),
                judged,
            )
        )
    payload = build_results(
        [config],
        documents,
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    problems = validate_results(payload)
    path = ROOT / "results" / "results.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote %s", path.relative_to(ROOT))
    logger.info("results.json check: %s", "PASS" if not problems else "FAIL " + "; ".join(problems))
    for item in documents:
        logger.info(
            "%s correctness=%.3f faithfulness=%.3f refusal_accuracy=%.3f over_refusals=%d p50=%s p95=%s tokens_per_query=%.1f failures=%s",
            item["doc_id"],
            item["correctness"],
            item["faithfulness"],
            item["refusal_accuracy"],
            item["over_refusals"],
            item["latency_p50_ms"],
            item["latency_p95_ms"],
            item["tokens_per_query"],
            item["failures_by_stage"],
        )


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    if args.stage == "ingest":
        if args.limit is not None:
            logger.info("ingest ignores --limit")
        run_ingest(args.config, args.doc, args.force)
        return
    if args.stage == "index":
        run_index(args.config, args.doc, args.force, args.limit)
        return
    if args.stage == "retrieve":
        run_retrieve(args.config, args.doc, args.force, args.limit)
        return
    if args.stage == "generate":
        run_generate(args.config, args.doc, args.force, args.limit, args.calls_per_minute)
        return
    if args.stage == "judge":
        run_judge(args.config, args.doc, args.force, args.limit)
        return
    if args.stage == "aggregate":
        run_aggregate(args.config, args.doc)
        return
    raise SystemExit(f"Stage {args.stage} is not implemented yet.")


if __name__ == "__main__":
    main(sys.argv[1:])
