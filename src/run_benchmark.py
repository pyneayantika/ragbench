"""
What it does: Command-line entry point that runs one stage for one config and one document.
Why it exists: One command must reproduce a run from the config file.
What breaks without it: Runs become one-off scripts and the numbers cannot be repeated.
Failure stage: none (reproducibility).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from src.chunk import chunk_document, get_tokenizer, token_count
from src.config import load_config
from src.ingest import DOC_FILES, ingest_document

logger = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one RAGBench stage.")
    parser.add_argument("--config", required=True, help="Config id, for example C1")
    parser.add_argument("--doc", required=True, help="annual_report, fund_doc, ghg_scope3, or all")
    parser.add_argument("--stage", required=True, help="Pipeline stage to run")
    parser.add_argument("--force", action="store_true", help="Ignore the cache and rebuild")
    parser.add_argument("--limit", type=int, default=None, help="Max questions; unused by ingest")
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


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    if args.stage != "ingest":
        raise SystemExit(f"Stage {args.stage} is not implemented yet. This step only runs ingest.")
    if args.limit is not None:
        logger.info("ingest ignores --limit")
    run_ingest(args.config, args.doc, args.force)


if __name__ == "__main__":
    main(sys.argv[1:])
