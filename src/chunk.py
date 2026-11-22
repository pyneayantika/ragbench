"""
What it does: Splits parsed pages into chunks of at most 256 tokens, optionally adding a context header.
Why it exists: Embedding models have a token limit, and retrieval needs focused pieces of text.
What breaks without it: Chunks are cut off, or an answer is split across two chunks.
Failure stage: indexing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache" / "chunks"
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKENIZERS: dict[str, Any] = {}


def chunk_sig(config: dict[str, Any]) -> str:
    chunking = config["chunking"]
    payload = "|".join(
        [
            str(config["parsing"]),
            str(chunking["strategy"]),
            str(chunking["max_tokens"]),
            str(chunking["overlap_tokens"]),
            str(bool(chunking["contextual_headers"])),
            str(config["embedding_model"]),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def cache_path(doc_id: str, signature: str) -> Path:
    return CACHE_DIR / f"{doc_id}__{signature}.jsonl"


def get_tokenizer(model_name: str) -> Any:
    if model_name not in _TOKENIZERS:
        logger.info("loading tokenizer %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.model_max_length = max(int(tokenizer.model_max_length), 1_000_000)
        _TOKENIZERS[model_name] = tokenizer
    return _TOKENIZERS[model_name]


def token_ids(tokenizer: Any, text: str) -> list[int]:
    if not text:
        return []
    encoded = tokenizer.encode(text, add_special_tokens=False)
    return list(encoded)


def token_count(tokenizer: Any, text: str) -> int:
    return len(token_ids(tokenizer, text))


def text_within_limit(tokenizer: Any, ids: list[int], limit: int) -> str:
    chosen = list(ids[:limit])
    while chosen:
        decoded = tokenizer.decode(chosen, skip_special_tokens=True)
        if isinstance(decoded, str) and token_count(tokenizer, decoded) <= limit:
            return decoded
        chosen.pop()
    return ""


def _paragraphs(pages: list[dict[str, Any]]) -> tuple[list[tuple[str, int, str]], bool]:
    heading = ""
    found = False
    rows: list[tuple[str, int, str]] = []
    for page in pages:
        raw = page.get("text")
        text = raw.replace("\r\n", "\n") if isinstance(raw, str) else ""
        page_no = int(page["page"])
        buffer: list[str] = []

        def flush() -> None:
            paragraph = "\n".join(buffer).strip()
            buffer.clear()
            if paragraph:
                rows.append((paragraph, page_no, heading))

        for line in text.split("\n"):
            match = HEADING_LINE.match(line.strip())
            if match:
                flush()
                heading = match.group(2).strip()
                found = True
                continue
            if not line.strip():
                flush()
            else:
                buffer.append(line)
        flush()
    return rows, found


def _pieces(tokenizer: Any, text: str, limit: int) -> list[str]:
    if token_count(tokenizer, text) <= limit:
        return [text]
    parts: list[str] = []
    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        ids = token_ids(tokenizer, sentence)
        if len(ids) <= limit:
            parts.append(sentence)
            continue
        for start in range(0, len(ids), limit):
            fitted = text_within_limit(tokenizer, ids[start : start + limit], limit)
            if fitted.strip():
                parts.append(fitted.strip())
    return parts


def _pack_rows(tokenizer: Any, rows: list[tuple[str, int, str]], limit: int, use_headings: bool) -> list[dict[str, Any]]:
    packed: list[dict[str, Any]] = []
    body: list[tuple[str, int]] = []
    heading = ""
    page_start = 0
    page_end = 0
    used = 0

    def emit() -> None:
        if not body:
            return
        text = "\n\n".join(piece for piece, _page in body).strip()
        if text:
            packed.append({"text": text, "page_start": page_start, "page_end": page_end, "section_heading": heading})

    for paragraph, page_no, row_heading in rows:
        section = row_heading if use_headings else ""
        if body and section != heading:
            emit()
            body = []
            used = 0
        heading = section
        prefix = f"{heading}\n" if heading else ""
        budget = limit - token_count(tokenizer, prefix)
        if budget < 1:
            budget = limit
            prefix = ""
        for piece in _pieces(tokenizer, paragraph, budget):
            piece_text = f"{prefix}{piece}" if prefix and not body else piece
            cost = token_count(tokenizer, piece_text if not body else piece)
            if body and used + cost > limit:
                emit()
                body = []
                used = 0
                piece_text = f"{prefix}{piece}" if prefix else piece
                cost = token_count(tokenizer, piece_text)
            if not body:
                page_start = page_no
            body.append((piece_text, page_no))
            page_end = page_no
            used += cost
    emit()
    return packed


def _fixed_chunks(tokenizer: Any, pages: list[dict[str, Any]], limit: int, overlap: int) -> list[dict[str, Any]]:
    if overlap >= limit:
        raise ValueError(f"overlap_tokens ({overlap}) must be smaller than max_tokens ({limit})")
    units: list[tuple[int, int]] = []
    for page in pages:
        raw = page.get("text")
        text = raw if isinstance(raw, str) else ""
        page_no = int(page["page"])
        units.extend((token_id, page_no) for token_id in token_ids(tokenizer, text))
    chunks: list[dict[str, Any]] = []
    step = limit - overlap
    start = 0
    while start < len(units):
        window = units[start : start + limit]
        text = text_within_limit(tokenizer, [token_id for token_id, _page in window], limit)
        if text.strip():
            chunks.append(
                {
                    "text": text.strip(),
                    "page_start": window[0][1],
                    "page_end": window[-1][1],
                    "section_heading": "",
                }
            )
        if start + limit >= len(units):
            break
        start += step
    return chunks


def _with_header(doc_id: str, heading: str, text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"Document: {doc_id} | Section: {heading}\n{text}"


def _header_cost(tokenizer: Any, doc_id: str, heading: str, enabled: bool) -> int:
    if not enabled:
        return 0
    return token_count(tokenizer, f"Document: {doc_id} | Section: {heading}\n")


def _rows_within_limit(tokenizer: Any, doc_id: str, rows: list[dict[str, Any]], limit: int, enabled: bool) -> list[dict[str, Any]]:
    fitted: list[dict[str, Any]] = []
    for row in rows:
        heading = str(row["section_heading"])
        budget = limit - _header_cost(tokenizer, doc_id, heading, enabled)
        budget = max(budget, 1)
        ids = token_ids(tokenizer, str(row["text"]))
        start = 0
        while start < len(ids):
            text = text_within_limit(tokenizer, ids[start : start + budget], budget)
            if not text.strip():
                start += 1
                continue
            embed = _with_header(doc_id, heading, text.strip(), enabled)
            while token_count(tokenizer, embed) > limit and text:
                text = text[:-1]
                embed = _with_header(doc_id, heading, text.strip(), enabled)
            if text.strip() and token_count(tokenizer, embed) <= limit:
                fitted.append(
                    {
                        "text": text.strip(),
                        "embed_text": embed,
                        "page_start": row["page_start"],
                        "page_end": row["page_end"],
                        "section_heading": heading,
                    }
                )
            consumed = max(1, len(token_ids(tokenizer, text.strip())))
            start += consumed
    return fitted


def build_chunks(doc_id: str, config: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunking = config["chunking"]
    limit = int(chunking["max_tokens"])
    tokenizer = get_tokenizer(str(config["embedding_model"]))
    headers = bool(chunking["contextual_headers"])
    if chunking["strategy"] == "fixed":
        rows = _fixed_chunks(tokenizer, pages, limit, int(chunking["overlap_tokens"]))
    elif chunking["strategy"] == "structure":
        paragraphs, found_headings = _paragraphs(pages)
        rows = _pack_rows(tokenizer, paragraphs, limit, use_headings=found_headings)
    else:
        raise ValueError(f"Unknown chunking strategy {chunking['strategy']}")
    chunks: list[dict[str, Any]] = []
    for row in _rows_within_limit(tokenizer, doc_id, rows, limit, headers):
        row["chunk_id"] = f"{doc_id}-{len(chunks):04d}"
        row["doc_id"] = doc_id
        chunks.append(row)
    return chunks


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise ValueError(f"Chunk cache row is not an object: {path.relative_to(ROOT)}")
            rows.append(loaded)
    return rows


def chunk_document(doc_id: str, config: dict[str, Any], pages: list[dict[str, Any]], force: bool = False) -> tuple[list[dict[str, Any]], bool]:
    path = cache_path(doc_id, chunk_sig(config))
    if path.is_file() and not force:
        logger.info("cache hit %s", path.relative_to(ROOT))
        return _read_jsonl(path), True
    logger.info("cache miss %s", path.relative_to(ROOT))
    chunks = build_chunks(doc_id, config, pages)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    lines = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
    temporary.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temporary.replace(path)
    return chunks, False
