"""
What it does: Turns each PDF page into text, using basic extraction or layout-aware parsing.
Why it exists: The model can only answer from text the parser actually read.
What breaks without it: Columns and tables stay garbled, and every later stage is wrong.
Failure stage: ingestion.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pymupdf
import pymupdf4llm

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = ROOT / "cache" / "parsed"
DOC_FILES = {
    "annual_report": RAW_DIR / "annual_report.pdf",
    "fund_doc": RAW_DIR / "fund_doc.pdf",
    "ghg_scope3": RAW_DIR / "ghg_scope3.pdf",
}


def cache_path(doc_id: str, parsing: str) -> Path:
    return CACHE_DIR / f"{doc_id}__{parsing}.json"


def pdf_path(doc_id: str) -> Path:
    if doc_id not in DOC_FILES:
        known = ", ".join(DOC_FILES)
        raise FileNotFoundError(f"Unknown doc_id {doc_id}. Known: {known}")
    path = DOC_FILES[doc_id]
    if not path.is_file():
        raise FileNotFoundError(f"Missing PDF: {path.relative_to(ROOT)}")
    return path


def load_cache(path: Path) -> list[dict[str, object]] | None:
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError(f"Cache is not a list: {path.relative_to(ROOT)}")
    return loaded


def save_cache(path: Path, pages: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def parse_basic(doc_id: str, path: Path) -> list[dict[str, object]]:
    document = pymupdf.open(path)
    try:
        return [
            {"doc_id": doc_id, "page": index, "text": page.get_text()}
            for index, page in enumerate(document, start=1)
        ]
    finally:
        document.close()


def layout_text_by_page(chunks: object) -> dict[int, str]:
    if not isinstance(chunks, list):
        raise TypeError("layout parse did not return a list of page chunks")
    by_page: dict[int, str] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict) or "text" not in chunk:
            raise TypeError("layout chunk is missing text")
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("page_number"), int):
            raise TypeError("layout chunk is missing metadata.page_number")
        text = chunk["text"]
        by_page[metadata["page_number"]] = text if isinstance(text, str) else ""
    return by_page


def parse_layout(doc_id: str, path: Path) -> list[dict[str, object]]:
    by_page = layout_text_by_page(pymupdf4llm.to_markdown(str(path), page_chunks=True))
    document = pymupdf.open(path)
    try:
        count = document.page_count
    finally:
        document.close()
    return [
        {"doc_id": doc_id, "page": number, "text": by_page.get(number, "")}
        for number in range(1, count + 1)
    ]


def parse_pdf(doc_id: str, parsing: str) -> list[dict[str, object]]:
    path = pdf_path(doc_id)
    if parsing == "basic":
        return parse_basic(doc_id, path)
    if parsing == "layout":
        return parse_layout(doc_id, path)
    raise ValueError(f"Unknown parsing mode {parsing}")


def ingest_document(doc_id: str, parsing: str, force: bool = False) -> tuple[list[dict[str, object]], bool]:
    path = cache_path(doc_id, parsing)
    if not force:
        cached = load_cache(path)
        if cached is not None:
            logger.info("cache hit %s", path.relative_to(ROOT))
            return cached, True
    logger.info("cache miss %s", path.relative_to(ROOT))
    pages = parse_pdf(doc_id, parsing)
    save_cache(path, pages)
    return pages, False
