"""
What it does: Reads data/golden_set.csv and prints a problem report. It never writes that file.
Why it exists: A wrong page, a missing answer, or a copied passage would make later scores meaningless.
What breaks without it: Bad questions get indexed and the benchmark measures the set, not the pipeline.
Failure stage: evaluation.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pymupdf
from rapidfuzz.fuzz import partial_ratio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingest import DOC_FILES, load_cache, pdf_path

GOLDEN_PATH = ROOT / "data" / "golden_set.csv"
COLUMNS = [
    "qid",
    "doc_id",
    "question",
    "qtype",
    "gold_answer",
    "source_page",
    "supporting_text",
    "source",
]
DOC_IDS = ("annual_report", "fund_doc", "ghg_scope3")
PREFIX = {"annual_report": "AR-", "fund_doc": "FD-", "ghg_scope3": "GH-"}
QTYPE_COUNTS = {"fact": 6, "table": 5, "multi": 4, "paraphrase": 3, "unanswerable": 2}
ANSWERABLE = ("fact", "table", "multi", "paraphrase")
PARSINGS = ("basic", "layout")
SCORE_MIN = 90
ROWS_PER_DOC = 20
WORD_RE = re.compile(r"[A-Za-z0-9]+")
SPACE_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    return SPACE_RE.sub(" ", text.lower()).strip()


def word_present(page_text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", page_text) is not None


def longest_words(question: str, count: int = 3) -> list[str]:
    words = WORD_RE.findall(question)
    ranked = sorted(enumerate(words), key=lambda item: (-len(item[1]), item[0]))
    return [word.lower() for _, word in ranked[:count]]


def pdf_page_count(doc_id: str) -> int:
    document = pymupdf.open(pdf_path(doc_id))
    try:
        return int(document.page_count)
    finally:
        document.close()


def pages_by_number(doc_id: str, parsing: str) -> dict[int, str] | None:
    loaded = load_cache(ROOT / "cache" / "parsed" / f"{doc_id}__{parsing}.json")
    if loaded is None:
        return None
    pages: dict[int, str] = {}
    for record in loaded:
        if not isinstance(record, dict):
            continue
        page = record.get("page")
        text = record.get("text")
        if isinstance(page, int) and isinstance(text, str):
            pages[page] = normalise(text)
    return pages


def best_page(pages: dict[int, str], needle: str) -> tuple[int, float]:
    best_number = 0
    best_score = -1.0
    for number, text in pages.items():
        score = float(partial_ratio(needle, text))
        if score > best_score or (score == best_score and (best_number == 0 or number < best_number)):
            best_score = score
            best_number = number
    return best_number, best_score


def add(problems: list[tuple[str, str, str]], qid: str, kind: str, detail: str) -> None:
    problems.append((qid, kind, detail))


def check_shape(
    rows: list[dict[str, str]],
    fieldnames: list[str] | None,
    problems: list[tuple[str, str, str]],
) -> None:
    if fieldnames != COLUMNS:
        add(problems, "-", "columns", f"got {fieldnames}; expected {COLUMNS}")
    if len(rows) != len(DOC_IDS) * ROWS_PER_DOC:
        add(problems, "-", "row_count", f"{len(rows)} rows; expected {len(DOC_IDS) * ROWS_PER_DOC}")
    seen: dict[str, int] = {}
    per_doc: Counter[str] = Counter()
    per_type: dict[str, Counter[str]] = {doc_id: Counter() for doc_id in DOC_IDS}
    for row in rows:
        qid = row.get("qid", "").strip()
        doc_id = row.get("doc_id", "").strip()
        qtype = row.get("qtype", "").strip()
        per_doc[doc_id] += 1
        if doc_id in per_type:
            per_type[doc_id][qtype] += 1
        if qid in seen:
            add(problems, qid, "duplicate_qid", f"also on earlier row {seen[qid]}")
        else:
            seen[qid] = len(seen) + 1
        prefix = PREFIX.get(doc_id)
        if prefix is None:
            add(problems, qid or "-", "doc_id", f"unknown doc_id {doc_id!r}")
        elif not qid.startswith(prefix):
            add(problems, qid or "-", "qid_prefix", f"{qid!r} does not start with {prefix} for {doc_id}")
    for doc_id in DOC_IDS:
        if per_doc[doc_id] != ROWS_PER_DOC:
            add(problems, doc_id, "row_count", f"{per_doc[doc_id]} rows; expected {ROWS_PER_DOC}")
        for qtype, expected in QTYPE_COUNTS.items():
            found = per_type[doc_id][qtype]
            if found != expected:
                add(problems, doc_id, "qtype_mix", f"{qtype} {found}; expected {expected}")


def check_row_fields(row: dict[str, str], page_counts: dict[str, int], problems: list[tuple[str, str, str]]) -> None:
    qid = row.get("qid", "").strip() or "-"
    qtype = row.get("qtype", "").strip()
    gold = row.get("gold_answer", "").strip()
    page_raw = row.get("source_page", "").strip()
    support = row.get("supporting_text", "").strip()
    if qtype == "unanswerable":
        filled = [name for name, value in (("gold_answer", gold), ("source_page", page_raw), ("supporting_text", support)) if value]
        if filled:
            add(problems, qid, "unanswerable_not_empty", ", ".join(filled))
        return
    if qtype not in ANSWERABLE:
        add(problems, qid, "qtype", f"unknown qtype {qtype!r}")
        return
    missing = [name for name, value in (("gold_answer", gold), ("source_page", page_raw), ("supporting_text", support)) if not value]
    if missing:
        add(problems, qid, "empty_required", ", ".join(missing))
    if not page_raw:
        return
    if not page_raw.isdigit():
        add(problems, qid, "bad_source_page", page_raw)
        return
    page = int(page_raw)
    doc_id = row.get("doc_id", "").strip()
    limit = page_counts.get(doc_id)
    if limit is not None and not 1 <= page <= limit:
        add(problems, qid, "page_out_of_range", f"page {page}; PDF has {limit} pages")


def check_support(
    rows: list[dict[str, str]],
    caches: dict[tuple[str, str], dict[int, str] | None],
    problems: list[tuple[str, str, str]],
) -> None:
    print("SUPPORT SCORES")
    print(f"{'qid':<8} {'mode':<8} {'part':<4} {'page':>4} {'score':>7} {'best_page':>9} {'best_score':>10}")
    for row in rows:
        qtype = row.get("qtype", "").strip()
        if qtype not in ANSWERABLE:
            continue
        qid = row.get("qid", "").strip() or "-"
        doc_id = row.get("doc_id", "").strip()
        page_raw = row.get("source_page", "").strip()
        support = row.get("supporting_text", "").strip()
        if not support or not page_raw.isdigit():
            continue
        stated = int(page_raw)
        parts = support.split(" ||| ") if qtype == "multi" else [support]
        for index, part in enumerate(parts, start=1):
            needle = normalise(part)
            if not needle:
                add(problems, qid, "empty_required", f"supporting part {index} is empty")
                continue
            for parsing in PARSINGS:
                pages = caches.get((doc_id, parsing))
                if pages is None:
                    add(problems, qid, "cache_missing", f"{doc_id}__{parsing}.json")
                    continue
                stated_text = pages.get(stated, "")
                stated_score = float(partial_ratio(needle, stated_text)) if stated_text else 0.0
                best_number, best_score = best_page(pages, needle)
                best_label = "" if stated_score >= SCORE_MIN else str(best_number)
                best_value = "" if stated_score >= SCORE_MIN else f"{best_score:.1f}"
                print(
                    f"{qid:<8} {parsing:<8} {index:<4} {stated:>4} {stated_score:>7.1f} {best_label:>9} {best_value:>10}"
                )
                if stated_score < SCORE_MIN:
                    add(
                        problems,
                        qid,
                        "supporting_text_low",
                        f"{parsing} part {index} scores {stated_score:.1f} on page {stated}; best is page {best_number} at {best_score:.1f}",
                    )


def check_unanswerable(
    rows: list[dict[str, str]],
    caches: dict[tuple[str, str], dict[int, str] | None],
    problems: list[tuple[str, str, str]],
) -> None:
    print()
    print("UNANSWERABLE TERM SCAN")
    print(f"{'qid':<8} {'words':<40} {'basic pages':<24} {'layout pages'}")
    for row in rows:
        if row.get("qtype", "").strip() != "unanswerable":
            continue
        qid = row.get("qid", "").strip() or "-"
        doc_id = row.get("doc_id", "").strip()
        words = longest_words(row.get("question", ""))
        if len(words) < 3:
            add(problems, qid, "too_few_words", f"question has {len(words)} words")
        found: dict[str, list[int]] = {}
        for parsing in PARSINGS:
            pages = caches.get((doc_id, parsing))
            if pages is None:
                add(problems, qid, "cache_missing", f"{doc_id}__{parsing}.json")
                found[parsing] = []
                continue
            hits = [
                number
                for number in sorted(pages)
                if all(word_present(pages[number], word) for word in words)
            ]
            found[parsing] = hits
            if hits:
                add(problems, qid, "unanswerable_terms", f"{parsing} pages {', '.join(str(n) for n in hits)}; words {', '.join(words)}")
        print(
            f"{qid:<8} {', '.join(words):<40} "
            f"{', '.join(str(n) for n in found.get('basic', [])) or '-':<24} "
            f"{', '.join(str(n) for n in found.get('layout', [])) or '-'}"
        )


def check_duplicate_support(rows: list[dict[str, str]], problems: list[tuple[str, str, str]]) -> None:
    owners: dict[str, str] = {}
    for row in rows:
        text = row.get("supporting_text", "").strip()
        if not text:
            continue
        qid = row.get("qid", "").strip() or "-"
        if text in owners:
            add(problems, qid, "duplicate_supporting_text", f"same text as {owners[text]}")
        else:
            owners[text] = qid


def print_problems(problems: list[tuple[str, str, str]]) -> None:
    print()
    print("PROBLEMS")
    print(f"{'qid':<16} {'type':<28} detail")
    if not problems:
        print("(none)")
    for qid, kind, detail in problems:
        print(f"{qid:<16} {kind:<28} {detail}")
    print()
    print("SUMMARY")
    counts = Counter(kind for _, kind, _ in problems)
    if not counts:
        print("total problems: 0")
        return
    for kind in sorted(counts):
        print(f"{kind}: {counts[kind]}")
    print(f"total problems: {sum(counts.values())}")


def file_mtime(path: Path) -> str:
    if not path.is_file():
        return "missing"
    stamp = datetime.fromtimestamp(path.stat().st_mtime)
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    print(f"golden_set.csv mtime before: {file_mtime(GOLDEN_PATH)}")
    if not GOLDEN_PATH.is_file():
        print("PROBLEMS")
        print(f"{'-':<16} {'missing_file':<28} data/golden_set.csv is not in the project")
        print()
        print("SUMMARY")
        print("missing_file: 1")
        print("total problems: 1")
        print(f"golden_set.csv mtime after: {file_mtime(GOLDEN_PATH)}")
        return 1
    # utf-8-sig drops a leading Excel byte mark on read. The CSV file is not rewritten.
    with GOLDEN_PATH.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    problems: list[tuple[str, str, str]] = []
    check_shape(rows, fieldnames, problems)
    page_counts = {doc_id: pdf_page_count(doc_id) for doc_id in DOC_IDS}
    print("PDF PAGE COUNTS")
    for doc_id, count in page_counts.items():
        print(f"{doc_id}: {count}")
    caches = {(doc_id, parsing): pages_by_number(doc_id, parsing) for doc_id in DOC_IDS for parsing in PARSINGS}
    for (doc_id, parsing), pages in caches.items():
        if pages is None:
            add(problems, doc_id, "cache_missing", f"cache/parsed/{doc_id}__{parsing}.json")
        elif len(pages) != page_counts[doc_id]:
            add(problems, doc_id, "cache_page_count", f"{parsing} cache has {len(pages)} pages; PDF has {page_counts[doc_id]}")
    for row in rows:
        check_row_fields(row, page_counts, problems)
    check_support(rows, caches, problems)
    check_unanswerable(rows, caches, problems)
    check_duplicate_support(rows, problems)
    print_problems(problems)
    print(f"golden_set.csv mtime after: {file_mtime(GOLDEN_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
